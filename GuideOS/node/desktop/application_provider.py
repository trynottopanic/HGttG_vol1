"""Owner-controlled application sessions for a Guide desktop Node.

The Deck may request only applications the Node owner explicitly registered.
Approval and process launch remain local actions on the Node.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from functools import lru_cache
import re
import secrets
import shutil
import subprocess
import threading
import time


SESSION_SECONDS = 4 * 60 * 60
PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
SESSION_ID = re.compile(r"[0-9a-f]{32}")


def _label(value: object, limit: int = 64) -> str:
    text = " ".join(str(value).replace("\x00", "").split())
    return text[:limit]


@lru_cache(maxsize=1)
def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
    try:
        matches = sorted(packages.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
    except OSError:
        return None
    return str(matches[-1]) if matches else None


class ApplicationProvider:
    """Configured applications and short-lived, explicitly approved sessions."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, str]] = {}
        self._sessions: dict[str, dict[str, object]] = {}
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._load()

    @property
    def streaming_available(self) -> bool:
        return os.name == "nt" and _ffmpeg() is not None

    def _load(self) -> None:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        applications = value.get("applications") if isinstance(value, dict) else None
        if not isinstance(applications, list):
            return
        for record in applications[:64]:
            if not isinstance(record, dict):
                continue
            app_id = record.get("id")
            executable = record.get("executable")
            if (isinstance(app_id, str) and PROFILE_ID.fullmatch(app_id) and
                    isinstance(executable, str) and Path(executable).is_absolute()):
                self._profiles[app_id] = {
                    "id": app_id,
                    "name": _label(record.get("name", app_id)),
                    "executable": executable,
                    "window_title": _label(record.get("window_title", ""), 120),
                }

    def _save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            value = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            value = {}
        value["applications"] = list(self._profiles.values())
        temporary = self.config_path.with_suffix(".applications.new")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, self.config_path)

    @staticmethod
    def _make_id(name: str, existing: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:40] or "application"
        candidate = base
        number = 2
        while candidate in existing:
            suffix = f"-{number}"
            candidate = base[:48 - len(suffix)] + suffix
            number += 1
        return candidate

    def add(self, executable: Path, name: str = "", window_title: str = "") -> dict[str, object]:
        path = executable.expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.casefold() != ".exe":
            raise ValueError("choose a Windows application (.exe)")
        label = _label(name or path.stem)
        with self._lock:
            app_id = self._make_id(label, set(self._profiles))
            self._profiles[app_id] = {
                "id": app_id, "name": label, "executable": str(path),
                "window_title": _label(window_title or label, 120),
            }
            self._save()
            return self._public_profile(self._profiles[app_id])

    def remove(self, app_id: str) -> bool:
        with self._lock:
            if any(value["app_id"] == app_id and value["state"] in ("pending", "active")
                   for value in self._sessions.values()):
                return False
            removed = self._profiles.pop(app_id, None) is not None
            if removed:
                self._save()
            return removed

    def _public_profile(self, profile: dict[str, str]) -> dict[str, object]:
        path = Path(profile["executable"])
        return {
            "id": profile["id"], "name": profile["name"],
            "available": path.is_file(),
            "streaming_ready": self.streaming_available,
        }

    def profiles(self) -> list[dict[str, object]]:
        with self._lock:
            return [self._public_profile(value) for value in
                    sorted(self._profiles.values(), key=lambda item: item["name"].casefold())]

    def request(self, app_id: str, client_id: str, client_name: str) -> dict[str, object] | None:
        with self._lock:
            self._expire()
            profile = self._profiles.get(app_id)
            if not profile or not Path(profile["executable"]).is_file():
                return None
            for existing in self._sessions.values():
                if (existing["client_id"] == client_id and existing["app_id"] == app_id and
                        existing["state"] in ("pending", "active")):
                    return self._public_session(existing)
            live = [value for value in self._sessions.values()
                    if value["state"] in ("pending", "active")]
            if len(live) >= 16:
                return None
            if len(self._sessions) >= 128:
                removable = [key for key, value in self._sessions.items()
                             if value["state"] in ("closed", "denied")]
                for key in removable[:len(self._sessions) - 127]:
                    self._sessions.pop(key, None)
            session_id = secrets.token_hex(16)
            self._sessions[session_id] = {
                "id": session_id, "app_id": app_id, "application": profile["name"],
                "client_id": client_id, "client_name": _label(client_name) or "Deck",
                "state": "pending", "created_at": int(time.time()),
                "expires_at": int(time.time() + SESSION_SECONDS), "reason": "",
            }
            return self._public_session(self._sessions[session_id])

    @staticmethod
    def _public_session(session: dict[str, object]) -> dict[str, object]:
        public = {key: session[key] for key in
                  ("id", "app_id", "application", "client_name", "state", "expires_at", "reason")}
        if session["state"] == "active":
            public["stream_path"] = f"/guide/v1/application-sessions/{session['id']}/stream"
            public["video"] = {"format": "mpegts", "codec": "h264", "width": 640, "height": 480}
        return public

    def pending(self) -> list[dict[str, object]]:
        with self._lock:
            self._expire()
            return [self._public_session(value) for value in self._sessions.values()
                    if value["state"] == "pending"]

    def decide(self, session_id: str, approved: bool) -> dict[str, object] | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session["state"] != "pending":
                return None
            if not approved:
                session["state"] = "denied"
                session["reason"] = "the Node owner declined the request"
                return self._public_session(session)
            profile = self._profiles.get(str(session["app_id"]))
            if not profile:
                session["state"] = "closed"
                session["reason"] = "application was removed"
                return self._public_session(session)
            if not self.streaming_available:
                session["state"] = "closed"
                session["reason"] = "FFmpeg is not installed on the Node"
                return self._public_session(session)
            try:
                process = subprocess.Popen([profile["executable"]], shell=False,
                                           stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
            except OSError as error:
                session["state"] = "closed"
                session["reason"] = _label(error, 120)
                return self._public_session(session)
            self._processes[session_id] = process
            session["state"] = "active"
            return self._public_session(session)

    def session(self, session_id: str, client_id: str) -> dict[str, object] | None:
        if not SESSION_ID.fullmatch(session_id):
            return None
        with self._lock:
            self._expire()
            session = self._sessions.get(session_id)
            if not session or session["client_id"] != client_id:
                return None
            return self._public_session(session)

    def stream_command(self, session_id: str, client_id: str) -> list[str] | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if (not session or session["client_id"] != client_id or
                    session["state"] != "active" or not self.streaming_available):
                return None
            profile = self._profiles.get(str(session["app_id"]))
            if not profile:
                return None
            ffmpeg = _ffmpeg()
            if not ffmpeg:
                return None
            return [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "gdigrab", "-framerate", "30", "-i", "title=" + profile["window_title"],
                "-vf", "scale=640:480:force_original_aspect_ratio=decrease,"
                       "pad=640:480:(ow-iw)/2:(oh-ih)/2",
                "-an", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-pix_fmt", "yuv420p", "-g", "30", "-f", "mpegts", "pipe:1",
            ]

    def close_session(self, session_id: str, client_id: str = "") -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or (client_id and session["client_id"] != client_id):
                return False
            session["state"] = "closed"
            process = self._processes.pop(session_id, None)
            if process and process.poll() is None:
                process.terminate()
            return True

    def _expire(self) -> None:
        now = time.time()
        for session_id, session in list(self._sessions.items()):
            if int(session["expires_at"]) <= now and session["state"] in ("pending", "active"):
                self.close_session(session_id)
                session["reason"] = "session expired"

    def close(self) -> None:
        with self._lock:
            for session_id in list(self._processes):
                self.close_session(session_id)
