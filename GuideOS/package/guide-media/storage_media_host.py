#!/usr/bin/python3
"""Media catalog lifecycle adapter hosted inside External Storage 0."""
from __future__ import annotations

from pathlib import Path
from media_library import StorageMediaCatalog


class StorageMediaHost:
    """Keep the catalog synchronized with trusted storage recognition records.

    Socket/listener ownership is deliberately injected. This object is safe to
    host in the storage service's private mount namespace and never publishes a
    physical path.
    """

    def __init__(self, mount: Path, *, source_id: bytes, id_key: bytes,
                 endpoint=None):
        self.catalog = StorageMediaCatalog(mount, source_id=source_id, id_key=id_key)
        self.endpoint = endpoint
        self.source_endpoint = None
        self.last_signature = None
        self.closed = False

    @property
    def listener(self):
        return getattr(self.endpoint, "listener", None)

    def refresh(self, storage_record: dict[str, object]) -> None:
        if self.closed:
            raise RuntimeError("media host is closed")
        signature = (storage_record.get("generation"), storage_record.get("state"),
                     tuple(storage_record.get("folders", [])))
        if signature != self.last_signature:
            self.catalog.refresh(storage_record)
            self.last_signature = signature

    def poll(self) -> None:
        if self.endpoint is not None:
            self.endpoint.poll()

    def tick(self):
        if self.source_endpoint is not None:
            import select
            if select.select([self.source_endpoint.listener],[],[],0)[0]:self.source_endpoint.poll()
        if self.endpoint is not None and hasattr(self.endpoint,'tick'):self.endpoint.tick()

    def invalidate(self, generation: int) -> None:
        self.refresh({"state": "absent", "generation": generation, "folders": []})

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.source_endpoint is not None:self.source_endpoint.close()
        if self.endpoint is not None:
            self.endpoint.close()
