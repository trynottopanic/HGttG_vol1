"""State and policy for the lightweight Guide desktop Node."""

from __future__ import annotations

import ipaddress
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from dataclasses import dataclass
from at_field import ATField, FieldMode

from android_provider import AndroidProviderDetector
from application_provider import ApplicationProvider
from media_library import MediaLibrary, MediaRecord, default_config_path
from media_preparer import DeckMediaPreparer
from semiotic_provider import SemioticProvider
from diagnostic_commands import DiagnosticCatalog


PROTOCOL_VERSION = "guide-node/1"
DEFAULT_HTTP_PORT = 4365
DEFAULT_DISCOVERY_PORT = 4365
PAIRING_SECONDS = 10 * 60
SESSION_SECONDS = 8 * 60 * 60
MEDIA_TICKET_SECONDS = 2 * 60 * 60
MAX_PAIR_FAILURES = 8


def valid_identity(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 32:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def is_local_address(address: str) -> bool:
    """Accept addresses that cannot normally be routed across the public Internet."""
    try:
        candidate = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return candidate.is_loopback or candidate.is_private or candidate.is_link_local


@dataclass(frozen=True)
class PairingResult:
    ok: bool
    reason: str
    token: str | None = None
    expires_at: int | None = None


class NodeState:
    """Memory-only identity, pairing codes, and Deck sessions for one Node run."""

    def __init__(self, name: str = "Guide Desktop Node",
                 config_path: Path | None = None, auto_prepare: bool = False,
                 semiotic_enabled: bool | None = None,
                 semiotic_provider: SemioticProvider | None = None) -> None:
        self.name = name.strip()[:64] or "Guide Desktop Node"
        self.config_path = config_path or default_config_path()
        self.node_id = secrets.token_hex(16)
        self.started_at = int(time.time())
        self._lock = threading.RLock()
        self._tokens: dict[str, tuple[str, float, str]] = {}
        self._peer_addresses: dict[str, str] = {}
        self._failures: dict[str, int] = {}
        self._media_tickets: dict[str, tuple[str, float, str, int | None]] = {}
        self._trusted_decks: dict[str, dict[str, str]] = {}
        self._trust_armed = False
        self._semiotic_enabled = False
        # Offer introductions while the owner has selected Open.
        self._at_field = ATField(FieldMode.OPEN)
        self._load_trust()
        self.android = AndroidProviderDetector()
        self.applications = ApplicationProvider(self.config_path)
        self.media = MediaLibrary(self.config_path)
        self.media_preparer = (DeckMediaPreparer(self.config_path.parent / "media-cache")
                               if auto_prepare else None)
        if semiotic_enabled is not None:
            self._semiotic_enabled = bool(semiotic_enabled)
        self.semiotic = semiotic_provider or SemioticProvider(
            enabled=self._semiotic_enabled)
        self.prepare_media()
        self.rotate_pairing_code()

    def prepare_media(self) -> None:
        if self.media_preparer:
            self.media_preparer.synchronize(self.media.records())

    def media_listing(self) -> list[dict[str, object]]:
        ready = []
        for record in self.media.records():
            current = self.media.get(record.media_id)
            if current is None:
                continue
            prepared = self.media_preparer.prepared(current) if self.media_preparer else current
            if prepared is not None:
                ready.append(prepared)
        ready.sort(key=self.media._sort_key)
        return [record.public() for record in ready]

    def playback_media(self, media_id: str) -> MediaRecord | None:
        record = self.media.get(media_id)
        if record is None:
            return None
        return self.media_preparer.prepared(record) if self.media_preparer else record

    def playback_subtitle(self, media_id: str, track: int) -> MediaRecord | None:
        record = self.media.get(media_id)
        if record is None or self.media_preparer is None:
            return None
        return self.media_preparer.subtitle(record, track)

    def media_preparation(self) -> dict[str, object]:
        if not self.media_preparer:
            return {"queued": 0, "preparing": 0, "ready": 0, "error": 0,
                    "last_error": ""}
        return self.media_preparer.summary()

    def close(self) -> None:
        self.applications.close()
        if self.media_preparer:
            self.media_preparer.close()

    def _load_trust(self) -> None:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(value, dict):
            return
        if "at_field" in value:
            self._at_field = ATField.from_dict(value["at_field"])
        node_id = value.get("node_id")
        trusted = value.get("trusted_decks")
        semiotic_enabled = value.get("semiotic_engine_enabled")
        if valid_identity(node_id):
            self.node_id = node_id
        if isinstance(trusted, dict):
            for client_id, record in trusted.items():
                if (valid_identity(client_id) and
                        isinstance(record, dict) and
                        isinstance(record.get("name"), str) and
                        isinstance(record.get("secret_hash"), str)):
                    self._trusted_decks[client_id] = {
                        "name": record["name"][:64],
                        "secret_hash": record["secret_hash"],
                    }
        if isinstance(semiotic_enabled, bool):
            self._semiotic_enabled = semiotic_enabled

    def _save_trust(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            value = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            value = {}
        value["node_id"] = self.node_id
        value["trusted_decks"] = self._trusted_decks
        value["semiotic_engine_enabled"] = self._semiotic_enabled
        value["at_field"] = self._at_field.to_dict()
        temporary = self.config_path.with_suffix(".new")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, self.config_path)

    def set_semiotic_enabled(self, enabled: bool) -> None:
        """Persist the owner's decision to offer the optional local Engine."""
        with self._lock:
            self._semiotic_enabled = bool(enabled)
            self.semiotic.enabled = self._semiotic_enabled
            self._save_trust()

    @property
    def at_field(self) -> ATField:
        with self._lock:
            return self._at_field

    def preview_at_field(self, mode: str) -> str:
        with self._lock:
            return self._at_field.with_mode(mode).preview(self.session_count())

    def set_at_field(self, mode: str) -> None:
        """Local owner setting. Apply to future connections; retain current work."""
        with self._lock:
            previous = self._at_field
            self._at_field = previous.with_mode(mode)
            try:
                self._save_trust()
            except OSError:
                self._at_field = previous
                raise

    def set_at_field_exception(self, client_id: str, allowed: bool | None) -> None:
        """Local settings API; None removes an exception. Does not grant trust."""
        if not valid_identity(client_id) or (allowed is not None and type(allowed) is not bool):
            raise ValueError("valid peer identity and connection choice required")
        with self._lock:
            previous = self._at_field
            exceptions = dict(previous.exceptions)
            if allowed is None:
                exceptions.pop(client_id, None)
            else:
                exceptions[client_id] = allowed
            self._at_field = ATField(previous.mode, tuple(exceptions.items()))
            try:
                self._save_trust()
            except OSError:
                self._at_field = previous
                raise

    def rotate_pairing_code(self) -> str:
        with self._lock:
            self.pairing_code = f"{secrets.randbelow(1_000_000):06d}"
            self.pairing_expires = time.time() + PAIRING_SECONDS
            self._failures.clear()
            return self.pairing_code

    def pair(self, address: str, code: str, client_name: str,
             client_id: str = "") -> PairingResult:
        now = time.time()
        with self._lock:
            failures = self._failures.get(address, 0)
            if failures >= MAX_PAIR_FAILURES:
                return PairingResult(False, "pairing temporarily locked")
            if now > self.pairing_expires:
                return PairingResult(False, "pairing code expired")
            if not secrets.compare_digest(str(code), self.pairing_code):
                self._failures[address] = failures + 1
                return PairingResult(False, "pairing code rejected")

            # A valid owner-shared code supplies acceptance for Familiar mode.
            # Pairing's claimed identity is not yet a verified trusted peer;
            # exceptions apply to credential-checked reconnections instead.
            if self._at_field.connection(accepted=True) != "allow":
                return PairingResult(False, "AT Field declines new incoming connections")

            token = secrets.token_urlsafe(32)
            expiry = now + SESSION_SECONDS
            label = str(client_name).strip()[:64] or "Unnamed Deck"
            identity = client_id if valid_identity(client_id) else ""
            self._tokens[token] = (label, expiry, identity)
            self._peer_addresses[token] = address
            self._failures.pop(address, None)
            return PairingResult(True, "paired", token, int(expiry))

    def arm_trust(self, enabled: bool) -> None:
        with self._lock:
            self._trust_armed = bool(enabled)

    @property
    def trust_armed(self) -> bool:
        with self._lock:
            return self._trust_armed

    def trust_session(self, token: str) -> tuple[str, str] | None:
        with self._lock:
            record = self._tokens.get(token)
            if not record or record[1] <= time.time() or not record[2]:
                return None
            secret = secrets.token_urlsafe(32)
            previous = self._trusted_decks.get(record[2])
            self._trusted_decks[record[2]] = {
                "name": record[0],
                "secret_hash": hashlib.sha256(secret.encode("ascii")).hexdigest(),
            }
            try:
                self._save_trust()
            except OSError:
                if previous is None:
                    self._trusted_decks.pop(record[2], None)
                else:
                    self._trusted_decks[record[2]] = previous
                return None
            self._trust_armed = False
            return record[2], secret

    def reconnect(self, client_id: str, secret: str, client_name: str,
                  address: str = "") -> PairingResult:
        now = time.time()
        with self._lock:
            record = self._trusted_decks.get(client_id)
            candidate = hashlib.sha256(str(secret).encode("ascii", "ignore")).hexdigest()
            if not record or not secrets.compare_digest(candidate, record["secret_hash"]):
                return PairingResult(False, "trusted companion rejected")
            if self._at_field.connection(client_id, known=True) != "allow":
                return PairingResult(False, "AT Field declines reconnection")
            label = str(client_name).strip()[:64] or record["name"]
            record["name"] = label
            token = secrets.token_urlsafe(32)
            expiry = now + SESSION_SECONDS
            self._tokens[token] = (label, expiry, client_id)
            self._peer_addresses[token] = address
            return PairingResult(True, "trusted companion", token, int(expiry))

    def connected_decks(self) -> list[dict[str, object]]:
        """Local UI metadata for live sessions; never expose bearer credentials."""
        with self._lock:
            self.session_count()
            peers = {}
            for token, (name, expiry, identity) in self._tokens.items():
                key = identity or self._peer_addresses.get(token, name)
                peers[key] = {"id": identity, "name": name,
                              "address": self._peer_addresses.get(token, ""),
                              "remembered": identity in self._trusted_decks,
                              "expires_at": int(expiry)}
            return sorted(peers.values(), key=lambda peer: str(peer["name"]).casefold())

    def disconnect_deck(self, client_id: str, address: str = "") -> None:
        with self._lock:
            for token, record in list(self._tokens.items()):
                if (client_id and record[2] == client_id) or (not client_id and self._peer_addresses.get(token) == address):
                    self.unpair(token)

    def trusted_decks(self) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(((client_id, record["name"])
                           for client_id, record in self._trusted_decks.items()),
                          key=lambda item: item[1].casefold())

    def revoke_trust(self, client_id: str) -> bool:
        with self._lock:
            previous = self._trusted_decks.pop(client_id, None)
            removed = previous is not None
            if removed:
                try:
                    self._save_trust()
                except OSError:
                    self._trusted_decks[client_id] = previous
                    raise
                revoked_tokens = {token for token, record in self._tokens.items()
                                  if record[2] == client_id}
                for token in revoked_tokens:
                    self._tokens.pop(token, None)
                    self._peer_addresses.pop(token, None)
                self._media_tickets = {ticket: value for ticket, value in self._media_tickets.items()
                                       if value[2] not in revoked_tokens}
            return removed

    def authenticate(self, token: str) -> bool:
        now = time.time()
        with self._lock:
            record = self._tokens.get(token)
            if not record:
                return False
            if record[1] <= now:
                self._tokens.pop(token, None)
                self._peer_addresses.pop(token, None)
                return False
            return True

    def unpair(self, token: str) -> bool:
        with self._lock:
            removed = self._tokens.pop(token, None) is not None
            self._peer_addresses.pop(token, None)
            self._media_tickets = {
                ticket: value for ticket, value in self._media_tickets.items()
                if value[2] != token
            }
            return removed

    def session_identity(self, token: str) -> str:
        with self._lock:
            record = self._tokens.get(token)
            return record[2] if record and record[1] > time.time() else ""

    def session_client(self, token: str) -> tuple[str, str]:
        with self._lock:
            record = self._tokens.get(token)
            if not record or record[1] <= time.time():
                return "", ""
            # Older clients did not send a persistent identity. Their temporary
            # token still receives a distinct scope and cannot inspect another
            # legacy client's application session.
            identity = record[2] or hashlib.sha256(token.encode("ascii")).hexdigest()
            return identity, record[0]

    def revoke_all(self) -> None:
        with self._lock:
            self._tokens.clear()
            self._peer_addresses.clear()
            self._media_tickets.clear()

    def issue_media_ticket(self, token: str, media_id: str,
                           subtitle_track: int | None = None) -> tuple[str, int] | None:
        if not self.authenticate(token):
            return None
        available = (self.playback_media(media_id) if subtitle_track is None else
                     self.playback_subtitle(media_id, subtitle_track))
        if available is None:
            return None
        with self._lock:
            # One session cannot accumulate an unbounded collection of URLs.
            owned = [key for key, value in self._media_tickets.items() if value[2] == token]
            for key in owned[:-15]:
                self._media_tickets.pop(key, None)
            ticket = secrets.token_urlsafe(32)
            expiry = time.time() + MEDIA_TICKET_SECONDS
            self._media_tickets[ticket] = (media_id, expiry, token, subtitle_track)
            return ticket, int(expiry)

    def resolve_media_ticket(self, ticket: str):
        now = time.time()
        with self._lock:
            value = self._media_tickets.get(ticket)
            if not value:
                return None
            if value[1] <= now or not self.authenticate(value[2]):
                self._media_tickets.pop(ticket, None)
                return None
            media_id, subtitle_track = value[0], value[3]
        return (self.playback_media(media_id) if subtitle_track is None else
                self.playback_subtitle(media_id, subtitle_track))

    def session_count(self) -> int:
        now = time.time()
        with self._lock:
            expired = [token for token, value in self._tokens.items() if value[1] <= now]
            for token in expired:
                self._tokens.pop(token, None)
                self._peer_addresses.pop(token, None)
            return len(self._tokens)

    def public_description(self) -> dict[str, object]:
        return {
            "protocol": PROTOCOL_VERSION,
            "node_id": self.node_id,
            "name": self.name,
            "pairing_required": True,
            "transport_security": "development-local-http",
        }

    def capabilities(self) -> list[dict[str, object]]:
        android = self.android.status()
        semiotic = self.semiotic.status()
        media_count = len(self.media_listing())
        return [
            {"id": "node.status", "available": True},
            {"id": "semiotic.text", **semiotic},
            {"id": "media.library", "available": bool(self.media.folders),
             "items": media_count,
             "reason": "" if self.media.folders else "owner has not selected a media folder"},
            {"id": "android.provider", "available": False, "state": android["state"],
             "reason": android["reason"]},
            {"id": "application.sessions", "available": bool(self.applications.profiles()),
             "items": len(self.applications.profiles()),
             "streaming_ready": self.applications.streaming_available,
             "reason": "" if self.applications.profiles() else
                       "owner has not added an application"},
        ]


    def diagnostic_capabilities(self) -> list[dict[str, object]]:
        """Return only explicitly registered diagnostic operations."""
        return self.diagnostics.list()
