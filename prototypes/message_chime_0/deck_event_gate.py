#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authentication, replay prevention, and rate limiting for MESSAGE-CHIME-0."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections import deque

PROTOCOL = "third-way.event/1"
MAX_AGE_SECONDS = 120
MAX_FUTURE_SECONDS = 15


def canonical_json(event: dict) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_event(event: dict, shared_secret: bytes) -> str:
    return hmac.new(shared_secret, canonical_json(event), hashlib.sha256).hexdigest()


class EventGate:
    def __init__(self, paired_phones: dict[str, bytes], selected_person_id: str,
                 max_sounds: int = 3, interval_seconds: int = 60):
        self.paired_phones = paired_phones
        self.selected_person_id = selected_person_id
        self.max_sounds = max_sounds
        self.interval_seconds = interval_seconds
        self.seen: dict[str, int] = {}
        self.played = deque()

    def accept(self, phone_id: str, event: dict, signature: str, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        secret = self.paired_phones.get(phone_id)
        if secret is None:
            raise PermissionError("This phone is not paired with the Deck.")
        expected = sign_event(event, secret)
        if not hmac.compare_digest(expected, signature.lower()):
            raise PermissionError("The event signature is not valid.")
        if event.get("protocol") != PROTOCOL or event.get("type") != "message.received":
            raise ValueError("This is not a supported Guide event.")
        try:
            uuid.UUID(str(event["event_id"]))
            created = int(event["created_unix"])
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError("The event identity or time is invalid.") from error
        if created < now - MAX_AGE_SECONDS or created > now + MAX_FUTURE_SECONDS:
            raise ValueError("The event is stale or has an invalid future time.")
        event_id = str(event["event_id"])
        self._discard_old(now)
        if event_id in self.seen:
            raise ValueError("This event has already been handled.")
        self.seen[event_id] = created
        if event.get("person_id") != self.selected_person_id:
            return False
        while self.played and self.played[0] <= now - self.interval_seconds:
            self.played.popleft()
        if len(self.played) >= self.max_sounds:
            raise ValueError("The sound rate limit has been reached.")
        self.played.append(now)
        return True

    def _discard_old(self, now: int) -> None:
        cutoff = now - MAX_AGE_SECONDS
        self.seen = {event_id: created for event_id, created in self.seen.items() if created >= cutoff}
