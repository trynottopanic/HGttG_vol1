"""Bounded Deck-side client for Guide Node discovery and pairing."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request


DISCOVERY_PORT = 4365
DISCOVERY_REQUEST = b"GUIDE-DISCOVER/1\n"
MAX_RESPONSE_BYTES = 64 * 1024


class NodeLinkError(RuntimeError):
    pass


def _local_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def validate_node_description(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NodeLinkError("NODE SENT AN INVALID DESCRIPTION")
    if value.get("protocol") != "guide-node/1":
        raise NodeLinkError("NODE USES AN UNSUPPORTED GUIDE VERSION")
    name = value.get("name")
    node_id = value.get("node_id")
    address = value.get("address")
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise NodeLinkError("NODE NAME IS INVALID")
    if not isinstance(node_id, str) or len(node_id) != 32:
        raise NodeLinkError("NODE IDENTITY IS INVALID")
    try:
        int(node_id, 16)
    except ValueError as error:
        raise NodeLinkError("NODE IDENTITY IS INVALID") from error
    if not isinstance(address, str):
        raise NodeLinkError("NODE ADDRESS IS INVALID")
    parsed = urllib.parse.urlsplit(address)
    if parsed.scheme != "http" or not parsed.hostname or not _local_ip(parsed.hostname):
        raise NodeLinkError("NODE ADDRESS IS NOT LOCAL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise NodeLinkError("NODE ADDRESS IS INVALID")
    try:
        port = parsed.port
    except ValueError as error:
        raise NodeLinkError("NODE PORT IS INVALID") from error
    if port is None or port < 1 or port > 65535:
        raise NodeLinkError("NODE PORT IS INVALID")
    clean = dict(value)
    clean["name"] = name.strip()
    clean["address"] = address.rstrip("/")
    return clean


def discover_nodes(timeout: float = 2.0) -> list[dict[str, object]]:
    """Return distinct, well-formed Node announcements seen before timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    found: dict[str, dict[str, object]] = {}
    try:
        sock.sendto(DISCOVERY_REQUEST, ("255.255.255.255", DISCOVERY_PORT))
        while True:
            try:
                data, peer = sock.recvfrom(4096)
            except socket.timeout:
                break
            if not _local_ip(peer[0]):
                continue
            try:
                description = validate_node_description(json.loads(data.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError, NodeLinkError):
                continue
            found[str(description["node_id"])] = description
    finally:
        sock.close()
    return sorted(found.values(), key=lambda item: str(item["name"]).casefold())


class NodeClient:
    def __init__(self, description: dict[str, object], timeout: float = 5.0) -> None:
        self.description = validate_node_description(description)
        self.base = str(self.description["address"])
        self.timeout = timeout
        self.token = ""

    def _request(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.headers.get_content_type() != "application/json":
                    raise NodeLinkError("NODE SENT AN UNKNOWN RESPONSE")
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            try:
                reason = json.loads(error.read(MAX_RESPONSE_BYTES).decode("utf-8")).get("error")
            except Exception:
                reason = None
            raise NodeLinkError(str(reason or "NODE REFUSED THE REQUEST").upper()[:160]) from error
        except (OSError, urllib.error.URLError) as error:
            raise NodeLinkError("NODE COULD NOT BE REACHED") from error
        if len(data) > MAX_RESPONSE_BYTES:
            raise NodeLinkError("NODE RESPONSE WAS TOO LARGE")
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise NodeLinkError("NODE SENT AN INVALID RESPONSE") from error
        if not isinstance(value, dict):
            raise NodeLinkError("NODE SENT AN INVALID RESPONSE")
        return value

    def pair(self, code: str, client_name: str = "GuideOS Deck", client_id: str = "") -> dict:
        if len(code) != 6 or not code.isdigit():
            raise NodeLinkError("PAIRING CODE MUST BE SIX NUMBERS")
        result = self._request(
            "/guide/v1/pair", "POST", {
                "code": code, "client_name": client_name[:64], "client_id": client_id,
            }
        )
        token = result.get("token")
        if not isinstance(token, str) or len(token) < 32:
            raise NodeLinkError("NODE DID NOT COMPLETE PAIRING")
        self.token = token
        return result

    def reconnect(self, client_id: str, secret: str,
                  client_name: str = "GuideOS Deck") -> dict:
        result = self._request("/guide/v1/reconnect", "POST", {
            "client_id": client_id, "secret": secret, "client_name": client_name[:64],
        })
        token = result.get("token")
        if not isinstance(token, str) or len(token) < 32:
            raise NodeLinkError("NODE DID NOT COMPLETE TRUSTED RECONNECTION")
        self.token = token
        return result

    def trust(self) -> dict:
        return self._request("/guide/v1/trust", "POST", {})

    def revoke_trust(self) -> dict:
        return self._request("/guide/v1/trust/revoke", "POST", {})

    def status(self) -> dict:
        return self._request("/guide/v1/status")

    def capabilities(self) -> dict:
        return self._request("/guide/v1/capabilities")

    def android_status(self) -> dict:
        return self._request("/guide/v1/android/status")

    def applications(self) -> dict:
        return self._request("/guide/v1/applications")

    def request_application(self, app_id: str) -> dict:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", app_id):
            raise NodeLinkError("APPLICATION ID IS INVALID")
        return self._request(f"/guide/v1/applications/{app_id}/sessions", "POST", {})

    def application_session(self, session_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", session_id):
            raise NodeLinkError("APPLICATION SESSION IS INVALID")
        return self._request(f"/guide/v1/application-sessions/{session_id}")

    def close_application(self, session_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", session_id):
            raise NodeLinkError("APPLICATION SESSION IS INVALID")
        return self._request(f"/guide/v1/application-sessions/{session_id}/close", "POST", {})

    def application_stream(self, session_id: str) -> tuple[str, str]:
        session = self.application_session(session_id)
        path = session.get("stream_path")
        expected = f"/guide/v1/application-sessions/{session_id}/stream"
        if session.get("state") != "active" or path != expected or not self.token:
            raise NodeLinkError("APPLICATION STREAM IS NOT READY")
        return self.base + expected, "Authorization: Bearer " + self.token + "\r\n"

    def media_library(self, offset: int = 0, limit: int = 100) -> dict:
        offset = max(0, int(offset))
        limit = min(200, max(1, int(limit)))
        return self._request(f"/guide/v1/media?offset={offset}&limit={limit}")

    def media_request(self, media_id: str) -> urllib.request.Request:
        if len(media_id) != 32 or any(character not in "0123456789abcdef" for character in media_id):
            raise NodeLinkError("MEDIA ID IS INVALID")
        if not self.token:
            raise NodeLinkError("PAIR WITH THE NODE FIRST")
        return urllib.request.Request(
            self.base + "/guide/v1/media/" + media_id,
            headers={"Authorization": "Bearer " + self.token},
        )

    def media_ticket(self, media_id: str) -> str:
        if len(media_id) != 32 or any(character not in "0123456789abcdef" for character in media_id):
            raise NodeLinkError("MEDIA ID IS INVALID")
        result = self._request(f"/guide/v1/media/{media_id}/ticket", "POST", {})
        path = result.get("path")
        if not isinstance(path, str) or not path.startswith("/guide/v1/play/"):
            raise NodeLinkError("NODE DID NOT CREATE A PLAYBACK TICKET")
        return self.base + path

    def media_subtitle_ticket(self, media_id: str, track: int) -> str:
        if (len(media_id) != 32 or
                any(character not in "0123456789abcdef" for character in media_id) or
                track < 0 or track > 7):
            raise NodeLinkError("SUBTITLE SELECTION IS INVALID")
        result = self._request(
            f"/guide/v1/media/{media_id}/subtitles/{track}/ticket", "POST", {})
        path = result.get("path")
        if not isinstance(path, str) or not path.startswith("/guide/v1/play/"):
            raise NodeLinkError("NODE DID NOT CREATE A SUBTITLE TICKET")
        return self.base + path

    def unpair(self) -> None:
        if self.token:
            self._request("/guide/v1/unpair", "POST", {})
            self.token = ""
