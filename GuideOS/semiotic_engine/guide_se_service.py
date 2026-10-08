"""Loopback-only HTTP service for the independent Guide Semiotic Engine."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import threading
from typing import Any
from urllib.parse import urlsplit

from guide_se_core import BackendProblem, JobManager, PROTOCOL, RequestProblem


DEFAULT_PORT = 4370
MAX_BODY_BYTES = 64 * 1024


def default_connection_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "GuideSemioticEngine" / "connection.json"


def load_or_create_connection(path: Path, port: int) -> dict[str, object]:
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current = {}
    token = current.get("token") if isinstance(current, dict) else None
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
    record = {"protocol": PROTOCOL, "url": f"http://127.0.0.1:{port}", "token": token}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return record


class EngineServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR can allow multiple live listeners on the same
    # address, making requests reach an older Engine instance unpredictably.
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], manager: JobManager, token: str) -> None:
        super().__init__(address, EngineHandler)
        self.manager = manager
        self.token = token


class EngineHandler(BaseHTTPRequestHandler):
    server: EngineServer
    server_version = "GuideSemioticEngine/0"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, value: dict[str, object]) -> None:
        body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        return header.startswith("Bearer ") and secrets.compare_digest(header[7:].strip(), self.server.token)

    def _read(self) -> dict | None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if not 1 <= size <= MAX_BODY_BYTES:
            return None
        try:
            value = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _job_id(self) -> str:
        path = urlsplit(self.path).path
        match = re.fullmatch(r"/semiotic/v0/jobs/([0-9a-f]{32})", path)
        return match.group(1) if match else ""

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/semiotic/v0/about":
            self._send(200, self.server.manager.about())
            return
        if not self._authorized():
            self._send(401, {"error": "connection credential required"})
            return
        if path == "/semiotic/v0/status":
            self._send(200, self.server.manager.status())
            return
        job = self.server.manager.get(self._job_id())
        self._send(200, job.public()) if job else self._send(404, {"error": "job not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(401, {"error": "connection credential required"})
            return
        path = urlsplit(self.path).path
        if path == "/semiotic/v0/shutdown":
            self._send(202, {"protocol": PROTOCOL, "stopping": True})
            threading.Thread(target=self.server.shutdown,
                             name="guide-se-shutdown", daemon=True).start()
            return
        if path != "/semiotic/v0/jobs":
            self._send(404, {"error": "not found"})
            return
        value = self._read()
        if value is None:
            self._send(400, {"error": "invalid or oversized JSON request"})
            return
        try:
            job = self.server.manager.submit(value)
        except RequestProblem as problem:
            self._send(400, {"error": str(problem)})
            return
        self._send(202, job.public())

    def do_DELETE(self) -> None:
        if not self._authorized():
            self._send(401, {"error": "connection credential required"})
            return
        job = self.server.manager.cancel(self._job_id())
        self._send(202, job.public()) if job else self._send(404, {"error": "job not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the independent Guide Semiotic Engine")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--connection-file", type=Path, default=default_connection_path())
    parser.add_argument("--backend", choices=("deterministic", "llama-cpp"),
                        default="deterministic")
    parser.add_argument("--llama-server", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--gpu-layers", type=int, default=999)
    args = parser.parse_args()
    connection = load_or_create_connection(args.connection_file, args.port)
    backend = None
    if args.backend == "llama-cpp":
        if args.llama_server is None or args.model is None:
            parser.error("--llama-server and --model are required for the llama-cpp backend")
        from llama_cpp_backend import LlamaCppBackend
        try:
            backend = LlamaCppBackend(args.llama_server, args.model, args.gpu_layers)
        except BackendProblem as error:
            parser.error(str(error))
    manager = JobManager(backend)
    server = EngineServer(("127.0.0.1", args.port), manager, str(connection["token"]))
    print(f"Guide Semiotic Engine ready on 127.0.0.1:{args.port}")
    print(f"Local connection record: {args.connection_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()


if __name__ == "__main__":
    main()
