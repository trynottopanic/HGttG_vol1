#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deck-side VISITING-SCREEN-1 media offer and temporary stream."""

from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

from thirdway_host import is_local_client, local_ipv4, parse_byte_range, safe_filename, url_uses_local_address


APP_NAME = "Third Way Deck Media"
APP_VERSION = "0.1.0"
MEDIA_LIFETIME = 6 * 60 * 60


@dataclass
class DeckState:
    movie: Path
    display_name: str
    mime_type: str
    stream_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    revoke_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    active: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.active.set()

    def available(self) -> bool:
        if time.time() > self.started_at + MEDIA_LIFETIME:
            self.active.clear()
        return self.active.is_set()


class DeckServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: DeckState):
        super().__init__(address, DeckHandler)
        self.state = state
        self.lan_ip = local_ipv4()

    @property
    def stream_url(self) -> str:
        name = urllib.parse.quote(self.state.display_name)
        return f"http://{self.lan_ip}:{self.server_port}/stream/{self.state.stream_token}/{name}"

    @property
    def revoke_url(self) -> str:
        return f"http://{self.lan_ip}:{self.server_port}/control/{self.state.revoke_token}/revoke"


class DeckHandler(BaseHTTPRequestHandler):
    server: DeckServer

    def log_message(self, message: str, *args: object) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), message % args))

    def _local_allowed(self) -> bool:
        return is_local_client(self.client_address[0])

    def _text(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if self.path == "/health":
            status = "available" if self.server.state.available() else "revoked"
            self._text(HTTPStatus.OK, status)
            return
        prefix = f"/stream/{self.server.state.stream_token}/"
        if self.path.startswith(prefix):
            self._serve_movie()
            return
        self._text(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self) -> None:
        expected = f"/control/{self.server.state.revoke_token}/revoke"
        if self.path != expected:
            self._text(HTTPStatus.NOT_FOUND, "Not found.")
            return
        if not self._local_allowed():
            self._text(HTTPStatus.FORBIDDEN, "Local-network access only.")
            return
        self.server.state.active.clear()
        self._text(HTTPStatus.OK, "Deck stream revoked.")

    def _serve_movie(self) -> None:
        state = self.server.state
        if not self._local_allowed() or not state.available():
            self._text(HTTPStatus.FORBIDDEN, "Deck stream is not available.")
            return
        size = state.movie.stat().st_size
        byte_range = None
        if self.headers.get("Range"):
            byte_range = parse_byte_range(self.headers["Range"], size)
            if byte_range is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        start, end = byte_range or (0, size - 1)
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if byte_range else HTTPStatus.OK)
        self.send_header("Content-Type", state.mime_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(state.display_name)}")
        self.send_header("transferMode.dlna.org", "Streaming")
        self.send_header("contentFeatures.dlna.org", "DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000")
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with state.movie.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining and state.available():
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


def parse_join_address(raw: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(raw.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "http" or not parsed.netloc or len(parts) != 2 or parts[0] != "join":
        raise ValueError("expected the complete http://.../join/12345678 address")
    if not url_uses_local_address(raw):
        raise ValueError("the pairing address is not on this local network")
    return f"{parsed.scheme}://{parsed.netloc}", parts[1]


def send_offer(host_base: str, pair_code: str, server: DeckServer) -> str:
    state = server.state
    body = json.dumps(
        {
            "name": state.display_name,
            "size": state.movie.stat().st_size,
            "mime_type": state.mime_type,
            "url": server.stream_url,
            "revoke_url": server.revoke_url,
        }
    ).encode("utf-8")
    url = f"{host_base}/api/offer?code={urllib.parse.quote(pair_code)}"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        result = json.loads(response.read())
    return str(result["offer_token"])


def withdraw_offer(host_base: str, offer_token: str) -> None:
    if not offer_token:
        return
    url = f"{host_base}/api/withdraw?offer={urllib.parse.quote(offer_token)}"
    try:
        request = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(request, timeout=2) as response:
            response.read()
    except (OSError, ValueError):
        pass


def clean_dragged_path(raw: str) -> str:
    return raw.strip().strip('"').strip("'")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="movie to offer")
    parser.add_argument("--join", help="visitor pairing address shown by the host")
    parser.add_argument("--port", type=int, default=0, help="Deck stream port; zero chooses one")
    return parser


def run(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"{APP_NAME} {APP_VERSION}", flush=True)
    file_text = args.file or input("Drag the movie into this window, then press Enter:\n> ")
    join_text = args.join or input("Paste the owner's Visitor pairing address:\n> ")
    movie = Path(clean_dragged_path(file_text)).expanduser().resolve()
    if not movie.is_file() or movie.stat().st_size <= 0:
        raise SystemExit("The selected movie is not a readable non-empty file.")
    try:
        host_base, pair_code = parse_join_address(join_text)
    except ValueError as error:
        raise SystemExit(f"Pairing address rejected: {error}") from error
    mime_type = mimetypes.guess_type(movie.name)[0] or "application/octet-stream"
    state = DeckState(movie, safe_filename(movie.name), mime_type)
    server = DeckServer(("0.0.0.0", args.port), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    offer_token = ""
    try:
        offer_token = send_offer(host_base, pair_code, server)
        print("The movie remains on this Deck and is waiting for the owner's approval.", flush=True)
        print("Keep this window open during playback.", flush=True)
        input("Press Enter to withdraw the offer and stop sharing.\n")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        print(f"The host rejected this offer: {detail or error.reason}")
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"The Deck could not reach the host: {error}")
        return 1
    except KeyboardInterrupt:
        print("\nWithdrawing the offer...")
    finally:
        state.active.clear()
        withdraw_offer(host_base, offer_token)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
