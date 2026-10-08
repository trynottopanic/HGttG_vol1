from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IPC = HERE.parent / "guide-ipc"
sys.path[:0] = [str(IPC / "python"), str(IPC / "generated")]

from media_library import StorageMediaCatalog
from media_session import (CLOSED, EVENT_RESNAPSHOT_REQUIRED, PAUSED, PLAYING,
                           BUFFERING, MediaSessionManager, StaleSession, WrongOwner)
from media_session_broker import DENIED, MediaSessionBroker, OK
from guide_grants import GrantStore
from guide_ipc import EVENT, REQUEST, encode_packet, recv_packet, send_packet


class Context:
    def __init__(self, instance_id="owner", generation=1):
        self.instance_id = instance_id
        self.generation = generation


class Engine:
    def __init__(self):
        self.position_ms = 0
        self.duration_ms = 30_000
        self.stopped = False
        self.actions = []
    def open(self, descriptor, position_ms):
        self.actions.append(("open", os.read(descriptor, 8))); self.position_ms = position_ms
    def play(self): self.actions.append(("play",));
    def pause(self): self.actions.append(("pause",));
    def seek(self, value): self.actions.append(("seek", value)); self.position_ms = value
    def select_audio(self, value): self.actions.append(("audio", value))
    def select_subtitle(self, value): self.actions.append(("subtitle", value))
    def set_output(self, value): self.actions.append(("output", value))
    def stop(self): self.actions.append(("stop",)); self.stopped = True


class Admission:
    def __init__(self): self.active = set(); self.released = []
    def acquire(self, context, media_id, output_id):
        lease = object(); self.active.add(lease); return lease
    def release(self, lease): self.active.discard(lease); self.released.append(lease)


class Checkpoints:
    def __init__(self): self.saved = []
    def save(self, *value): self.saved.append(value)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        media = root / "GUIDE" / "MEDIA"; media.mkdir(parents=True)
        (media / "clip.mp4").write_bytes(b"video")
        self.catalog = StorageMediaCatalog(root, source_id=b"S"*16, id_key=b"K"*32)
        self.catalog.refresh({"state":"guide","generation":4,"folders":["MEDIA"]})
        self.item = self.catalog.list(after_media_id=None, limit=1)[1][0]
        self.engines=[]
        def factory(): value=Engine(); self.engines.append(value); return value
        self.admission=Admission(); self.checkpoints=Checkpoints()
        self.manager=MediaSessionManager(self.catalog,factory,self.admission,self.checkpoints)
        self.owner=Context()
    def tearDown(self): self.temp.cleanup()

    def open(self):
        return self.manager.open(self.owner,self.item[0],4,resume_position_ms=100)

    def test_acknowledged_lifecycle_checkpoint_and_cleanup(self):
        opened=self.open(); sid=opened[0]
        self.assertEqual(opened[1],PAUSED)
        played=self.manager.play(self.owner,sid,opened[2]); self.assertEqual(played[0],PLAYING)
        sought=self.manager.seek(self.owner,sid,played[1],500)
        paused=self.manager.pause(self.owner,sid,sought[1]); self.assertEqual(paused[0],PAUSED)
        saved=self.manager.checkpoint(self.owner,sid,paused[1]); self.assertEqual(len(self.checkpoints.saved),1)
        stopped=self.manager.stop(self.owner,sid,saved[1]); self.assertEqual(stopped[0],CLOSED)
        self.assertTrue(self.engines[0].stopped); self.assertFalse(self.admission.active)

    def test_stale_revision_and_wrong_owner_are_rejected(self):
        opened=self.open(); sid=opened[0]
        with self.assertRaises(StaleSession): self.manager.play(self.owner,sid,1)
        with self.assertRaises(WrongOwner): self.manager.snapshot(Context("other",1),sid)

    def test_open_failure_rolls_back_lease_and_session(self):
        with self.assertRaises(Exception): self.manager.open(self.owner,self.item[0],3)
        self.assertFalse(self.admission.active); self.assertEqual(self.manager.sessions,{})

    def test_owner_exit_stops_every_active_session(self):
        first=self.open(); second=self.open()
        self.assertEqual(self.manager.invalidate_owner("owner",1),2)
        self.assertEqual(self.manager.snapshot(self.owner,first[0])[0],CLOSED)
        self.assertEqual(self.manager.snapshot(self.owner,second[0])[0],CLOSED)

    def test_closed_sessions_reuse_capacity(self):
        for _ in range(12):
            opened = self.open()
            self.manager.stop(self.owner, opened[0])
        self.assertLessEqual(len(self.manager.sessions), self.manager.session_limit)
        self.assertFalse(self.admission.active)

    def test_factory_failure_releases_admission(self):
        def fail(): raise RuntimeError("decoder unavailable")
        self.manager.engine_factory = fail
        with self.assertRaises(RuntimeError): self.open()
        self.assertFalse(self.admission.active)
        self.assertFalse(self.manager.sessions)

    def test_stop_failure_releases_once_and_closes(self):
        opened = self.open()
        def fail(): raise RuntimeError("decoder stop failed")
        self.engines[0].stop = fail
        self.assertEqual(self.manager.invalidate_owner("owner", 1), 1)
        self.assertEqual(len(self.admission.released), 1)
        self.assertEqual(self.manager.snapshot(self.owner, opened[0])[0], CLOSED)
        self.manager.stop(self.owner, opened[0])
        self.assertEqual(len(self.admission.released), 1)

    def test_source_loss_stops_matching_generation(self):
        opened = self.open()
        self.assertEqual(self.manager.invalidate_source(3), 0)
        self.assertEqual(self.manager.invalidate_source(4), 1)
        self.assertTrue(self.engines[0].stopped)
        self.assertEqual(self.manager.snapshot(self.owner, opened[0])[0], CLOSED)

    def test_closed_session_rejects_controls_and_checkpoint(self):
        from media_session import InvalidTransition
        opened = self.open()
        result = self.manager.stop(self.owner, opened[0])
        for method, extra in [(self.manager.set_output, [b"O"*16]),
                              (self.manager.select_audio, [b"A"*16]),
                              (self.manager.select_subtitle, [None]),
                              (self.manager.checkpoint, [])]:
            with self.assertRaises(InvalidTransition):
                method(self.owner, opened[0], result[1], *extra)

    def test_bounded_event_history_requests_resnapshot(self):
        opened=self.open(); sid=opened[0]; revision=opened[2]
        for _ in range(10):
            result=self.manager.play(self.owner,sid,revision); revision=result[1]
            result=self.manager.pause(self.owner,sid,revision); revision=result[1]
        events=self.manager.events_after(self.owner,sid,0)
        self.assertEqual(events[0][1],EVENT_RESNAPSHOT_REQUIRED)

    def test_end_of_media_closes_and_releases(self):
        opened=self.open();sid=opened[0]
        self.manager.play(self.owner,sid,opened[2])
        self.engines[0].poll=lambda:{"ended":True}
        self.assertEqual(self.manager.refresh(self.owner,sid)[0],CLOSED)
        self.assertTrue(self.engines[0].stopped)
        self.assertFalse(self.admission.active)

    def test_engine_buffering_is_acknowledged_before_playing(self):
        opened=self.open();sid=opened[0];engine=self.engines[0]
        engine.play=lambda:False
        engine.poll=lambda:{"ready":False,"buffered_ms":300}
        result=self.manager.play(self.owner,sid,opened[2]);self.assertEqual(result[0],BUFFERING)
        engine.poll=lambda:{"ready":True,"buffered_ms":750}
        result=self.manager.refresh(self.owner,sid);self.assertEqual(result[0],PLAYING)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        SessionTests.setUp(self)
        self.grants = GrantStore()
        self.grant = self.grants.issue(
            self.owner, provider="guide.media.session", interface_major=1,
            capability="media.session.control", operations=range(1, 12))

        class Resolver:
            def __init__(inner, context): inner.context = context
            def resolve(inner, pid, uid, gid):
                return SimpleNamespace(context=inner.context,
                                       pidfd=os.open("/dev/null", os.O_RDONLY))
        self.broker = MediaSessionBroker(self.manager, Resolver(self.owner), self.grants)

    def tearDown(self):
        SessionTests.tearDown(self)

    def exchange(self, operation, arguments, event_count=0):
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        thread = threading.Thread(target=self.broker.serve_connection,
                                  args=(server,), daemon=True)
        thread.start()
        deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 1_000_000_000
        packet = encode_packet(REQUEST, 7, {0: operation, 1: arguments, 2: deadline},
                               interface_major=1, interface_minor=0)
        send_packet(client, packet)
        reply = recv_packet(client)
        events = [recv_packet(client) for _ in range(event_count)]
        client.close(); server.close(); thread.join(1)
        return reply, events

    def test_open_play_snapshot_and_watch(self):
        reply, _ = self.exchange(1, {0:self.grant.grant_id, 1:self.item[0], 2:4,
                                     3:None, 4:None, 5:None, 6:100})
        self.assertEqual(reply[1][0], OK)
        sid, revision = reply[1][1][0], reply[1][1][2]
        played, _ = self.exchange(2, {0:self.grant.grant_id, 1:sid, 2:revision})
        self.assertEqual(played[1][1][0], PLAYING)
        snapshot, _ = self.exchange(10, {0:self.grant.grant_id, 1:sid})
        self.assertEqual(snapshot[1][1][0], PLAYING)
        watched, events = self.exchange(11, {0:self.grant.grant_id, 1:sid,
                                             2:revision}, event_count=1)
        self.assertEqual(watched[1][0], OK)
        self.assertEqual(events[0][0].message_class, EVENT)
        self.assertEqual(events[0][1][0], 1)

    def test_provider_resolved_identity_without_local_context(self):
        owner = self.owner
        class Resolver:
            def resolve(inner, pid, uid, gid):
                return SimpleNamespace(pid=pid, uid=uid, gid=gid,
                                       pidfd=os.pidfd_open(pid))
        class Provider:
            def validate_peer(inner, grant, peer, *, capability):
                self.assertEqual(capability, "media.session.control")
                return owner
        self.broker = MediaSessionBroker(self.manager, Resolver(), Provider())
        reply, _ = self.exchange(1, {0:b"G"*16, 1:self.item[0], 2:4,
                                     3:None, 4:None, 5:None, 6:0})
        self.assertEqual(reply[1][0], OK)
        self.assertEqual(self.manager.snapshot(owner, reply[1][1][0])[0], PAUSED)

    def test_wrong_capability_is_denied(self):
        other = self.grants.issue(
            self.owner, provider="guide.media.session", interface_major=1,
            capability="media.library.browse", operations={10})
        reply, _ = self.exchange(10, {0:other.grant_id, 1:b"X"*16})
        self.assertEqual(reply[1][0], DENIED)


if __name__ == "__main__": unittest.main()
