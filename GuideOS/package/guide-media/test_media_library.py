from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
IPC = HERE.parent / "guide-ipc"
SUPERVISOR = HERE.parent / "guide-supervisor" / "host"
sys.path[:0] = [str(HERE), str(IPC / "python"), str(IPC / "generated"), str(SUPERVISOR)]

from guide_grants import GrantStore
from guide_instance_registry import InstanceContext, InstanceRegistry
from guide_ipc import REQUEST, encode_packet, recv_packet, send_packet
from media_library import (KIND_AUDIO, KIND_VIDEO, MediaNotFound, StaleMedia,
                           StorageMediaCatalog)
from media_library_broker import MediaLibraryBroker
from storage_media_host import StorageMediaHost


class ResolverFixture:
    def __init__(self, base: Path):
        self.proc = base / "proc"
        self.cgroup = base / "cgroup"
        self.pid = os.getpid()
        self.uid = os.getuid()
        group = self.cgroup / "guide-app-media.service"
        (self.proc / str(self.pid)).mkdir(parents=True)
        group.mkdir(parents=True)
        (self.proc / str(self.pid) / "status").write_text(
            f"Name:\ttest\nUid:\t{self.uid}\t{self.uid}\t{self.uid}\t{self.uid}\n",
            encoding="ascii")
        (self.proc / str(self.pid) / "cgroup").write_text(
            "0::/guide-app-media.service\n", encoding="ascii")
        self.context = InstanceContext("2" * 32, 1, "2001", "main",
                                       "guide-app-media.service", group, self.uid, 3)
        self.registry = InstanceRegistry(proc_root=self.proc, cgroup_root=self.cgroup)
        self.registry.register(self.context)
        self.registry.set_reconciled(True)


class MediaLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "card" / "GUIDE" / "MEDIA"
        (self.media / "Films").mkdir(parents=True)
        (self.media / "Music").mkdir()
        (self.media / "Films" / "Movie.mp4").write_bytes(b"video")
        (self.media / "Music" / "Song.flac").write_bytes(b"audio")
        (self.media / "ignore.txt").write_text("not media", encoding="utf-8")
        (self.media / "escape.mp3").symlink_to(self.root / "outside.mp3")
        self.catalog = StorageMediaCatalog(self.root / "card",
                                           source_id=b"S" * 16, id_key=b"K" * 32)
        self.catalog.refresh({"state": "guide", "generation": 7,
                              "folders": ["MEDIA"]})

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_is_bounded_private_and_paginated(self):
        snapshot = self.catalog.snapshot()
        self.assertEqual(snapshot[2], 2)
        first = self.catalog.list(after_media_id=None, limit=1)
        self.assertTrue(first[2])
        record = first[1][0]
        self.assertIsInstance(record[0], bytes)
        self.assertNotIn(str(self.root), repr(record))
        second = self.catalog.list(after_media_id=record[0], limit=1)
        self.assertFalse(second[2])
        self.assertEqual({record[3], second[1][0][3]}, {KIND_AUDIO, KIND_VIDEO})

    def test_stale_cursor_generation_and_changed_file_fail(self):
        item = self.catalog.list(after_media_id=None, limit=2)[1][0]
        with self.assertRaises(StaleMedia):
            self.catalog.describe(item[0], 6)
        with self.assertRaises(StaleMedia):
            self.catalog.list(after_media_id=b"X" * 16, limit=1)
        target = self.media / item[5] / item[4]
        target.write_bytes(b"changed")
        with self.assertRaises(StaleMedia):
            self.catalog.open_local(item[0], 7)

    def test_absent_storage_is_not_a_false_empty_source(self):
        self.catalog.refresh({"state": "absent", "generation": 8, "folders": []})
        snapshot = self.catalog.snapshot()
        self.assertEqual({key: snapshot[key] for key in (1, 2, 3)},
                         {1: 0, 2: 0, 3: False})
        with self.assertRaises(MediaNotFound):
            self.catalog.describe(b"A" * 16, 8)

    def test_open_returns_same_regular_file_without_a_path(self):
        item = self.catalog.list(after_media_id=None, limit=2)[1][0]
        descriptor = self.catalog.open_local(item[0], 7)
        try:
            self.assertIn(os.read(descriptor, 16), (b"audio", b"video"))
            self.assertFalse(os.get_inheritable(descriptor))
        finally:
            os.close(descriptor)

    def test_host_accepts_absent_then_ready_with_same_generation(self):
        host = StorageMediaHost(self.root / "card", source_id=b"S" * 16,
                                id_key=b"K" * 32)
        host.invalidate(9)
        host.refresh({"state": "guide", "generation": 9,
                      "folders": ["MEDIA"]})
        snapshot = host.catalog.snapshot()
        self.assertEqual(snapshot[1], 1)
        self.assertEqual(snapshot[2], 2)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        media = root / "card" / "GUIDE" / "MEDIA"
        media.mkdir(parents=True)
        (media / "Clip.mp4").write_bytes(b"clip")
        self.catalog = StorageMediaCatalog(root / "card", source_id=b"S" * 16,
                                           id_key=b"K" * 32)
        self.catalog.refresh({"state": "guide", "generation": 3,
                              "folders": ["MEDIA"]})
        self.fixture = ResolverFixture(root)
        self.grants = GrantStore()

    def tearDown(self):
        self.temp.cleanup()

    def exchange(self, operation, arguments, capability, descriptors=0):
        grant = self.grants.issue(self.fixture.context, provider="guide.media.library",
                                  interface_major=1, capability=capability,
                                  operations={operation})
        arguments = dict(arguments)
        arguments[0] = grant.grant_id
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        errors = []
        def server():
            try:
                MediaLibraryBroker(self.catalog, self.fixture.registry,
                                   self.grants).serve_connection(right)
            except Exception as exc:
                errors.append(exc)
            finally:
                right.close()
        thread = threading.Thread(target=server)
        thread.start()
        deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 1_000_000_000
        send_packet(left, encode_packet(REQUEST, 44,
                    {0: operation, 1: arguments, 2: deadline},
                    interface_major=1, interface_minor=0))
        header, payload, received = recv_packet(left)
        left.close(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(header.request_id, 44)
        self.assertEqual(len(received), descriptors)
        return payload, received

    def test_snapshot_list_describe_and_open(self):
        payload, received = self.exchange(1, {}, "media.library.browse")
        self.assertEqual(payload[0], 0); self.assertEqual(received, [])
        payload, received = self.exchange(2, {1: None, 2: 32, 3: None, 4: None,
                                              5: None}, "media.library.browse")
        self.assertEqual(payload[0], 0)
        item = payload[1][1][0]
        payload, _ = self.exchange(3, {1: item[0], 2: 3}, "media.library.browse")
        self.assertEqual(payload[0], 0)
        payload, received = self.exchange(4, {1: item[0], 2: 3, 3: None, 4: None},
                                          "media.source.open", descriptors=1)
        self.assertEqual(payload[0], 0)
        try:
            self.assertEqual(os.read(received[0], 8), b"clip")
        finally:
            os.close(received[0])

    def test_wrong_capability_is_denied(self):
        payload, received = self.exchange(1, {}, "media.source.open")
        self.assertEqual(payload[0], 6)
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
