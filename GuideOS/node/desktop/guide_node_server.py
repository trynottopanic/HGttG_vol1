"""Local HTTP and UDP discovery service for the Guide desktop Node."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from guide_node_core import (
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_HTTP_PORT,
    PROTOCOL_VERSION,
    NodeState,
    is_local_address,
)


MAX_BODY_BYTES = 16 * 1024
DISCOVERY_REQUEST = b"GUIDE-DISCOVER/1\n"
MEDIA_STREAM_TIMEOUT_SECONDS = 10 * 60


def parse_byte_range(value: str, size: int) -> tuple[int, int] | None:
    """Parse one HTTP byte range; return an inclusive start/end pair."""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or size <= 0:
        return None
    first, second = match.groups()
    if not first:
        if not second:
            return None
        length = int(second)
        if length <= 0:
            return None
        return max(0, size - length), size - 1
    start = int(first)
    if start >= size:
        return None
    end = size - 1 if not second else min(int(second), size - 1)
    if end < start:
        return None
    return start, end


def local_ip_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


class GuideHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: NodeState) -> None:
        super().__init__(address, GuideRequestHandler)
        self.state = state


class GuideRequestHandler(BaseHTTPRequestHandler):
    server: GuideHTTPServer
    server_version = "GuideNode/0.1"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format: str, *args: Any) -> None:
        # Pairing secrets and authorization headers must never reach a log file.
        return

    def _send(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _path(self) -> str:
        return urlsplit(self.path).path

    def _local_peer(self) -> bool:
        return is_local_address(self.client_address[0])

    def _token(self) -> str:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return ""
        return header[7:].strip()

    def _authorized(self) -> bool:
        return self.server.state.authenticate(self._token())

    def _read_json(self) -> dict[str, object] | None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if size <= 0 or size > MAX_BODY_BYTES:
            return None
        try:
            value = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def do_GET(self) -> None:
        if not self._local_peer():
            self._send(403, {"error": "local network only"})
            return
        path = self._path()
        if path == "/guide/v1/about":
            self._send(200, self.server.state.public_description())
            return
        if path.startswith("/guide/v1/play/"):
            ticket = path.rsplit("/", 1)[-1]
            record = self.server.state.resolve_media_ticket(ticket)
            if record is None:
                self._send(404, {"error": "playback ticket expired or revoked"})
            else:
                self._send_media_record(record, send_body=True)
            return
        if not self._authorized():
            self._send(401, {"error": "pairing required"})
            return
        if path == "/guide/v1/status":
            self._send(200, {
                "protocol": PROTOCOL_VERSION,
                "ready": True,
                "active_decks": self.server.state.session_count(),
            })
        elif path == "/guide/v1/capabilities":
            self._send(200, {"capabilities": self.server.state.capabilities()})
        elif path == "/guide/v1/android/status":
            self._send(200, self.server.state.android.status())
        elif path == "/guide/v1/applications":
            applications = self.server.state.applications.profiles()
            self._send(200, {"items": applications, "count": len(applications)})
        elif path.startswith("/guide/v1/application-sessions/") and path.endswith("/stream"):
            session_id = path.split("/")[-2]
            client_id = self.server.state.session_client(self._token())[0]
            command = self.server.state.applications.stream_command(session_id, client_id)
            if command is None:
                self._send(409, {"error": "application stream is not ready"})
            else:
                self._send_application_stream(command)
        elif path.startswith("/guide/v1/application-sessions/"):
            session_id = path.rsplit("/", 1)[-1]
            client_id = self.server.state.session_client(self._token())[0]
            session = self.server.state.applications.session(session_id, client_id)
            if session is None:
                self._send(404, {"error": "application session not found"})
            else:
                self._send(200, session)
        elif path == "/guide/v1/media":
            items = self.server.state.media_listing()
            query = parse_qs(urlsplit(self.path).query)
            try:
                offset = max(0, int(query.get("offset", ["0"])[0]))
                limit = min(200, max(1, int(query.get("limit", ["100"])[0])))
            except ValueError:
                self._send(400, {"error": "invalid media page"})
                return
            self._send(200, {
                "items": items[offset:offset + limit],
                "count": len(items),
                "offset": offset,
            })
        elif path.startswith("/guide/v1/media/"):
            self._send_media(path.rsplit("/", 1)[-1], send_body=True)
        else:
            self._send(404, {"error": "not found"})

    def _send_application_stream(self, command: list[str]) -> None:
        process = None
        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(60)
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp2t")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if process.stdout is not None:
                while True:
                    block = process.stdout.read(64 * 1024)
                    if not block:
                        break
                    self.wfile.write(block)
        except (OSError, ConnectionError):
            return
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            try:
                self.connection.settimeout(previous_timeout)
            except OSError:
                pass

    def do_HEAD(self) -> None:
        if not self._local_peer():
            self._send(403, {"error": "local network only"})
            return
        path = self._path()
        if path.startswith("/guide/v1/play/"):
            ticket = path.rsplit("/", 1)[-1]
            record = self.server.state.resolve_media_ticket(ticket)
            if record is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._send_media_record(record, send_body=False)
            return
        if not self._authorized():
            self._send(401, {"error": "pairing required"})
            return
        if path.startswith("/guide/v1/media/"):
            self._send_media(path.rsplit("/", 1)[-1], send_body=False)
        else:
            self._send(404, {"error": "not found"})

    def _send_media(self, media_id: str, send_body: bool) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", media_id):
            self._send(404, {"error": "media not found"})
            return
        record = self.server.state.playback_media(media_id)
        if record is None:
            self._send(404, {"error": "media unavailable or changed; rescan the folder"})
            return
        self._send_media_record(record, send_body)

    def _send_media_record(self, record, send_body: bool) -> None:
        requested = self.headers.get("Range")
        selected = parse_byte_range(requested, record.size) if requested else None
        if requested and selected is None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{record.size}")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        start, end = selected if selected else (0, max(0, record.size - 1))
        length = 0 if record.size == 0 else end - start + 1
        self.send_response(206 if selected else 200)
        self.send_header("Content-Type", record.content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if selected:
            self.send_header("Content-Range", f"bytes {start}-{end}/{record.size}")
        self.end_headers()
        if not send_body or length == 0:
            return
        remaining = length
        previous_timeout = self.connection.gettimeout()
        try:
            # Media is deliberately paced by the Deck. Its decoder may stop reading
            # for more than the five-second API timeout while decoding or paused.
            self.connection.settimeout(MEDIA_STREAM_TIMEOUT_SECONDS)
            with record.path.open("rb") as source:
                source.seek(start)
                while remaining:
                    block = source.read(min(256 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (OSError, ConnectionError):
            return
        finally:
            self.connection.settimeout(previous_timeout)

    def do_POST(self) -> None:
        if not self._local_peer():
            self._send(403, {"error": "local network only"})
            return
        path = self._path()
        if path == "/guide/v1/pair":
            request = self._read_json()
            if request is None:
                self._send(400, {"error": "invalid request"})
                return
            result = self.server.state.pair(
                self.client_address[0],
                str(request.get("code", "")),
                str(request.get("client_name", "")),
                str(request.get("client_id", "")),
            )
            if not result.ok:
                self._send(403, {"error": result.reason})
                return
            self._send(200, {
                "protocol": PROTOCOL_VERSION,
                "token": result.token,
                "expires_at": result.expires_at,
                "capabilities": self.server.state.capabilities(),
            })
            return
        if path == "/guide/v1/reconnect":
            request = self._read_json()
            if request is None:
                self._send(400, {"error": "invalid request"})
                return
            result = self.server.state.reconnect(
                str(request.get("client_id", "")),
                str(request.get("secret", "")),
                str(request.get("client_name", "")),
            )
            if not result.ok:
                self._send(403, {"error": result.reason})
                return
            self._send(200, {
                "protocol": PROTOCOL_VERSION,
                "token": result.token,
                "expires_at": result.expires_at,
                "trusted": True,
                "capabilities": self.server.state.capabilities(),
            })
            return
        if not self._authorized():
            self._send(401, {"error": "pairing required"})
            return
        if path == "/guide/v1/unpair":
            self.server.state.unpair(self._token())
            self._send(200, {"unpaired": True})
        elif path == "/guide/v1/trust":
            trusted = self.server.state.trust_session(self._token())
            if trusted is None:
                self._send(403, {"error": "approve this trust request on the Node first"})
            else:
                client_id, secret = trusted
                self._send(200, {"trusted": True, "client_id": client_id, "secret": secret})
        elif path == "/guide/v1/trust/revoke":
            token = self._token()
            client_id = self.server.state.session_identity(token)
            revoked = bool(client_id) and self.server.state.revoke_trust(client_id)
            self._send(200, {"trusted": False, "revoked": revoked})
        elif re.fullmatch(r"/guide/v1/media/[0-9a-f]{32}/subtitles/[0-7]/ticket", path):
            parts = path.split("/")
            media_id, track = parts[-4], int(parts[-2])
            issued = self.server.state.issue_media_ticket(self._token(), media_id, track)
            if issued is None:
                self._send(404, {"error": "subtitle unavailable or could not be prepared"})
            else:
                ticket, expiry = issued
                self._send(200, {"path": "/guide/v1/play/" + ticket,
                                 "expires_at": expiry})
        elif path.startswith("/guide/v1/media/") and path.endswith("/ticket"):
            parts = path.split("/")
            media_id = parts[-2] if len(parts) >= 2 else ""
            issued = self.server.state.issue_media_ticket(self._token(), media_id)
            if issued is None:
                self._send(404, {"error": "media unavailable or changed; rescan the folder"})
            else:
                ticket, expiry = issued
                self._send(200, {
                    "path": "/guide/v1/play/" + ticket,
                    "expires_at": expiry,
                })
        elif path.startswith("/guide/v1/applications/") and path.endswith("/sessions"):
            request = self._read_json()
            if request is None:
                self._send(400, {"error": "invalid request"})
                return
            app_id = path.split("/")[-2]
            client_id, client_name = self.server.state.session_client(self._token())
            session = self.server.state.applications.request(app_id, client_id, client_name)
            if session is None:
                self._send(404, {"error": "application is unavailable"})
            else:
                self._send(202, session)
        elif path.startswith("/guide/v1/application-sessions/") and path.endswith("/close"):
            session_id = path.split("/")[-2]
            client_id = self.server.state.session_client(self._token())[0]
            closed = self.server.state.applications.close_session(session_id, client_id)
            self._send(200 if closed else 404, {"closed": closed})
        elif path.startswith("/guide/v1/application-sessions/") and path.endswith("/input"):
            # Input injection is deliberately withheld until it has its own bounded,
            # independently tested adapter. A session never grants desktop control.
            self._send(501, {"error": "application input adapter is not installed"})
        else:
            self._send(404, {"error": "not found"})


class DiscoveryResponder:
    def __init__(self, state: NodeState, address: str, http_port: int, port: int) -> None:
        self.state = state
        self.address = address
        self.http_port = http_port
        self.port = port
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(0.5)
        except OSError:
            sock.close()
            raise
        self._socket = sock
        self._thread = threading.Thread(target=self._run, name="guide-discovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._socket:
            self._socket.close()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        sock = self._socket
        if sock is None:
            return
        while not self._stop.is_set():
            try:
                data, peer = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if data != DISCOVERY_REQUEST or not is_local_address(peer[0]):
                continue
            payload = self.state.public_description()
            payload["address"] = f"http://{self.address}:{self.http_port}"
            try:
                sock.sendto(json.dumps(payload, separators=(",", ":")).encode("utf-8"), peer)
            except OSError:
                continue


class NodeRuntime:
    def __init__(self, state: NodeState, http_port: int = DEFAULT_HTTP_PORT,
                 discovery_port: int = DEFAULT_DISCOVERY_PORT) -> None:
        self.state = state
        self.address = local_ip_address()
        self.http_port = http_port
        self.discovery_port = discovery_port
        self._http: GuideHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._discovery: DiscoveryResponder | None = None

    @property
    def running(self) -> bool:
        return self._http is not None

    def start(self) -> None:
        if self.running:
            return
        self._http = GuideHTTPServer(("0.0.0.0", self.http_port), self.state)
        self._http_thread = threading.Thread(target=self._http.serve_forever,
                                             name="guide-http", daemon=True)
        self._http_thread.start()
        try:
            self._discovery = DiscoveryResponder(
                self.state, self.address, self.http_port, self.discovery_port
            )
            self._discovery.start()
        except OSError:
            self._http.shutdown()
            self._http.server_close()
            self._http = None
            if self._http_thread:
                self._http_thread.join(timeout=3)
                self._http_thread = None
            self._discovery = None
            raise

    def stop(self) -> None:
        self.state.revoke_all()
        if self._discovery:
            self._discovery.stop()
            self._discovery = None
        if self._http:
            self._http.shutdown()
            self._http.server_close()
            self._http = None
        if self._http_thread:
            self._http_thread.join(timeout=3)
            self._http_thread = None
