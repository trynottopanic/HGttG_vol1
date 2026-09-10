"""Owner-selected, read-only media libraries for a Guide Desktop Node."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import threading
from dataclasses import dataclass
from typing import Iterable

MAX_MEDIA_ITEMS = 10_000
MEDIA_TYPES = {
    ".mp3": ("audio", "audio/mpeg"), ".m4a": ("audio", "audio/mp4"),
    ".aac": ("audio", "audio/aac"), ".flac": ("audio", "audio/flac"),
    ".ogg": ("audio", "audio/ogg"), ".opus": ("audio", "audio/ogg"),
    ".wav": ("audio", "audio/wav"), ".mp4": ("video", "video/mp4"),
    ".m4v": ("video", "video/mp4"), ".mkv": ("video", "video/x-matroska"),
    ".webm": ("video", "video/webm"), ".avi": ("video", "video/x-msvideo"),
    ".mov": ("video", "video/quicktime"), ".mpeg": ("video", "video/mpeg"),
    ".mpg": ("video", "video/mpeg"), ".ts": ("video", "video/mp2t"),
    ".m2ts": ("video", "video/mp2t"), ".mts": ("video", "video/mp2t"),
    ".wmv": ("video", "video/x-ms-wmv"), ".3gp": ("video", "video/3gpp"),
    ".ogv": ("video", "video/ogg"), ".vob": ("video", "video/mpeg"),
    ".flv": ("video", "video/x-flv"),
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
    library: str = "Media"
    root: Path | None = None
    root_index: int = 0

    def public(self) -> dict[str, object]:
        parent = Path(self.relative_path).parent.as_posix()
        return {
            "id": self.media_id, "name": self.name, "library": self.library,
            "folder": "" if parent == "." else parent, "kind": self.kind,
            "format": self.path.suffix.lower().lstrip("."), "size": self.size,
            "subtitles": list(self.subtitle_tracks),
        }


class MediaLibrary:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or default_config_path()
        self._lock = threading.RLock()
        self._secret = secrets.token_bytes(32)
        self._folders: tuple[Path, ...] = ()
        self._records: dict[str, MediaRecord] = {}
        self.last_error = ""
        self._load_config()
        if self._folders:
            self.scan()

    @property
    def folders(self) -> tuple[Path, ...]:
        with self._lock:
            return self._folders

    @property
    def folder(self) -> Path | None:
        """Compatibility alias for callers from the one-folder prototype."""
        folders = self.folders
        return folders[0] if folders else None

    @staticmethod
    def _resolve_folders(values: Iterable[str | Path]) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for value in values:
            folder = Path(value).expanduser().resolve(strict=True)
            if not folder.is_dir():
                raise ValueError("Every media location must be a folder")
            key = os.path.normcase(str(folder))
            if key not in seen:
                result.append(folder)
                seen.add(key)
        return tuple(result)

    def set_folders(self, values: Iterable[str | Path]) -> int:
        folders = self._resolve_folders(values)
        with self._lock:
            self._folders = folders
            self._records = {}
            self.last_error = ""
        self._save_config()
        return self.scan()

    def add_folder(self, value: str | Path) -> int:
        return self.set_folders((*self.folders, value))

    def remove_folder(self, value: str | Path | int) -> int:
        folders = list(self.folders)
        if isinstance(value, int):
            if value < 0 or value >= len(folders):
                raise ValueError("Select a media folder to remove")
            del folders[value]
        else:
            target = os.path.normcase(str(Path(value).expanduser().resolve(strict=False)))
            folders = [folder for folder in folders
                       if os.path.normcase(str(folder)) != target]
        return self.set_folders(folders)

    def set_folder(self, value: str | Path | None) -> int:
        return self.set_folders(()) if value in (None, "") else self.set_folders((value,))

    @staticmethod
    def _labels(folders: tuple[Path, ...]) -> tuple[str, ...]:
        counts: dict[str, int] = {}
        labels: list[str] = []
        for folder in folders:
            base = folder.name.strip() or folder.anchor.rstrip("\\/") or "Media"
            folded = base.casefold()
            counts[folded] = counts.get(folded, 0) + 1
            number = counts[folded]
            labels.append(base if number == 1 else f"{base} ({number})")
        return tuple(labels)

    def _load_config(self) -> None:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return
            configured = value.get("media_folders")
            if not isinstance(configured, list):
                old = value.get("media_folder")
                configured = [old] if isinstance(old, str) and old else []
            available = []
            for item in configured:
                if not isinstance(item, str) or not item:
                    continue
                try:
                    candidate = Path(item).resolve(strict=True)
                    if candidate.is_dir():
                        available.append(candidate)
                except OSError:
                    continue
            self._folders = self._resolve_folders(available)
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
        value["media_folders"] = [str(folder) for folder in self.folders]
        value.pop("media_folder", None)
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
        folders = self.folders
        labels = self._labels(folders)
        records: dict[str, MediaRecord] = {}
        physical_files: set[str] = set()
        errors: list[str] = []
        for root_index, (root, label) in enumerate(zip(folders, labels)):
            try:
                for current, directories, files in os.walk(root, followlinks=False):
                    current_path = Path(current)
                    try:
                        with os.scandir(current_path) as iterator:
                            entries = {entry.name: entry for entry in iterator}
                    except OSError as error:
                        directories[:] = []
                        errors.append(f"{label}: {error}")
                        continue
                    directories[:] = [name for name in sorted(directories, key=str.casefold)
                                      if name in entries and not self._reparse(entries[name])]
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
                            attributes = getattr(information, "st_file_attributes", 0)
                            if (not stat.S_ISREG(information.st_mode) or
                                    attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                                continue
                            resolved = path.resolve(strict=True)
                            physical_key = os.path.normcase(str(resolved))
                            if physical_key in physical_files:
                                continue
                            physical_files.add(physical_key)
                            relative = path.relative_to(root).as_posix()
                        except (KeyError, OSError, ValueError):
                            continue
                        identity = (str(root).encode("utf-8") + b"\0" + relative.encode("utf-8") +
                                    b"\0" + str(information.st_size).encode() + b"\0" +
                                    str(information.st_mtime_ns).encode())
                        media_id = hashlib.blake2s(identity, key=self._secret,
                                                  digest_size=16).hexdigest()
                        records[media_id] = MediaRecord(
                            media_id, path, name[:240], relative, media_type[0], media_type[1],
                            information.st_size, information.st_mtime_ns, (), label, root,
                            root_index)
                    if len(records) >= MAX_MEDIA_ITEMS:
                        break
            except OSError as error:
                errors.append(f"{label}: {error}")
            if len(records) >= MAX_MEDIA_ITEMS:
                break
        with self._lock:
            self._records = records
            self.last_error = "; ".join(errors)[:320]
        return len(records)

    @staticmethod
    def _sort_key(record: MediaRecord) -> tuple[object, ...]:
        parent = Path(record.relative_path).parent.as_posix()
        return (record.root_index, parent.casefold(), record.name.casefold())

    def listing(self) -> list[dict[str, object]]:
        return [record.public() for record in sorted(self.records(), key=self._sort_key)]

    def records(self) -> list[MediaRecord]:
        with self._lock:
            return list(self._records.values())

    def get(self, media_id: str) -> MediaRecord | None:
        with self._lock:
            record = self._records.get(media_id)
            folders = self._folders
        root = record.root if record else None
        if record is None or root is None or root not in folders:
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
