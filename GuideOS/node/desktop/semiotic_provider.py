"""Optional, separately configured connector to a local Semiotic Engine."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
import urllib.error
import urllib.request


PROTOCOL = "guide-se/0"
MAX_RESPONSE_BYTES = 64 * 1024


def default_connection_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "GuideSemioticEngine" / "connection.json"


class SemioticProvider:
    """Relay bounded jobs without sharing the Engine credential with a Deck."""

    def __init__(self, enabled: bool = False, connection_path: Path | None = None) -> None:
        self.enabled = bool(enabled)
        self.connection_path = connection_path or default_connection_path()
        self._lock = threading.RLock()
        self._jobs: dict[str, tuple[str, str, str, float]] = {}

    def _connection(self) -> tuple[str, str] | None:
        if not self.enabled:
            return None
        try:
            value = json.loads(self.connection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
            return None
        url, token = value.get("url"), value.get("token")
        if (not isinstance(url, str) or not re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}", url)
                or not isinstance(token, str) or len(token) < 32):
            return None
        return url, token

    def _call(self, method: str, path: str, body: dict | None = None,
              authorized: bool = True) -> tuple[int, dict]:
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Semiotic Engine is not enabled or has no local connection record")
        base, token = connection
        data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ConnectionError("Semiotic Engine returned an oversized response")
                return response.status, json.loads(raw)
        except urllib.error.HTTPError as error:
            raw = error.read(MAX_RESPONSE_BYTES + 1)
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = {"error": "Semiotic Engine returned an invalid error"}
            return error.code, value
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ConnectionError("Semiotic Engine did not answer correctly") from error

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"available": False, "state": "not-enabled",
                    "reason": "owner has not enabled the Semiotic Engine provider"}
        try:
            status, value = self._call("GET", "/semiotic/v0/about", authorized=False)
        except ConnectionError as error:
            return {"available": False, "state": "offline", "reason": str(error)}
        valid = (status == 200 and value.get("protocol") == PROTOCOL and
                 isinstance(value.get("capabilities"), list))
        if not valid:
            return {"available": False, "state": "incompatible",
                    "reason": "local service does not speak Semiotic Engine Protocol 0"}
        return {"available": True, "state": "ready", "reason": "",
                "implementation": str(value.get("implementation", "unknown"))[:80],
                "capabilities": [str(item)[:64] for item in value["capabilities"][:16]]}

    @staticmethod
    def _request(value: object) -> dict:
        if not isinstance(value, dict) or not set(value) <= {
                "text", "instruction", "source_label", "max_output_chars", "deadline_ms"}:
            raise ValueError("request has unknown fields")
        text = value.get("text")
        if not isinstance(text, str) or not 1 <= len(text) <= 32_000:
            raise ValueError("select between 1 and 32,000 characters of text")
        instruction = value.get("instruction", "Summarize the supplied text.")
        source = value.get("source_label", "Deck selection")
        maximum = value.get("max_output_chars", 2_000)
        deadline = value.get("deadline_ms", 300_000)
        if not isinstance(instruction, str) or not 1 <= len(instruction) <= 1_000:
            raise ValueError("instruction is invalid")
        if not isinstance(source, str) or not 1 <= len(source) <= 120:
            raise ValueError("source label is invalid")
        if type(maximum) is not int or not 1 <= maximum <= 4_000:
            raise ValueError("output limit is invalid")
        if type(deadline) is not int or not 1 <= deadline <= 300_000:
            raise ValueError("deadline is invalid")
        return {
            "protocol": PROTOCOL,
            "request_id": secrets.token_hex(16),
            "task": {"kind": "text.summarize", "instruction": instruction,
                     "output_format": "guide-summary/0"},
            "context": [{"id": "deck-selection", "media_type": "text/plain",
                         "content": text, "source": {"label": source}}],
            "limits": {"deadline_ms": deadline, "max_output_chars": maximum,
                       "retention": "none"},
            "policy": {"tools": False, "network": False, "additional_context": False},
        }

    def submit(self, owner: str, value: object) -> dict:
        request = self._request(value)
        status, result = self._call("POST", "/semiotic/v0/jobs", request)
        inner = result.get("job_id")
        if status != 202 or not isinstance(inner, str) or not re.fullmatch(r"[0-9a-f]{32}", inner):
            raise ConnectionError(str(result.get("error", "Semiotic Engine rejected the request")))
        public = secrets.token_hex(16)
        with self._lock:
            self._jobs[public] = (inner, owner, request["request_id"], time.monotonic() + 900)
        return {"protocol": PROTOCOL, "job_id": public, "state": str(result.get("state", "queued"))}

    def _owned(self, public_id: str, owner: str) -> tuple[str, str] | None:
        with self._lock:
            now = time.monotonic()
            self._jobs = {key: record for key, record in self._jobs.items() if record[3] > now}
            record = self._jobs.get(public_id)
            if not record or not secrets.compare_digest(record[1], owner):
                return None
            return record[0], record[2]

    def get(self, public_id: str, owner: str) -> dict | None:
        owned = self._owned(public_id, owner)
        if owned is None:
            return None
        status, result = self._call("GET", "/semiotic/v0/jobs/" + owned[0])
        if status != 200 or result.get("request_id") != owned[1]:
            raise ConnectionError("Semiotic Engine returned the wrong job")
        safe = {"protocol": PROTOCOL, "job_id": public_id,
                "state": str(result.get("state", "failed"))}
        if safe["state"] == "complete":
            response = result.get("result")
            if (not isinstance(response, dict) or response.get("format") != "guide-summary/0"
                    or not isinstance(response.get("text"), str)
                    or len(response["text"]) > 4_000
                    or result.get("proposed_actions") != []):
                raise ConnectionError("Semiotic Engine returned an invalid completed response")
            safe.update({"result": response, "uncertainty": str(result.get("uncertainty", ""))[:500],
                         "provenance": ["deck-selection"], "proposed_actions": []})
        elif safe["state"] in {"failed", "cancelled"}:
            safe["error"] = str(result.get("error", safe["state"]))[:300]
        elif safe["state"] not in {"queued", "running"}:
            raise ConnectionError("Semiotic Engine returned an unknown job state")
        return safe

    def cancel(self, public_id: str, owner: str) -> dict | None:
        owned = self._owned(public_id, owner)
        if owned is None:
            return None
        self._call("DELETE", "/semiotic/v0/jobs/" + owned[0])
        return {"protocol": PROTOCOL, "job_id": public_id, "cancellation_requested": True}
