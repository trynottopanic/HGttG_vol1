#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Third Way VISITING-SCREEN-1 consent-based local media host."""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import mimetypes
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


APP_NAME = "Third Way Temporary Node"
APP_VERSION = "0.1.0"
SSDP_ADDRESS = ("239.255.255.250", 1900)
MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
AVTRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
DEFAULT_PORT = 8765
DEFAULT_MAX_BYTES = 8 * 1024 * 1024 * 1024
PAIRING_LIFETIME = 15 * 60
MEDIA_LIFETIME = 6 * 60 * 60


@dataclass(frozen=True)
class Renderer:
    name: str
    location: str
    control_url: str
    service_type: str
    manufacturer: str = ""
    model: str = ""


@dataclass
class SharedMovie:
    path: Path | None
    display_name: str
    media_token: str
    size: int
    mime_type: str
    source_url: str | None = None
    revoke_url: str | None = None
    offer_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    uploaded_at: float = field(default_factory=time.time)

    @property
    def expires_at(self) -> float:
        return self.uploaded_at + MEDIA_LIFETIME


@dataclass
class HostState:
    temp_dir: Path
    owner_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    pair_code: str = field(default_factory=lambda: f"{secrets.randbelow(100_000_000):08d}")
    pair_expires: float = field(default_factory=lambda: time.time() + PAIRING_LIFETIME)
    movie: SharedMovie | None = None
    renderers: list[Renderer] = field(default_factory=list)
    active_renderer: Renderer | None = None
    last_message: str = "Waiting for a movie."
    lock: threading.RLock = field(default_factory=threading.RLock)

    def rotate_pairing_code(self) -> None:
        self.pair_code = f"{secrets.randbelow(100_000_000):08d}"
        self.pair_expires = time.time() + PAIRING_LIFETIME

    def pairing_is_valid(self, code: str) -> bool:
        return time.time() <= self.pair_expires and secrets.compare_digest(
            code, self.pair_code
        )

    def remove_movie(self) -> None:
        movie = self.movie
        self.movie = None
        if movie and movie.path:
            try:
                movie.path.unlink(missing_ok=True)
            except OSError:
                pass


def local_ipv4() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


def is_local_client(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def url_uses_local_address(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        return False
    return bool(addresses) and all(is_local_client(item[4][0]) for item in addresses)


def parse_ssdp_headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("iso-8859-1", errors="replace")
    headers: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").split("\n")[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return headers


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_renderer_description(location: str, body: bytes) -> Renderer | None:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return None

    device = next((item for item in root.iter() if _tag_name(item.tag) == "device"), None)
    if device is None:
        return None

    def first_text(name: str) -> str:
        for item in device.iter():
            if _tag_name(item.tag) == name and item.text:
                return item.text.strip()
        return ""

    for service in device.iter():
        if _tag_name(service.tag) != "service":
            continue
        values = {
            _tag_name(child.tag): (child.text or "").strip() for child in service
        }
        service_type = values.get("serviceType", "")
        if "AVTransport" not in service_type:
            continue
        control = urllib.parse.urljoin(location, values.get("controlURL", ""))
        if not control:
            continue
        return Renderer(
            name=first_text("friendlyName") or "Unnamed media renderer",
            location=location,
            control_url=control,
            service_type=service_type or AVTRANSPORT,
            manufacturer=first_text("manufacturer"),
            model=first_text("modelName"),
        )
    return None


def discover_renderers(timeout: float = 3.0) -> list[Renderer]:
    request = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        f"ST: {MEDIA_RENDERER}\r\n\r\n"
    ).encode("ascii")
    locations: set[str] = set()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(0.35)
    deadline = time.monotonic() + timeout
    try:
        sock.sendto(request, SSDP_ADDRESS)
        while time.monotonic() < deadline:
            try:
                payload, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            location = parse_ssdp_headers(payload).get("location")
            if location:
                locations.add(location)
    finally:
        sock.close()

    found: list[Renderer] = []
    for location in sorted(locations):
        if not url_uses_local_address(location):
            continue
        try:
            with urllib.request.urlopen(location, timeout=2.5) as response:
                renderer = parse_renderer_description(location, response.read(1_000_000))
        except (OSError, ValueError):
            continue
        if renderer and url_uses_local_address(renderer.control_url):
            found.append(renderer)
    return found


def soap_action(renderer: Renderer, action: str, inner_xml: str = "") -> None:
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<s:Body><u:{action} xmlns:u="{html.escape(renderer.service_type)}">'
        f"<InstanceID>0</InstanceID>{inner_xml}</u:{action}></s:Body></s:Envelope>"
    ).encode("utf-8")
    request = urllib.request.Request(
        renderer.control_url,
        data=envelope,
        method="POST",
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{renderer.service_type}#{action}"',
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        response.read()


def set_and_play(renderer: Renderer, media_url: str, mime_type: str) -> None:
    metadata = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="1" parentID="0" restricted="1">'
        '<dc:title>Third Way temporary movie</dc:title>'
        '<upnp:class>object.item.videoItem</upnp:class>'
        f'<res protocolInfo="http-get:*:{html.escape(mime_type)}:*">'
        f"{html.escape(media_url)}</res></item></DIDL-Lite>"
    )
    soap_action(
        renderer,
        "SetAVTransportURI",
        f"<CurrentURI>{html.escape(media_url)}</CurrentURI>"
        f"<CurrentURIMetaData>{html.escape(metadata)}</CurrentURIMetaData>",
    )
    soap_action(renderer, "Play", "<Speed>1</Speed>")


def stop_renderer(renderer: Renderer | None) -> None:
    if renderer is None:
        return
    try:
        soap_action(renderer, "Stop")
    except (OSError, ValueError):
        pass


def notify_deck_revoke(movie: SharedMovie | None) -> None:
    if movie is None or not movie.revoke_url:
        return
    try:
        request = urllib.request.Request(movie.revoke_url, data=b"", method="POST")
        with urllib.request.urlopen(request, timeout=2) as response:
            response.read()
    except (OSError, ValueError):
        pass


def parse_byte_range(value: str, size: int) -> tuple[int, int] | None:
    if not value.startswith("bytes=") or "," in value:
        return None
    spec = value[6:].strip()
    if "-" not in spec:
        return None
    start_text, end_text = spec.split("-", 1)
    try:
        if not start_text:
            length = int(end_text)
            if length <= 0:
                return None
            start = max(0, size - length)
            return start, size - 1
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)


def safe_filename(raw: str) -> str:
    name = Path(raw).name.strip().replace("\x00", "")
    return name[:180] or "movie.bin"


class ThirdWayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: HostState, max_bytes: int):
        super().__init__(address, ThirdWayHandler)
        self.state = state
        self.max_bytes = max_bytes
        self.lan_ip = local_ipv4()


class ThirdWayHandler(BaseHTTPRequestHandler):
    server: ThirdWayServer

    def log_message(self, message: str, *args: object) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), message % args))

    def _parsed(self) -> tuple[urllib.parse.SplitResult, dict[str, list[str]]]:
        parsed = urllib.parse.urlsplit(self.path)
        return parsed, urllib.parse.parse_qs(parsed.query)

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _text(self, status: int, message: str) -> None:
        self._send(status, message.encode("utf-8"))

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _owner_allowed(self, query: dict[str, list[str]]) -> bool:
        supplied = query.get("owner", [""])[0]
        return self.client_address[0] in {"127.0.0.1", "::1"} and secrets.compare_digest(
            supplied, self.server.state.owner_token
        )

    def _local_allowed(self) -> bool:
        return is_local_client(self.client_address[0])

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed, query = self._parsed()
        if parsed.path == "/health":
            self._send(
                HTTPStatus.OK,
                json.dumps({"name": APP_NAME, "version": APP_VERSION, "status": "ready"}).encode(),
                "application/json",
            )
            return
        if parsed.path == "/":
            if not self._owner_allowed(query):
                self._text(HTTPStatus.FORBIDDEN, "Owner console is available only on this computer.")
                return
            self._send(HTTPStatus.OK, self._owner_page().encode(), "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/join/"):
            code = parsed.path.removeprefix("/join/")
            if not self._local_allowed() or not self.server.state.pairing_is_valid(code):
                self._text(HTTPStatus.FORBIDDEN, "Pairing code is invalid or expired.")
                return
            self._send(HTTPStatus.OK, self._guest_page(code).encode(), "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/media/"):
            self._serve_media(parsed.path)
            return
        self._text(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self) -> None:
        parsed, query = self._parsed()
        if parsed.path == "/api/upload":
            self._upload(query)
            return
        if parsed.path == "/api/offer":
            self._offer(query)
            return
        if parsed.path == "/api/withdraw":
            self._withdraw(query)
            return
        if parsed.path == "/api/discover":
            self._discover(query)
            return
        if parsed.path == "/api/play":
            self._play(query)
            return
        if parsed.path == "/api/revoke":
            self._revoke(query)
            return
        self._text(HTTPStatus.NOT_FOUND, "Not found.")

    def _guest_page(self, code: str) -> str:
        return f"""<!doctype html><meta name=viewport content='width=device-width'>
<title>Third Way - Offer a movie</title>
<style>{PAGE_STYLE}</style><main><h1>Offer one movie</h1>
<p>The store owner must approve the destination before playback. The file stays
on this local network and is removed when the host revokes it or closes.</p>
<input id=file type=file accept='video/*'><button id=send>Send to owner</button>
<p id=status>No file selected.</p></main><script>
const button=document.querySelector('#send'), status=document.querySelector('#status');
button.onclick=async()=>{{const file=document.querySelector('#file').files[0];
if(!file){{status.textContent='Choose a movie first.';return;}}
button.disabled=true;status.textContent='Sending '+file.name+'...';
try{{const response=await fetch('/api/upload?code={urllib.parse.quote(code)}&filename='+encodeURIComponent(file.name),
{{method:'POST',headers:{{'Content-Type':file.type||'application/octet-stream'}},body:file}});
status.textContent=await response.text();}}catch(error){{status.textContent='Transfer failed: '+error;}}
button.disabled=false;}};</script>"""

    def _owner_page(self) -> str:
        state = self.server.state
        with state.lock:
            movie = state.movie
            renderers = list(state.renderers)
            message = state.last_message
            pair_valid = time.time() <= state.pair_expires
        owner = urllib.parse.quote(state.owner_token)
        join_url = f"http://{self.server.lan_ip}:{self.server.server_port}/join/{state.pair_code}"
        movie_text = (
            f"<strong>{html.escape(movie.display_name)}</strong> "
            f"({movie.size / 1048576:.1f} MiB; "
            f"{'served directly by the Deck' if movie.source_url else 'temporarily copied to this host'})"
            if movie and (movie.source_url or (movie.path and movie.path.exists()))
            else "No movie is waiting."
        )
        choices = "".join(
            f"<button name=renderer value='{index}'>Play on {html.escape(item.name)}"
            f"{(' — ' + html.escape(item.model)) if item.model else ''}</button>"
            for index, item in enumerate(renderers)
        ) or "<p>No compatible UPnP/DLNA television has been discovered.</p>"
        return f"""<!doctype html><meta name=viewport content='width=device-width'>
<title>Third Way Temporary Node</title><style>{PAGE_STYLE}</style><main>
<h1>Third Way Temporary Node</h1><p class=message>{html.escape(message)}</p>
<h2>Pair a visitor</h2><p>Give the visitor this local address. It expires in
{'under 15 minutes' if pair_valid else '0 minutes'}:</p><code>{html.escape(join_url)}</code>
<h2>Movie awaiting consent</h2><p>{movie_text}</p>
<form method=post action='/api/discover?owner={owner}'><button>Search for TVs</button></form>
<h2>Compatible TVs</h2><form method=post action='/api/play?owner={owner}'>{choices}</form>
<form method=post action='/api/revoke?owner={owner}'><button class=danger>Stop and revoke</button></form>
<p class=small>Playback works only when the TV advertises a compatible AVTransport
service and supports the movie's format. Discovery is not proof of decoding support.</p>
</main>"""

    def _upload(self, query: dict[str, list[str]]) -> None:
        state = self.server.state
        code = query.get("code", [""])[0]
        if not self._local_allowed() or not state.pairing_is_valid(code):
            self._text(HTTPStatus.FORBIDDEN, "Pairing code is invalid or expired.")
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length <= 0:
            self._text(HTTPStatus.LENGTH_REQUIRED, "The movie size was not provided.")
            return
        if length > self.server.max_bytes:
            self._text(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The movie exceeds this host's limit.")
            return
        name = safe_filename(query.get("filename", ["movie.bin"])[0])
        suffix = Path(name).suffix[:16]
        destination = state.temp_dir / f"offered-{secrets.token_hex(8)}{suffix}"
        remaining = length
        try:
            with destination.open("xb") as output:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise OSError("transfer ended early")
                    output.write(chunk)
                    remaining -= len(chunk)
        except OSError as error:
            destination.unlink(missing_ok=True)
            self._text(HTTPStatus.BAD_REQUEST, f"Transfer failed: {error}")
            return
        with state.lock:
            stop_renderer(state.active_renderer)
            notify_deck_revoke(state.movie)
            state.active_renderer = None
            state.remove_movie()
            state.movie = SharedMovie(
                destination,
                name,
                secrets.token_urlsafe(24),
                length,
                self.headers.get("Content-Type", "application/octet-stream"),
            )
            state.rotate_pairing_code()
            state.last_message = f"Received {name}; waiting for owner approval."
        self._text(HTTPStatus.CREATED, "Movie received. Waiting for the owner's approval.")

    def _offer(self, query: dict[str, list[str]]) -> None:
        state = self.server.state
        code = query.get("code", [""])[0]
        if not self._local_allowed() or not state.pairing_is_valid(code):
            self._text(HTTPStatus.FORBIDDEN, "Pairing code is invalid or expired.")
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 < length <= 16_384:
            self._text(HTTPStatus.BAD_REQUEST, "Offer description is missing or too large.")
            return
        try:
            offer = json.loads(self.rfile.read(length))
            name = safe_filename(str(offer["name"]))
            size = int(offer["size"])
            source_url = str(offer["url"])
            revoke_url = str(offer["revoke_url"])
            mime_type = str(offer.get("mime_type") or "application/octet-stream")[:128]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._text(HTTPStatus.BAD_REQUEST, "Offer description is invalid.")
            return
        if size <= 0 or size > self.server.max_bytes:
            self._text(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The movie exceeds this host's limit.")
            return
        if not url_uses_local_address(source_url) or not url_uses_local_address(revoke_url):
            self._text(HTTPStatus.BAD_REQUEST, "The Deck endpoints are not on this local network.")
            return
        with state.lock:
            stop_renderer(state.active_renderer)
            notify_deck_revoke(state.movie)
            state.active_renderer = None
            state.remove_movie()
            state.movie = SharedMovie(
                None,
                name,
                "",
                size,
                mime_type,
                source_url=source_url,
                revoke_url=revoke_url,
            )
            offer_token = state.movie.offer_token
            state.rotate_pairing_code()
            state.last_message = f"Deck offered {name}; waiting for owner approval."
        self._send(
            HTTPStatus.CREATED,
            json.dumps({"status": "waiting_for_owner", "offer_token": offer_token}).encode(),
            "application/json",
        )

    def _withdraw(self, query: dict[str, list[str]]) -> None:
        if not self._local_allowed():
            self._text(HTTPStatus.FORBIDDEN, "Local-network access only.")
            return
        supplied = query.get("offer", [""])[0]
        state = self.server.state
        with state.lock:
            movie = state.movie
            if not movie or not secrets.compare_digest(supplied, movie.offer_token):
                self._text(HTTPStatus.FORBIDDEN, "Offer authorization failed.")
                return
            stop_renderer(state.active_renderer)
            state.active_renderer = None
            state.remove_movie()
            state.last_message = "The Deck withdrew its movie offer."
        self._text(HTTPStatus.OK, "Offer withdrawn.")

    def _discover(self, query: dict[str, list[str]]) -> None:
        if not self._owner_allowed(query):
            self._text(HTTPStatus.FORBIDDEN, "Owner authorization failed.")
            return
        found = discover_renderers()
        with self.server.state.lock:
            self.server.state.renderers = found
            self.server.state.last_message = (
                f"Found {len(found)} compatible media renderer(s)."
                if found
                else "No compatible UPnP/DLNA media renderer answered."
            )
        self._redirect(f"/?owner={urllib.parse.quote(self.server.state.owner_token)}")

    def _play(self, query: dict[str, list[str]]) -> None:
        if not self._owner_allowed(query):
            self._text(HTTPStatus.FORBIDDEN, "Owner authorization failed.")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(min(length, 8192)).decode("utf-8", errors="replace")
        form = urllib.parse.parse_qs(body)
        try:
            index = int(form.get("renderer", ["-1"])[0])
        except ValueError:
            index = -1
        state = self.server.state
        with state.lock:
            movie = state.movie
            renderer = state.renderers[index] if 0 <= index < len(state.renderers) else None
        if not movie or not (movie.source_url or (movie.path and movie.path.exists())):
            state.last_message = "Playback was not attempted: no movie is waiting."
        elif renderer is None:
            state.last_message = "Playback was not attempted: choose a discovered TV."
        else:
            quoted = urllib.parse.quote(movie.display_name)
            media_url = movie.source_url or (
                f"http://{self.server.lan_ip}:{self.server.server_port}/media/"
                f"{movie.media_token}/{quoted}"
            )
            try:
                set_and_play(renderer, media_url, movie.mime_type)
                with state.lock:
                    state.active_renderer = renderer
                    state.last_message = f"Playback request accepted by {renderer.name}."
            except Exception as error:  # Report device/network failures without claiming success.
                state.last_message = f"TV rejected or could not receive playback: {error}"
        self._redirect(f"/?owner={urllib.parse.quote(state.owner_token)}")

    def _revoke(self, query: dict[str, list[str]]) -> None:
        if not self._owner_allowed(query):
            self._text(HTTPStatus.FORBIDDEN, "Owner authorization failed.")
            return
        state = self.server.state
        with state.lock:
            stop_renderer(state.active_renderer)
            notify_deck_revoke(state.movie)
            state.active_renderer = None
            state.remove_movie()
            state.rotate_pairing_code()
            state.last_message = "Playback stopped and temporary movie access revoked."
        self._redirect(f"/?owner={urllib.parse.quote(state.owner_token)}")

    def _serve_media(self, path: str) -> None:
        if not self._local_allowed():
            self._text(HTTPStatus.FORBIDDEN, "Local-network access only.")
            return
        parts = path.split("/", 4)
        token = parts[2] if len(parts) > 2 else ""
        state = self.server.state
        with state.lock:
            movie = state.movie
        if (
            movie is None
            or movie.path is None
            or not secrets.compare_digest(token, movie.media_token)
            or time.time() > movie.expires_at
            or not movie.path.exists()
        ):
            self._text(HTTPStatus.NOT_FOUND, "Temporary movie access is unavailable.")
            return
        size = movie.path.stat().st_size
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
        self.send_header("Content-Type", movie.mime_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(movie.display_name)}")
        self.send_header("transferMode.dlna.org", "Streaming")
        self.send_header("contentFeatures.dlna.org", "DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000")
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with movie.path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


PAGE_STYLE = """
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#101416;color:#edf7f5}
main{max-width:48rem;margin:4rem auto;padding:1.5rem}h1{color:#81ffe1}h2{margin-top:2rem}
button,input{font:inherit;padding:.75rem;margin:.4rem 0}button{display:block;background:#81ffe1;
color:#07110f;border:0;border-radius:.3rem;font-weight:700}.danger{background:#ff8b8b}
code{display:block;padding:1rem;background:#20282b;overflow-wrap:anywhere}.message{padding:1rem;
border-left:.3rem solid #81ffe1;background:#182024}.small{opacity:.75;font-size:.9rem}
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="local HTTP port")
    parser.add_argument(
        "--max-gib",
        type=float,
        default=DEFAULT_MAX_BYTES / (1024**3),
        help="largest accepted movie in GiB",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open the owner page")
    return parser


def run(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.max_gib <= 0:
        raise SystemExit("--max-gib must be greater than zero")
    with tempfile.TemporaryDirectory(prefix="thirdway-host-") as temp:
        state = HostState(Path(temp))
        server = ThirdWayServer(("0.0.0.0", args.port), state, int(args.max_gib * 1024**3))
        owner_url = f"http://127.0.0.1:{server.server_port}/?owner={state.owner_token}"
        join_url = f"http://{server.lan_ip}:{server.server_port}/join/{state.pair_code}"
        print(f"{APP_NAME} {APP_VERSION}", flush=True)
        print(f"Owner console: {owner_url}", flush=True)
        print(f"Visitor pairing address: {join_url}", flush=True)
        print("Closing this window revokes access and removes the temporary movie.", flush=True)
        if not args.no_browser:
            threading.Timer(0.5, lambda: webbrowser.open(owner_url)).start()
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            print("\nRevoking temporary access...")
        finally:
            with state.lock:
                stop_renderer(state.active_renderer)
                notify_deck_revoke(state.movie)
                state.remove_movie()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
