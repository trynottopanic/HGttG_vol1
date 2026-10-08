#!/usr/bin/python3
"""Production construction for the storage-owned Media Library catalog."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import socket
import select
import time
from guide_ipc import EVENT, encode_packet, send_packet
from dataclasses import dataclass

from storage_media_host import StorageMediaHost
from media_library_broker import MediaLibraryBroker
from provider_grants import ProviderGrantValidator

STATE = Path("/var/lib/guideos-media")

@dataclass(frozen=True)
class _UntrustedPeerCredentials:
    pid: int
    uid: int
    gid: int
    pidfd: int

class _CredentialCapture:
    """Pin credentials; Foundation provider performs authoritative resolution."""
    def resolve(self, pid, uid, gid):
        if any(type(value) is not int or value < 0 for value in (pid, uid, gid)) or pid <= 0:
            raise RuntimeError("invalid peer credentials")
        return _UntrustedPeerCredentials(pid, uid, gid, os.pidfd_open(pid, 0))

class MediaLibraryEndpoint:
    def __init__(self, listener, catalog, *, resolver=None, grants=None):
        self.listener = listener
        self.listener.setblocking(False)
        self.watchers=[];self.catalog=catalog
        self.broker = MediaLibraryBroker(catalog, resolver or _CredentialCapture(),
                                         grants or ProviderGrantValidator(),self.watch)

    def poll(self):
        connection, _ = self.listener.accept()
        retained=False
        try:
            connection.settimeout(.1)
            retained=self.broker.serve_connection(connection)
        except (OSError,ValueError):
            pass
        finally:
            if not retained:connection.close()

    def watch(self,connection,peer,grant,deadline,revision,request_id):
        if len(self.watchers)>=8:return False
        current=self.catalog.library_revision
        self.broker._reply(connection,request_id,0,{0:current})
        if revision!=current:
            send_packet(connection,encode_packet(EVENT,0,{0:3,1:{0:current}}))
        self.watchers.append(dict(connection=connection,peer=peer,grant=grant,
                                  deadline=deadline,revision=current,next_check=0))
        return True

    def tick(self):
        if not self.watchers:return
        w=self.watchers.pop(0);connection=w['connection']
        try:
            if select.select([w['peer'].pidfd],[],[],0)[0]:raise ProcessLookupError()
            if time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=w['deadline']:raise TimeoutError()
            if time.monotonic()>=w['next_check']:
                self.broker.grants.validate_peer(w['grant'],w['peer'],capability='media.library.browse')
                w['next_check']=time.monotonic()+1
            if self.catalog.library_revision!=w['revision']:
                current=self.catalog.library_revision
                send_packet(connection,encode_packet(EVENT,0,{0:1,1:{0:current,1:1}}))
                w['revision']=current
            self.watchers.append(w)
        except Exception:
            connection.close();os.close(w['peer'].pidfd)

    def close(self):
        for w in self.watchers:
            w['connection'].close();os.close(w['peer'].pidfd)
        self.watchers.clear();self.listener.close()


def _private_value(directory: Path, name: str, size: int) -> bytes:
    """Create or read one fixed-size private value without following links."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
                           getattr(os, "O_NOFOLLOW", 0))
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(name, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            value = os.urandom(size)
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                                 0o600, dir_fd=directory_fd)
            try:
                if os.write(descriptor, value) != size:
                    raise OSError("short private-value write")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.fsync(directory_fd)
            descriptor = os.open(name, flags, dir_fd=directory_fd)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size != size or info.st_mode & 0o077:
                raise RuntimeError(f"invalid media state file: {name}")
            value = os.read(descriptor, size + 1)
            if len(value) != size:
                raise RuntimeError(f"invalid media state length: {name}")
            return value
        finally:
            os.close(descriptor)
    finally:
        os.close(directory_fd)


def create_storage_media_host(mount: Path, *, state: Path = STATE, endpoint=None, internal_source=False):
    source_id = _private_value(state, "storage-source-id", 16)
    id_key = _private_value(state, "storage-id-key", 32)
    host = StorageMediaHost(mount, source_id=source_id, id_key=id_key)
    if internal_source:
        from media_source_channel import SourceEndpoint
        host.source_endpoint = SourceEndpoint(host.catalog)
    if endpoint is not None:
        host.endpoint = MediaLibraryEndpoint(endpoint, host.catalog)
    return host
