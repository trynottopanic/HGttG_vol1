#!/usr/bin/python3
"""Provider-private transactions for the future documents.notepad collection.

This module is deliberately not an application API. The External Storage provider
owns its root descriptor, card identity and insertion generation; Notepad will
eventually submit a bounded request through the capability broker. No caller is
given a mount path by this module. Host tests cannot prove exFAT interruption
behaviour on the Deck.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import unicodedata

MAX_CODEPOINTS = 5120
MAX_UTF8_BYTES = 20480
MAX_BASENAME_CODEPOINTS = 32
COLLECTION = 'documents.notepad'
_FORBIDDEN = set('/\\:*?"<>|')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CLOCK$'}
_RESERVED.update({f'COM{i}' for i in range(1, 10)})
_RESERVED.update({f'LPT{i}' for i in range(1, 10)})


class StoreError(Exception):
    """Typed caller-visible outcome; the caller retains the document buffer."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CardBinding:
    """Stable physical identity plus current insertion generation."""
    identity: tuple[str, ...]
    insertion_generation: int


@dataclass(frozen=True)
class DestinationState:
    """Missing or content digest state observed while opening a document."""
    exists: bool
    digest: str | None = None


@dataclass(frozen=True)
class SaveReceipt:
    filename: str
    state: DestinationState


@dataclass(frozen=True)
class RecoveryItem:
    """Provider-only reconciliation evidence; it is never an application path."""
    token: str
    state: str
    filename: str | None


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise StoreError('invalid-text', 'Document text must be Unicode text')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if len(text) > MAX_CODEPOINTS:
        raise StoreError('text-too-long', 'Document exceeds 5,120 characters')
    encoded = text.encode('utf-8')
    if len(encoded) > MAX_UTF8_BYTES:
        raise StoreError('text-too-large', 'Document exceeds 20,480 UTF-8 bytes')
    return text


def normalize_basename(name: str) -> str:
    if not isinstance(name, str):
        raise StoreError('invalid-name', 'Document name must be text')
    name = unicodedata.normalize('NFC', name)
    if not name or name in ('.', '..') or len(name) > MAX_BASENAME_CODEPOINTS:
        raise StoreError('invalid-name', 'Document name must contain 1 through 32 characters')
    if name[-1] in (' ', '.') or any(ord(ch) < 32 or ch in _FORBIDDEN for ch in name):
        raise StoreError('invalid-name', 'Document name contains unsupported characters')
    stem = name.split('.', 1)[0].upper()
    if stem in _RESERVED:
        raise StoreError('invalid-name', 'Document name is reserved for portable storage')
    return name


class NotepadStore:
    """System-owned transaction core; created only by the Storage provider."""
    def __init__(self, collection_root: Path, recovery_root: Path, binding_supplier):
        self._root = Path(collection_root)
        self._recovery = Path(recovery_root)
        self._binding_supplier = binding_supplier

    @staticmethod
    def _filename(name: str) -> str:
        return normalize_basename(name) + '.txt'

    @staticmethod
    def _digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _require_binding(self, expected: CardBinding) -> None:
        if self._binding_supplier() != expected:
            raise StoreError('card-changed', 'External card was removed or reinserted')

    def _dirfd(self) -> int:
        return os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def _state(self, directory_fd: int, filename: str) -> DestinationState:
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        except FileNotFoundError:
            return DestinationState(False)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise StoreError('invalid-destination', 'Document destination is not a regular file')
            data = b''
            while len(data) <= MAX_UTF8_BYTES + 3:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                data += chunk
            if data.startswith(b'\xef\xbb\xbf'):
                data = data[3:]
            try:
                decoded = data.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise StoreError('invalid-destination', 'Existing document is not valid UTF-8') from exc
            normalize_text(decoded)
            return DestinationState(True, self._digest(data))
        finally:
            os.close(fd)

    def _record(self, token: str, record: dict) -> Path:
        self._recovery.mkdir(parents=True, exist_ok=True)
        target = self._recovery / (token + '.json')
        temporary = self._recovery / (token + '.tmp')
        with open(temporary, 'w', encoding='utf-8', newline='\n') as out:
            json.dump(record, out, sort_keys=True, separators=(',', ':'))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
        return target

    def recoveries(self, binding: CardBinding) -> list[RecoveryItem]:
        """Classify durable incomplete transactions without silently committing.

        After interrupted removable-media writes, automatic completion could be
        mistaken for a user-approved overwrite. The future service uses this
        bounded result to present recovery/cancel choices, then performs a new
        transaction only with current authorization.
        """
        self._require_binding(binding)
        if not self._recovery.exists():
            return []
        results = []
        for record_path in sorted(self._recovery.glob('*.json'))[:16]:
            try:
                record = json.loads(record_path.read_text(encoding='utf-8'))
                recorded = CardBinding(tuple(record['binding']['identity']), record['binding']['generation'])
                filename = record['filename']
                if recorded != binding or record.get('collection') != COLLECTION:
                    results.append(RecoveryItem(record_path.stem, 'different-card', None))
                    continue
                directory_fd = self._dirfd()
                try:
                    destination = self._state(directory_fd, filename)
                    temporary = record.get('temporary', '')
                    temp_state = self._state(directory_fd, temporary) if temporary else DestinationState(False)
                finally:
                    os.close(directory_fd)
                desired = record.get('digest')
                if destination.exists and destination.digest == desired:
                    results.append(RecoveryItem(record_path.stem, 'committed-cleanup', filename))
                elif temp_state.exists and temp_state.digest == desired:
                    results.append(RecoveryItem(record_path.stem, 'ready-for-owner-recovery', filename))
                else:
                    results.append(RecoveryItem(record_path.stem, 'needs-investigation', filename))
            except (OSError, KeyError, TypeError, ValueError, StoreError):
                results.append(RecoveryItem(record_path.stem, 'invalid-record', None))
        return results

    def save(self, *, name: str, text: str, expected: DestinationState,
             binding: CardBinding, replace: bool) -> SaveReceipt:
        """Write a temporary sibling then explicit create/replace commit."""
        filename = self._filename(name)
        payload = normalize_text(text).encode('utf-8')
        self._require_binding(binding)
        directory_fd = self._dirfd()
        temp_name = '.guideos-notepad-' + secrets.token_hex(16) + '.tmp'
        token = secrets.token_hex(16)
        try:
            current = self._state(directory_fd, filename)
            if current != expected:
                raise StoreError('destination-changed', 'Document changed since it was opened')
            if current.exists and not replace:
                raise StoreError('replace-required', 'An existing document requires an explicit replacement')
            if not current.exists and replace:
                raise StoreError('destination-missing', 'There is no document to replace')
            record_path = self._record(token, dict(
                version=0, collection=COLLECTION, filename=filename,
                binding=dict(identity=list(binding.identity), generation=binding.insertion_generation),
                expected=dict(exists=expected.exists, digest=expected.digest),
                temporary=temp_name, digest=self._digest(payload), state='prepared'))
            temp_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
            try:
                offset = 0
                while offset < len(payload):
                    offset += os.write(temp_fd, payload[offset:])
                os.fsync(temp_fd)
            finally:
                os.close(temp_fd)
            self._require_binding(binding)
            if self._state(directory_fd, filename) != expected:
                raise StoreError('destination-changed', 'Document changed before commit')
            os.replace(temp_name, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.fsync(directory_fd)
            record_path.unlink()
            return SaveReceipt(filename, DestinationState(True, self._digest(payload)))
        finally:
            os.close(directory_fd)
            # A record intentionally remains after a failed post-setup save.
            # A stale temporary object is hidden and never a user document.
