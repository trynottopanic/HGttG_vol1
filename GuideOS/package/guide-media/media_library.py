#!/usr/bin/python3
"""Bounded read-only media catalog for an External Storage 0 provider."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Iterable

PAGE_LIMIT = 32
SCAN_LIMIT = 10_000
NAME_BYTES = 512
FOLDER_BYTES = 512

AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}

SOURCE_STORAGE = 1
KIND_AUDIO = 1
KIND_VIDEO = 2
AVAILABLE = 1
COMPATIBILITY_UNKNOWN = 0


class MediaLibraryError(RuntimeError):
    pass


class StaleMedia(MediaLibraryError):
    pass


class MediaNotFound(MediaLibraryError):
    pass


class InvalidStorageRecord(MediaLibraryError):
    pass


@dataclass(frozen=True)
class MediaRecord:
    media_id: bytes
    source_id: bytes
    kind: int
    display_name: str
    folder_display: str
    size: int
    modified_ns: int
    availability_generation: int
    relative_parts: tuple[str, ...]
    device: int
    inode: int

    def summary(self) -> dict[int, object]:
        return {
            0: self.media_id,
            1: self.source_id,
            2: SOURCE_STORAGE,
            3: self.kind,
            4: self.display_name,
            5: self.folder_display,
            6: self.size,
            7: self.modified_ns,
            8: None,
            9: AVAILABLE,
            10: self.availability_generation,
            11: COMPATIBILITY_UNKNOWN,
            12: 0,
            13: 0,
        }


def _bounded_text(value: str, maximum: int) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= maximum:
        return value
    raw = raw[:maximum]
    while raw:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raw = raw[:-1]
    return ""


def _one_casefold_directory(parent: Path, wanted: str) -> Path | None:
    matches = []
    try:
        entries = list(parent.iterdir())
    except OSError as exc:
        raise InvalidStorageRecord("storage root is unreadable") from exc
    if len(entries) > 512:
        raise InvalidStorageRecord("storage directory exceeds recognition bound")
    for entry in entries:
        if entry.name.casefold() == wanted.casefold():
            matches.append(entry)
    if len(matches) > 1:
        raise InvalidStorageRecord("conflicting storage directory names")
    if not matches:
        return None
    candidate = matches[0]
    if candidate.is_symlink() or not candidate.is_dir():
        raise InvalidStorageRecord("media root must be a real directory")
    return candidate


class StorageMediaCatalog:
    """Private catalog. Paths never leave this object or its trusted broker."""

    def __init__(self, storage_root: Path, *, source_id: bytes, id_key: bytes):
        if type(source_id) is not bytes or len(source_id) != 16 or not any(source_id):
            raise ValueError("source_id must be a nonzero 16-byte value")
        if type(id_key) is not bytes or len(id_key) < 16:
            raise ValueError("id_key must contain at least 16 bytes")
        self.storage_root = Path(storage_root)
        self.source_id = source_id
        self.id_key = id_key
        self.library_revision = 0
        self.availability_generation = 0
        self.incomplete = False
        self._media_root: Path | None = None
        self._records: dict[bytes, MediaRecord] = {}
        self._ordered: tuple[MediaRecord, ...] = ()

    def _identity(self, parts: Iterable[str]) -> bytes:
        normalized = PurePosixPath(*parts).as_posix().encode("utf-8")
        return hashlib.blake2b(normalized, key=self.id_key, digest_size=16,
                              person=b"guide-media-v1").digest()

    def refresh(self, storage: dict[str, object]) -> None:
        if type(storage) is not dict:
            raise InvalidStorageRecord("storage record must be a map")
        state = storage.get("state")
        generation = storage.get("generation")
        folders = storage.get("folders", [])
        if type(state) is not str or type(generation) is not int or generation < 0:
            raise InvalidStorageRecord("storage state or generation is invalid")
        if type(folders) is not list or any(type(value) is not str for value in folders):
            raise InvalidStorageRecord("storage folder evidence is invalid")

        records: list[MediaRecord] = []
        media_root = None
        incomplete = False
        if state == "guide" and "MEDIA" in {value.upper() for value in folders}:
            guide = _one_casefold_directory(self.storage_root, "GUIDE")
            if guide is None:
                raise InvalidStorageRecord("storage record disagrees with mounted layout")
            media_root = _one_casefold_directory(guide, "MEDIA")
            if media_root is None:
                raise InvalidStorageRecord("storage record names a missing media root")
            inspected = 0
            for current, directories, files in os.walk(media_root, followlinks=False):
                directories[:] = sorted((name for name in directories
                                          if not (Path(current) / name).is_symlink()),
                                         key=str.casefold)
                for name in sorted(files, key=str.casefold):
                    inspected += 1
                    if inspected > SCAN_LIMIT:
                        incomplete = True
                        break
                    path = Path(current) / name
                    try:
                        info = path.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    suffix = path.suffix.casefold()
                    kind = KIND_AUDIO if suffix in AUDIO_EXTENSIONS else KIND_VIDEO if suffix in VIDEO_EXTENSIONS else 0
                    if not kind:
                        continue
                    relative = path.relative_to(media_root)
                    parts = relative.parts
                    folder = "" if len(parts) == 1 else PurePosixPath(*parts[:-1]).as_posix()
                    records.append(MediaRecord(
                        self._identity(parts), self.source_id, kind,
                        _bounded_text(name, NAME_BYTES), _bounded_text(folder, FOLDER_BYTES),
                        info.st_size, info.st_mtime_ns, generation, tuple(parts),
                        info.st_dev, info.st_ino))
                if incomplete:
                    break

        records.sort(key=lambda record: (record.folder_display.casefold(),
                                         record.display_name.casefold(), record.media_id))
        self.availability_generation = generation
        self._media_root = media_root
        self._ordered = tuple(records)
        self._records = {record.media_id: record for record in records}
        self.incomplete = incomplete
        self.library_revision += 1

    def snapshot(self) -> dict[int, object]:
        return {0: self.library_revision, 1: 1 if self._media_root else 0,
                2: len(self._ordered), 3: self.incomplete}

    def list(self, *, after_media_id: bytes | None, limit: int,
             source_class: int | None = None, media_kind: int | None = None,
             source_id: bytes | None = None) -> dict[int, object]:
        if type(limit) is not int or not 1 <= limit <= PAGE_LIMIT:
            raise ValueError("limit must be between 1 and 32")
        if source_class not in (None, SOURCE_STORAGE) or source_id not in (None, self.source_id):
            selected: list[MediaRecord] = []
        else:
            selected = [record for record in self._ordered
                        if media_kind is None or record.kind == media_kind]
        start = 0
        if after_media_id is not None:
            if type(after_media_id) is not bytes or len(after_media_id) != 16:
                raise ValueError("invalid cursor")
            indexes = [index for index, record in enumerate(selected)
                       if record.media_id == after_media_id]
            if not indexes:
                raise StaleMedia("cursor is stale")
            start = indexes[0] + 1
        page = selected[start:start + limit]
        return {0: self.library_revision, 1: [record.summary() for record in page],
                2: start + len(page) < len(selected)}

    def describe(self, media_id: bytes, generation: int) -> dict[int, object]:
        record = self._lookup(media_id, generation)
        return {0: record.summary(), 1: [], 2: 0, 3: AVAILABLE, 4: None}

    def _lookup(self, media_id: bytes, generation: int) -> MediaRecord:
        if type(media_id) is not bytes or len(media_id) != 16:
            raise MediaNotFound("invalid media identity")
        record = self._records.get(media_id)
        if record is None:
            raise MediaNotFound("media identity is unavailable")
        if generation != self.availability_generation or generation != record.availability_generation:
            raise StaleMedia("media generation is stale")
        return record

    def open_local(self, media_id: bytes, generation: int) -> int:
        record = self._lookup(media_id, generation)
        if self._media_root is None:
            raise MediaNotFound("media source is unavailable")
        opened: list[int] = []
        try:
            current = os.open(self._media_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened.append(current)
            for part in record.relative_parts[:-1]:
                current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=current)
                opened.append(current)
            descriptor = os.open(record.relative_parts[-1], os.O_RDONLY | os.O_NOFOLLOW,
                                 dir_fd=current)
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_dev != record.device or
                    info.st_ino != record.inode or info.st_size != record.size or
                    info.st_mtime_ns != record.modified_ns):
                os.close(descriptor)
                raise StaleMedia("media changed after cataloging")
            os.set_inheritable(descriptor, False)
            return descriptor
        except OSError as exc:
            raise StaleMedia("media changed or disappeared") from exc
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)
