from __future__ import annotations
import os, socket, sys, tempfile, threading, time, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"python"),str(ROOT/"generated"),str(ROOT/"reference"),str(ROOT.parent/"guide-supervisor"/"host")]
from guide_ipc import REQUEST, decode_packet, encode_packet, recv_packet, send_packet
from guide_grants import GrantError, GrantStore
from guide_instance_registry import InstanceContext, InstanceRegistry, ResolutionError
from health_broker import HealthBroker
from guide_ipc_interfaces import INTERFACES

class Fixture:
    def __init__(self,base):
        self.proc=Path(base)/"proc"; self.cg=Path(base)/"cgroup"; self.pid=os.getpid(); self.uid=os.getuid(); self.group=self.cg/"guide-app-test.service"
        (self.proc/str(self.pid)).mkdir(parents=True); self.group.mkdir(parents=True)
        (self.proc/str(self.pid)/"status").write_text(f"Name:\ttest\nUid:\t{self.uid}\t{self.uid}\t{self.uid}\t{self.uid}\n",encoding="ascii")
        (self.proc/str(self.pid)/"cgroup").write_text("0::/guide-app-test.service\n",encoding="ascii")
        self.context=InstanceContext("1"*32,1,"1001","main","guide-app-test.service",self.group,self.uid,3)
        self.registry=InstanceRegistry(proc_root=self.proc,cgroup_root=self.cg); self.registry.register(self.context); self.registry.set_reconciled(True)

class ProductionPrepTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.fx=Fixture(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_resolution_requires_reconciliation_and_exact_membership(self):
        other=InstanceRegistry(proc_root=self.fx.proc,cgroup_root=self.fx.cg); other.register(self.fx.context)
        with self.assertRaises(ResolutionError): other.resolve(self.fx.pid,self.fx.uid,os.getgid())
        peer=self.fx.registry.resolve(self.fx.pid,self.fx.uid,os.getgid())
        try: self.assertEqual(peer.context.instance_id,"1"*32)
        finally: os.close(peer.pidfd)
        (self.fx.proc/str(self.fx.pid)/"cgroup").write_text("0::/unregistered.service\n",encoding="ascii")
        with self.assertRaises(ResolutionError): self.fx.registry.resolve(self.fx.pid,self.fx.uid,os.getgid())
    def test_generation_advance_and_stale_retirement(self):
        newer=InstanceContext("1"*32,2,"1001","main","guide-app-test.service",self.fx.group,self.fx.uid,4); self.fx.registry.register(newer)
        with self.assertRaises(ResolutionError): self.fx.registry.retire("1"*32,1)
        self.fx.registry.retire("1"*32,2)
    def test_grant_binding_revocation_expiry_and_instance_invalidation(self):
        now=[100]; store=GrantStore(clock=lambda:now[0]); record=store.issue(self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operations={1},lifetime_ns=10)
        self.assertIs(store.validate(record.grant_id,self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operation=1),record)
        store.revoke(record.grant_id)
        with self.assertRaises(GrantError): store.validate(record.grant_id,self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operation=1)
        second=store.issue(self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operations={1},lifetime_ns=10); now[0]=111
        with self.assertRaises(GrantError): store.validate(second.grant_id,self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operation=1)
        self.assertTrue(store.invalidate_instance(self.fx.context.instance_id,self.fx.context.generation))
    def exchange(self,store,grant,interface_major=1):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET); errors=[]
        def server():
            try: HealthBroker(self.fx.registry,store).serve_connection(right)
            except Exception as exc: errors.append(exc)
            finally: right.close()
        thread=threading.Thread(target=server); thread.start()
        deadline=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+1_000_000_000
        send_packet(left,encode_packet(REQUEST,9,{0:1,1:{0:grant},2:deadline},interface_major=interface_major)); header,payload,fds=recv_packet(left); left.close(); thread.join(2)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors,[]); self.assertEqual(fds,[]); self.assertEqual(header.request_id,9); return payload
    def test_health_service_enforces_grant(self):
        store=GrantStore(); grant=store.issue(self.fx.context,provider="guide.broker.health",interface_major=1,capability="system.diagnostics.read",operations={1})
        payload=self.exchange(store,grant.grant_id); self.assertEqual(payload[0],0); self.assertEqual(payload[1][0],1)
        store.revoke(grant.grant_id); self.assertEqual(self.exchange(store,grant.grant_id)[0],6)
        self.assertEqual(self.exchange(store,grant.grant_id,interface_major=2)[0],4)

    def test_media_interfaces_are_versioned_and_separate(self):
        library=INTERFACES["guide.media.library"]
        session=INTERFACES["guide.media.session"]
        self.assertEqual((library["major"],library["minor"]),(1,0))
        self.assertEqual((session["major"],session["minor"]),(1,0))
        self.assertNotEqual(library["endpoint"],session["endpoint"])
        self.assertEqual(library["operations"][4]["name"],"OPEN")
        self.assertEqual(session["operations"][1]["name"],"OPEN")

    def test_media_view_never_receives_source_locator_or_descriptor(self):
        session=INTERFACES["guide.media.session"]
        for operation in session["operations"].values():
            names={field["name"] for field in operation["arguments"]+operation["result"]}
            self.assertFalse(names & {"locator","headers","path","ticket","source_private_record"})
        library_open=INTERFACES["guide.media.library"]["operations"][4]
        self.assertIn("source_private_record",{field["name"] for field in library_open["result"]})
        self.assertEqual((library_open["descriptor_min"],library_open["descriptor_max"]),(0,1))
        self.assertEqual(library_open["descriptors"],["media-read"])

    def test_media_watch_contract_has_resnapshot_events(self):
        library=INTERFACES["guide.media.library"]
        session=INTERFACES["guide.media.session"]
        self.assertTrue(library["operations"][5]["cancellable"])
        self.assertTrue(session["operations"][11]["cancellable"])
        self.assertIn("RESNAPSHOT_REQUIRED",{item["name"] for item in library["events"].values()})
        self.assertIn("RESNAPSHOT_REQUIRED",{item["name"] for item in session["events"].values()})

if __name__=="__main__": unittest.main()
