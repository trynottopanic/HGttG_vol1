import errno
import os
from pathlib import Path
import socket
import tempfile
import unittest
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'python'),str(Path(__file__).resolve().parents[2]/'guide-ipc/python')]
from guide_application_runtime import *

class FakeBroker:
    def __init__(self):self.grants={}
    def acquire(self,cap):
        token=os.urandom(16);self.grants[token]=cap;return token
    def valid(self,token,cap):
        if self.grants.get(token)!=cap:raise PermissionError('denied')
    def release(self,token):self.grants.pop(token,None)
    def renew(self,token,cap):self.valid(token,cap)

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=PrivateStore(self.temp.name,524288)
        self.broker=FakeBroker();self.session=Session({'mask':30},self.store,self.broker)
    def tearDown(self):self.store.close();self.temp.cleanup()
    def acquire(self,cap):return self.session.dispatch(1,{0:cap})[0]
    def test_media_grants_require_installed_policy(self):
        for cap in (6,7,8):
            with self.assertRaises(PermissionError):self.acquire(cap)
        self.session.policy['mask']=254
        for cap in (6,7,8):
            token=self.acquire(cap);self.session.valid(token,cap)
            self.session.release(token)
            with self.assertRaises(PermissionError):self.session.valid(token,cap)
        with self.assertRaises(PermissionError):self.acquire(9)
    def test_scope_release_restart(self):
        private=self.acquire(2);visual=self.acquire(3)
        with self.assertRaises(PermissionError):self.session.dispatch(7,{0:visual,1:'checkpoint'})
        self.session.dispatch(2,{0:visual});self.session.dispatch(2,{0:visual})
        self.session.dispatch(8,{0:private,1:'draft',2:'retained'})
        with self.assertRaises(PermissionError):self.session.valid(visual,3)
        self.broker.grants.clear()
        with self.assertRaises(PermissionError):self.session.valid(private,2)
    def test_denied_declaration_and_cross_instance(self):
        self.session.policy['mask']=2
        with self.assertRaises(PermissionError):self.acquire(3)
        token=self.acquire(2)
        other=Session({'mask':30},self.store,self.broker)
        with self.assertRaises(PermissionError):other.dispatch(7,{0:token,1:'draft'})
    def test_checkpoint_needs_new_durable_checkpoint_write(self):
        private=self.acquire(2);receipt=self.session.dispatch(8,{0:private,1:'checkpoint',2:'old'})[0]
        self.session.shell(4,{})
        with self.assertRaises(ValueError):self.session.dispatch(9,{0:receipt})
        receipt=self.session.dispatch(8,{0:private,1:'draft',2:'wrong object'})[0]
        with self.assertRaises(ValueError):self.session.dispatch(9,{0:receipt})
        receipt=self.session.dispatch(8,{0:private,1:'checkpoint',2:'new'})[0]
        self.session.dispatch(9,{0:receipt});self.assertEqual(self.session.checkpoint,'durable')
        self.assertEqual(self.store.read('checkpoint'),'new')
    def test_atomic_write_failure_keeps_prior(self):
        self.store.write('checkpoint','old')
        from unittest.mock import patch
        with patch('os.replace',side_effect=OSError('fault')):
            with self.assertRaises(OSError):self.store.write('checkpoint','new')
        self.assertEqual(self.store.read('checkpoint'),'old')
        self.store.close();self.store=PrivateStore(self.temp.name,524288)
        self.assertEqual(self.store.read('checkpoint'),'old')
        self.assertFalse((Path(self.temp.name)/'.pending').exists())
    def test_quota_and_paths(self):
        self.store.quota=10;self.store.write('draft','123456')
        with self.assertRaises(ValueError):self.store.write('draft','abcde')
        for key in ('../x','/x','a/b','.pending','x'*33):
            with self.assertRaises(ValueError):self.store.write(key,'data')
        os.symlink('/etc/passwd',Path(self.temp.name)/'link')
        with self.assertRaises(OSError):self.store.read('link')
    def test_revocation_clears_view_and_text(self):
        visual=self.acquire(3);text=self.acquire(5)
        self.session.dispatch(4,{0:visual,1:'title',2:'body',3:['edit']})
        self.session.dispatch(6,{0:text,1:'',2:128})
        self.session.shell(5,{0:3});self.assertIsNone(self.session.view)
        self.assertIsNotNone(self.session.text_request)
        self.broker.grants.clear();snapshot=self.session.shell(1,{})
        self.assertIsNone(snapshot[2])
    def test_input_bounds_and_focus(self):
        visual=self.acquire(3);text=self.acquire(5);actions=self.acquire(4)
        self.session.dispatch(4,{0:visual,1:'title',2:'body',3:['edit']})
        self.session.shell(2,{0:0});self.assertEqual(self.session.dispatch(5,{}),{0:1,1:0})
        self.session.dispatch(6,{0:text,1:'seed',2:10})
        with self.assertRaises(ValueError):self.session.shell(3,{0:'x'*11})
        self.session.shell(3,{0:'new'});self.assertEqual(self.session.dispatch(5,{}),{0:2,1:'new'})
        with self.assertRaises(ValueError):self.session.shell(3,{0:'stale result'})
        self.session.release(actions)
        with self.assertRaises(PermissionError):self.session.shell(2,{0:0})
    def test_renewal_keeps_live_grants_but_does_not_regrant_revocation(self):
        visual=self.acquire(3)
        self.session.dispatch(4,{0:visual,1:'title',2:'body',3:[]})
        self.session.next_renew=0;self.session.maintain();self.session.valid(visual,3)
        self.broker.grants.clear();self.session.next_renew=0;self.session.maintain()
        self.assertIsNone(self.session.view)
        with self.assertRaises(PermissionError):self.session.valid(visual,3)
        self.assertEqual(self.broker.grants,{})
    def test_kernel_denies_ambient_authority(self):
        a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        pid=os.fork()
        if pid==0:
            a.close()
            try:
                sandbox(b)
                denied=0
                for action in (lambda:os.open('/etc/passwd',os.O_RDONLY),lambda:socket.socket(socket.AF_INET,socket.SOCK_STREAM),lambda:os.fork(),lambda:os.execv('/bin/true',['true']),lambda:os.open('/dev/null',os.O_WRONLY),lambda:os.kill(os.getppid(),0)):
                    try:action()
                    except OSError as e:
                        if e.errno==errno.EPERM:denied+=1
                b.send(str(denied).encode());os._exit(0)
            except BaseException:os._exit(90)
        b.close();a.settimeout(2)
        try:self.assertEqual(a.recv(100),b'6')
        finally:
            _,status=os.waitpid(pid,0);a.close()
        self.assertEqual(status,0)

    def test_extended_views_are_atomic_bounded_and_revocable(self):
        visual=self.acquire(3)
        actions=['New note']+['Note '+str(i) for i in range(16)]
        meta={0:'notes',1:'Internal drafts',4:['']*17}
        self.session.dispatch(4,{0:visual,1:'Notepad',2:'',3:actions,4:meta})
        prior=self.session.view.copy()
        invalid=[{0:'notes',1:'Internal',4:[]},{0:'document',1:'Note',2:'Internal',3:'saved',5:{0:0},6:''},
                 {0:'menu',5:{3:99}},{0:'notes',1:'Internal',4:['x\n']*17}]
        for value in invalid:
            with self.assertRaises(ValueError):self.session.dispatch(4,{0:visual,1:'Notepad',2:'',3:actions[:4] if value[0]!='notes' else actions,4:value})
            self.assertEqual(self.session.view,prior)
        with self.assertRaises(ValueError):self.session.dispatch(4,{0:visual,1:'Notepad',2:'',3:[],4:{0:'notes',1:'Internal',4:[]}})
        self.session.shell(5,{0:3});self.assertIsNone(self.session.view)

    def test_single_line_validation_and_caret_do_not_consume_failed_request(self):
        text=self.acquire(5)
        self.session.dispatch(6,{0:text,1:'First',2:32,3:{0:'Note name',1:False,2:2,3:'Save'}})
        for args in ({0:'new\nname',2:2},{0:'new',2:4},{0:'new',2:True},{0:'new',1:1}):
            with self.assertRaises(ValueError):self.session.shell(3,args)
            self.assertIsNotNone(self.session.text_request)
        self.session.shell(3,{0:'Name',2:2});self.assertEqual(self.session.dispatch(5,{}),{0:2,1:'Name',3:2})

    def test_real_socket_roundtrip_extended_document_and_interrupted_caret(self):
        import threading
        client_sock,host_sock=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        errors=[]
        def host():
            try:
                for _ in range(5):serve(host_sock,self.session.dispatch)
            except BaseException as exc:errors.append(exc)
        worker=threading.Thread(target=host);worker.start()
        try:
            client=Client(client_sock);visual=client.acquire(3);text=client.acquire(5)
            body='😀'*5120;meta={0:'document',1:'Note',2:'Internal draft',3:'unsaved',5:{0:0,1:1,2:2,3:3},6:''}
            client.present(visual,'Notepad',body,['Edit','Save','Actions','Close'],meta)
            client.text(text,body,5120,label='Note text',multiline=True,caret=17)
            snapshot=self.session.shell(1,{})
            self.assertEqual(snapshot[1][1],body);self.assertEqual(snapshot[2][2][2],17)
            self.session.shell(3,{0:body,1:True,2:23});self.session.shell(4,{})
            self.assertEqual(client.event(),{0:2,1:body,2:True,3:23})
        finally:
            worker.join(2);client_sock.close();host_sock.close()
        self.assertFalse(worker.is_alive());self.assertEqual(errors,[])

if __name__=='__main__':unittest.main()
