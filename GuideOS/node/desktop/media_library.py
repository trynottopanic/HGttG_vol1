"""Owner-selected, read-only media library for a Guide Desktop Node."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import threading
from dataclasses import dataclass


MAX_MEDIA_ITEMS = 10_000
MEDIA_TYPES = {
    ".mp3": ("audio", "audio/mpeg"),
    ".m4a": ("audio", "audio/mp4"),
    ".aac": ("audio", "audio/aac"),
    ".flac": ("audio", "audio/flac"),
    ".ogg": ("audio", "audio/ogg"),
    ".opus": ("audio", "audio/ogg"),
    ".wav": ("audio", "audio/wav"),
    ".mp4": ("video", "video/mp4"),
    ".m4v": ("video", "video/mp4"),
    ".mkv": ("video", "video/x-matroska"),
    ".webm": ("video", "video/webm"),
    ".avi": ("video", "video/x-msvideo"),
    ".mov": ("video", "video/quicktime"),
}


def default_config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "GuideNode" / "config.json"
    return Path.home() / ".guide-node" / "config.json"


@dataclass(frozen=True)
class MediaRecord:
    media_id: str
    path: Path
    name: str
    relative_path: str
    kind: str
    content_type: str
    size: int
    modified_ns: int
    subtitle_tracks: tuple[str, ...] = ()

    def public(self) -> dict[str, object]:
        return {
            "id": self.media_id,
            "name": self.name,
            "folder": str(Path(self.relative_path).parent).replace("\\", "/")
                if "/" in self.relative_path or "\\" in self.relative_path else "",
            "kind": self.kind,
            "format": self.path.suffix.lower().lstrip("."),
            "size": self.size,
            "subtitles": list(self.subtitle_tracks),
        }


class MediaLibrary:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or default_config_path()
        self._lock = threading.RLock()
        self._secret = secrets.token_bytes(32)
        self._folder: Path | None = None
        self._records: dict[str, MediaRecord] = {}
        self.last_error = ""
        self._load_config()
        if self._folder:
            self.scan()

    @property
    def folder(self) -> Path | None:
        with self._lock:
            return self._folder

    def set_folder(self, value: str | Path | None) -> int:
        if value in (None, ""):
            with self._lock:
                self._folder = None
                self._records = {}
                self.last_error = ""
            self._save_config()
            return 0
        folder = Path(value).expanduser().resolve(strict=True)
        if not folder.is_dir():
            raise ValueError("Media location must be a folder")
        with self._lock:
            self._folder = folder
        self._save_config()
        return self.scan()

    def _load_config(self) -> None:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
            folder = value.get("media_folder") if isinstance(value, dict) else None
            if isinstance(folder, str) and folder:
                candidate = Path(folder).resolve(strict=True)
                if candidate.is_dir():
                    self._folder = candidate
        except (OSError, ValueError, json.JSONDecodeError):
            return

    def _save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(".new")
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            value = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            value = {}
        value["media_folder"] = str(self.folder) if self.folder else None
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, self.config_path)

    @staticmethod
    def _reparse(entry: os.DirEntry[str]) -> bool:
        try:
            information = entry.stat(follow_symlinks=False)
        except OSError:
            return True
        attributes = getattr(information, "st_file_attributes", 0)
        marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return entry.is_symlink() or bool(attributes & marker)

    def scan(self) -> int:
        with self._lock:
            root = self._folder
        if root is None:
            return 0
        records: dict[str, MediaRecord] = {}
        try:
            for current, directories, files in os.walk(root, followlinks=False):
                current_path = Path(current)
                try:
                    with os.scandir(current_path) as iterator:
                        entries = {entry.name: entry for entry in iterator}
                except OSError:
                    directories[:] = []
                    continue
                directories[:] = [
                    name for name in sorted(directories, key=str.casefold)
                    if name in entries and not self._reparse(entries[name])
                ]
                for name in sorted(files, key=str.casefold):
                    if len(records) >= MAX_MEDIA_ITEMS:
                        break
                    path = current_path / name
                    media_type = MEDIA_TYPES.get(path.suffix.lower())
                    if media_type is None:
                        continue
                    try:
                        entry = entries[name]
                        information = entry.stat(follow_symlinks=False)
                        if not stat.S_ISREG(information.st_mode):
                            continue
                        attributes = getattr(information, "st_file_attributes", 0)
                        marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                        if attributes & marker:
                            continue
                        relative = path.relative_to(root).as_posix()
                    except (KeyError, OSError, ValueError):
                        continue
                    identity = relative.encode("utf-8") + b"\0" + str(information.st_size).encode() + \
                        b"\0" + str(information.st_mtime_ns).encode()
                    media_id = hashlib.blake2s(identity, key=self._secret, digest_size=16).hexdigest()
                    records[media_id] = MediaRecord(
                        media_id, path, name[:240], relative, media_type[0], media_type[1],
                        information.st_size, information.st_mtime_ns,
                    )
                if len(records) >= MAX_MEDIA_ITEMS:
                    break
        except OSError as error:
            with self._lock:
                self.last_error = str(error)[:160]
                self._records = {}
            return 0
        with self._lock:
            self._records = records
            self.last_error = ""
        return len(records)

    def listing(self) -> list[dict[str, object]]:
        records = self.records()
        records.sort(key=lambda record: (record.kind, record.relative_path.casefold()))
        return [record.public() for record in records]

    def records(self) -> list[MediaRecord]:
        with self._lock:
            return list(self._records.values())

    def get(self, media_id: str) -> MediaRecord | None:
        with self._lock:
            record = self._records.get(media_id)
            root = self._folder
        if record is None or root is None:
            return None
        try:
            current = record.path.stat(follow_symlinks=False)
            resolved = record.path.resolve(strict=True)
            if not resolved.is_relative_to(root) or not stat.S_ISREG(current.st_mode):
                return None
            if current.st_size != record.size or current.st_mtime_ns != record.modified_ns:
                return None
            attributes = getattr(current, "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                return None
        except (OSError, ValueError):
            return None
        return record
