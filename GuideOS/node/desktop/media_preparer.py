"""Prepare conservative, cached video copies for the first GuideOS Deck."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import glob
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Callable
from urllib.parse import quote

from media_library import MediaRecord


TARGET_WIDTH = 640
TARGET_HEIGHT = 360
VIDEO_BITRATE_KBPS = 1200
AUDIO_BITRATE_KBPS = 128


def _winget_program(name: str) -> str | None:
    """Find a WinGet-installed FFmpeg even before this process sees PATH changes."""
    found = shutil.which(name)
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    links = Path(local) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
    if links.is_file():
        return str(links)
    pattern = str(Path(local) / "Microsoft" / "WinGet" / "Packages" /
                  "Gyan.FFmpeg_*" / "ffmpeg-*" / "bin" / f"{name}.exe")
    matches = sorted(glob.glob(pattern), reverse=True)
    return matches[0] if matches else None


def _subtitle_tracks(path: Path) -> tuple[str, ...]:
    ffprobe = _winget_program("ffprobe")
    if not ffprobe:
        return ()
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "s", "-show_entries",
             "stream=index:stream_tags=language,title", "-of", "json", str(path)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            creationflags=flags, check=False,
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ()
    tracks = []
    for number, stream in enumerate(payload.get("streams", [])):
        tags = stream.get("tags", {}) if isinstance(stream, dict) else {}
        language = str(tags.get("language", "")).strip().upper()
        title = str(tags.get("title", "")).strip()
        label = title or language or f"TRACK {number + 1}"
        tracks.append(" ".join(label.split())[:32])
    return tuple(tracks[:8])


def default_cache_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "GuideNode" / "media-cache"
    return Path.home() / ".guide-node" / "media-cache"


def _file_uri(path: Path) -> str:
    return "file:///" + quote(path.resolve().as_posix(), safe="/:[]()'")


class DeckMediaPreparer:
    """One bounded worker that never alters an owner's original media."""

    def __init__(self, cache_path: Path | None = None,
                 backend: Callable[[Path, Path], tuple[bool, str]] | None = None) -> None:
        self.cache_path = cache_path or default_cache_path()
        self._backend = backend
        self._lock = threading.RLock()
        self._states: dict[str, tuple[str, str]] = {}
        self._outputs: dict[str, Path] = {}
        self._subtitles: dict[str, tuple[str, ...]] = {}
        self._keys: dict[str, str] = {}
        self._queue: queue.Queue[MediaRecord | None] = queue.Queue(maxsize=10_000)
        self._stop = threading.Event()
        self._process: subprocess.Popen | None = None
        self._active_id = ""
        self._thread = threading.Thread(target=self._work, name="guide-media-preparer", daemon=True)
        self._thread.start()

    @staticmethod
    def _key(record: MediaRecord) -> str:
        identity = (str(record.path.resolve()) + "\0" + str(record.size) + "\0" +
                    str(record.modified_ns) + "\0deck-video-640x360-v2-subtitles").encode("utf-8")
        return hashlib.sha256(identity).hexdigest()

    def synchronize(self, records: list[MediaRecord]) -> None:
        current = {record.media_id for record in records if record.kind == "video"}
        cancel = None
        with self._lock:
            for media_id in list(self._states):
                if media_id not in current:
                    self._states.pop(media_id, None)
                    self._outputs.pop(media_id, None)
                    self._subtitles.pop(media_id, None)
                    self._keys.pop(media_id, None)
            for record in records:
                if record.kind != "video":
                    continue
                key = self._key(record)
                output = self.cache_path / (key + ".mp4")
                if output.is_file() and output.stat().st_size > 1024:
                    self._states[record.media_id] = ("ready", "")
                    self._outputs[record.media_id] = output
                    self._subtitles[record.media_id] = _subtitle_tracks(output)
                    self._keys[record.media_id] = key
                elif (self._keys.get(record.media_id) != key or
                      record.media_id not in self._states or
                      self._states[record.media_id][0] == "error"):
                    self._states[record.media_id] = ("queued", "")
                    self._keys[record.media_id] = key
                    self._queue.put_nowait(record)
            if self._active_id and self._active_id not in current:
                cancel = self._process
        if cancel and cancel.poll() is None:
            cancel.terminate()

    def prepared(self, record: MediaRecord) -> MediaRecord | None:
        if record.kind != "video":
            return record
        with self._lock:
            state = self._states.get(record.media_id, ("queued", ""))[0]
            output = self._outputs.get(record.media_id)
            subtitles = self._subtitles.get(record.media_id, ())
        if state != "ready" or output is None:
            return None
        try:
            information = output.stat()
            if not output.is_file() or information.st_size <= 1024:
                return None
        except OSError:
            return None
        return replace(record, path=output, content_type="video/mp4",
                       size=information.st_size, modified_ns=information.st_mtime_ns,
                       subtitle_tracks=subtitles)

    def summary(self) -> dict[str, object]:
        with self._lock:
            counts = {name: 0 for name in ("queued", "preparing", "ready", "error")}
            errors = []
            for state, detail in self._states.values():
                counts[state] = counts.get(state, 0) + 1
                if state == "error" and detail:
                    errors.append(detail)
        return {**counts, "last_error": errors[-1] if errors else ""}

    def wait_for_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            summary = self.summary()
            if not summary["queued"] and not summary["preparing"]:
                return True
            time.sleep(0.02)
        return False

    def close(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()
        self._thread.join(timeout=3)

    def _work(self) -> None:
        while not self._stop.is_set():
            try:
                record = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if record is None:
                return
            with self._lock:
                if self._states.get(record.media_id, ("", ""))[0] != "queued":
                    continue
                self._states[record.media_id] = ("preparing", "")
                self._active_id = record.media_id
            output = self.cache_path / (self._key(record) + ".mp4")
            temporary = output.with_suffix(".part.mp4")
            try:
                self.cache_path.mkdir(parents=True, exist_ok=True)
                temporary.unlink(missing_ok=True)
                okay, detail = (self._backend or self._convert)(record.path, temporary)
                if not okay or not temporary.is_file() or temporary.stat().st_size <= 1024:
                    raise OSError(detail or "The video converter did not produce a usable file")
                os.replace(temporary, output)
                with self._lock:
                    if self._keys.get(record.media_id) == self._key(record):
                        self._outputs[record.media_id] = output
                        self._subtitles[record.media_id] = _subtitle_tracks(output)
                        self._states[record.media_id] = ("ready", "")
            except OSError as error:
                temporary.unlink(missing_ok=True)
                with self._lock:
                    self._states[record.media_id] = ("error", str(error)[:180])
            finally:
                with self._lock:
                    self._active_id = ""

    def _convert(self, source: Path, destination: Path) -> tuple[bool, str]:
        ffmpeg = _winget_program("ffmpeg")
        if ffmpeg:
            arguments = [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?",
                "-map", "0:s?",
                "-vf", "scale=640:360:force_original_aspect_ratio=decrease,"
                "pad=640:360:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-profile:v", "main", "-b:v", f"{VIDEO_BITRATE_KBPS}k",
                "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_KBPS}k", "-ac", "2", "-ar", "48000",
                "-c:s", "mov_text",
                "-movflags", "+faststart", str(destination),
            ]
        else:
            program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            vlc = shutil.which("vlc") or str(program_files / "VideoLAN" / "VLC" / "vlc.exe")
            if not Path(vlc).is_file():
                return False, "Install VLC or FFmpeg to prepare videos for the Deck"
            transcode = (
                f"#transcode{{vcodec=h264,vb={VIDEO_BITRATE_KBPS},width={TARGET_WIDTH},"
                f"height={TARGET_HEIGHT},acodec=mp4a,ab={AUDIO_BITRATE_KBPS},channels=2,"
                "samplerate=48000}:std{access=file,mux=mp4,dst='" +
                str(destination).replace("'", "\\'") + "'}"
            )
            arguments = [vlc, "-I", "dummy", "--dummy-quiet", _file_uri(source),
                         "--sout", transcode, "vlc://quit"]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            with self._lock:
                self._process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL,
                                                 stdout=subprocess.DEVNULL,
                                                 stderr=subprocess.DEVNULL,
                                                 creationflags=flags)
                process = self._process
            return_code = process.wait()
        except OSError as error:
            return False, str(error)
        finally:
            with self._lock:
                self._process = None
        return return_code == 0, "Video conversion failed" if return_code else ""
