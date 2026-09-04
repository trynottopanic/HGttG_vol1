#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GuideOS-side receiver for the CONTINUE-ON-DECK-0 prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

API_VERSION = "third-way.continue-on-deck/1"
SUPPORTED_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".webm"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def safe_name(value: str) -> str:
    name = Path(value).name.strip().replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9._ ()\-]", "_", name)
    return name[:180] or "video"


@dataclass
class Pending:
    handoff_id: str
    token: str
    metadata: dict
    part_path: Path
    received_size: int = 0
    received_hash: str = ""


class HandoffStore:
    def __init__(self, root: Path, deck_name: str = "My Deck", max_bytes: int = 32 << 30,
                 on_commit: Callable[[dict, Path], None] | None = None):
        self.root = root
        self.deck_name = deck_name
        self.max_bytes = max_bytes
        self.on_commit = on_commit
        self.incoming = root / ".incoming"
        self.library = root / "library"
        self.incoming.mkdir(parents=True, exist_ok=True)
        self.library.mkdir(parents=True, exist_ok=True)
        self._remove_abandoned_parts()
        self.pending: dict[str, Pending] = {}
        self.lock = threading.Lock()

    def _remove_abandoned_parts(self) -> None:
        """A prior interrupted transfer must never survive as usable media."""
        for path in self.incoming.iterdir():
            if path.is_file() and (path.name.endswith(".part") or path.name.endswith(".json.part")):
                path.unlink(missing_ok=True)

    def describe(self) -> dict:
        return {
            "protocol": API_VERSION,
            "deck_name": self.deck_name,
            "free_bytes": shutil.disk_usage(self.root).free,
            "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        }

    def begin(self, metadata: dict) -> Pending:
        required = {"display_name", "size_bytes", "sha256", "position_ms", "created_utc"}
        if not required.issubset(metadata):
            raise ValueError("The handoff description is incomplete.")
        name = safe_name(str(metadata["display_name"]))
        size = int(metadata["size_bytes"])
        position = int(metadata["position_ms"])
        digest = str(metadata["sha256"]).lower()
        if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("This video format is not supported by the prototype Deck.")
        if size <= 0 or size > self.max_bytes:
            raise ValueError("The video size is outside the Deck's transfer limit.")
        if size > shutil.disk_usage(self.root).free:
            raise ValueError("The Deck does not have enough free space.")
        if position < 0 or not SHA256_RE.fullmatch(digest):
            raise ValueError("The playback position or file fingerprint is invalid.")
        clean = dict(metadata, display_name=name, size_bytes=size, position_ms=position, sha256=digest)
        handoff_id = str(uuid.uuid4())
        pending = Pending(handoff_id, secrets.token_urlsafe(32), clean, self.incoming / f"{handoff_id}.part")
        with self.lock:
            self.pending[handoff_id] = pending
        return pending

    def receive(self, handoff_id: str, token: str, source, length: int) -> Pending:
        pending = self._authorized(handoff_id, token)
        if length != pending.metadata["size_bytes"]:
            raise ValueError("The sent size does not match the promised size.")
        digest = hashlib.sha256()
        written = 0
        with pending.part_path.open("wb") as target:
            while written < length:
                chunk = source.read(min(1024 * 1024, length - written))
                if not chunk:
                    raise ValueError("The cable transfer ended before the file was complete.")
                target.write(chunk)
                digest.update(chunk)
                written += len(chunk)
            target.flush()
            os.fsync(target.fileno())
        pending.received_size = written
        pending.received_hash = digest.hexdigest()
        return pending

    def commit(self, handoff_id: str, token: str) -> dict:
        pending = self._authorized(handoff_id, token)
        expected_size = pending.metadata["size_bytes"]
        expected_hash = pending.metadata["sha256"]
        if pending.received_size != expected_size or pending.received_hash != expected_hash:
            self.cancel(handoff_id)
            raise ValueError("Verification failed; the incomplete copy was discarded.")
        media_name = f"{handoff_id}-{pending.metadata['display_name']}"
        final_media = self.library / media_name
        manifest = dict(pending.metadata, protocol=API_VERSION, handoff_id=handoff_id,
                        media_file=media_name, received_utc=int(time.time()))
        manifest_tmp = self.incoming / f"{handoff_id}.json.part"
        manifest_final = self.library / f"{handoff_id}.guide-resume.json"
        os.replace(pending.part_path, final_media)
        with manifest_tmp.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(manifest, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(manifest_tmp, manifest_final)
        with self.lock:
            self.pending.pop(handoff_id, None)
        if self.on_commit:
            self.on_commit(manifest, final_media)
        return manifest

    def cancel(self, handoff_id: str) -> None:
        with self.lock:
            pending = self.pending.pop(handoff_id, None)
        if pending:
            pending.part_path.unlink(missing_ok=True)

    def _authorized(self, handoff_id: str, token: str) -> Pending:
        with self.lock:
            pending = self.pending.get(handoff_id)
        if not pending or not secrets.compare_digest(pending.token, token):
            raise PermissionError("This transfer capability is not valid.")
        return pending


class DeckServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store: HandoffStore, pairing_code: str,
                 pairing_lifetime_seconds: int = 600, max_pairing_failures: int = 10):
        self.store = store
        self.pairing_code = pairing_code
        self.pairing_deadline = time.monotonic() + pairing_lifetime_seconds
        self.max_pairing_failures = max_pairing_failures
        self.pairing_failures = 0
        self.pairing_lock = threading.Lock()
        super().__init__(address, DeckHandler)

    def accept_pairing_code(self, candidate: str) -> bool:
        with self.pairing_lock:
            if time.monotonic() > self.pairing_deadline:
                return False
            if self.pairing_failures >= self.max_pairing_failures:
                return False
            accepted = secrets.compare_digest(candidate, self.pairing_code)
            if not accepted:
                self.pairing_failures += 1
            return accepted


class DeckHandler(BaseHTTPRequestHandler):
    server: DeckServer

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _token(self) -> str:
        return self.headers.get("Authorization", "").removeprefix("Bearer ")

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/v1/deck":
            self._json(HTTPStatus.OK, self.server.store.describe())
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown request."})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/v1/handoffs":
                if not self.server.accept_pairing_code(self.headers.get("X-Guide-Pairing-Code", "")):
                    raise PermissionError("The Deck pairing code is incorrect, expired, or temporarily locked.")
                length = int(self.headers.get("Content-Length", "0"))
                metadata = json.loads(self.rfile.read(length))
                pending = self.server.store.begin(metadata)
                self._json(HTTPStatus.CREATED, {"handoff_id": pending.handoff_id, "token": pending.token})
                return
            match = re.fullmatch(r"/v1/handoffs/([0-9a-f-]+)/commit", path)
            if match:
                manifest = self.server.store.commit(match.group(1), self._token())
                self._json(HTTPStatus.OK, {"status": "ready", "resume": manifest})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown request."})
        except PermissionError as error:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_PUT(self) -> None:
        match = re.fullmatch(r"/v1/handoffs/([0-9a-f-]+)/media", urlparse(self.path).path)
        if not match:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown request."})
            return
        try:
            pending = self.server.store.receive(match.group(1), self._token(), self.rfile,
                                                int(self.headers.get("Content-Length", "-1")))
            self._json(HTTPStatus.OK, {"received_bytes": pending.received_size,
                                      "sha256": pending.received_hash})
        except PermissionError as error:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(error)})
        except ValueError as error:
            self.server.store.cancel(match.group(1))
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def log_message(self, format: str, *args) -> None:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="192.168.77.2")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--storage", type=Path, default=Path("/data/guide-media"))
    parser.add_argument("--deck-name", default="Anbernic Deck")
    parser.add_argument("--pair-code", default=None)
    parser.add_argument("--pair-code-minutes", type=int, default=10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    code = args.pair_code or f"{secrets.randbelow(1_000_000):06d}"
    print(f"Deck pairing code: {code}", flush=True)
    server = DeckServer((args.listen, args.port), HandoffStore(args.storage, args.deck_name), code,
                        pairing_lifetime_seconds=max(1, args.pair_code_minutes * 60))
    server.serve_forever()


if __name__ == "__main__":
    main()
