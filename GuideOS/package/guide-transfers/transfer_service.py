"""Private transfer UI protocol; no caller-selected privileged filesystem paths."""
import json,os,pwd,signal,socket,struct,sys,time
from pathlib import Path
sys.path[:0]=['/usr/lib/guideos/installer','/usr/lib/guideos/ipc']
from transfers import Transfers
SOCKET='/run/guideos-transfers/control.sock'

def request(op,**args):
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(2);s.connect(SOCKET);s.send(json.dumps(dict(op=op,**args)).encode())
        raw=s.recv(65536);response=json.loads(raw)
        if not response['ok']:raise ValueError(response['error'])
        return response['result']

def main():
    from guide_install_wire import call
    os.umask(0o077)
    def storage(op,args):
        result,fds=call('/run/guideos-storage/files.sock',op,args,timeout=10)
        if 'errorCode' in result:raise ValueError(result['errorCode'])
        return result,fds
    media_cache=[0,False]
    def should_yield():
        if time.monotonic()<media_cache[0]:return media_cache[1]
        media_cache[0]=time.monotonic()+.5
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as peer:
                peer.settimeout(.2);peer.connect('/run/guideos-player/control.sock')
                peer.send(b'{"action":"status"}')
                reply=json.loads(peer.recv(65536))
                media_cache[1]=reply.get('result',{}).get('state') in ('buffering','opening')
        except (OSError,ValueError):media_cache[1]=False
        return media_cache[1]
    manager=Transfers('/var/lib/guideos-transfers',storage,should_yield)
    browser=pwd.getpwnam('guide-browser').pw_uid
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    Path(SOCKET).unlink(missing_ok=True);listener.bind(SOCKET);os.chown(SOCKET,0,pwd.getpwnam('guide-browser').pw_gid);os.chmod(SOCKET,0o660);listener.listen(4);listener.settimeout(.5)
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop)
    try:
        while not stopped:
            try:conn,_=listener.accept()
            except socket.timeout:continue
            with conn:
                conn.settimeout(.5)
                try:
                    _,uid,_=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid not in (0,browser):raise ValueError('unauthorized')
                    raw,_,flags,_=conn.recvmsg(32768)
                    if flags&socket.MSG_TRUNC:raise ValueError('request-limit')
                    a=json.loads(raw);op=a.pop('op')
                    if op=='snapshot':result=manager.snapshot(uid,a.get('offset',0))
                    elif op=='locations':result,_=manager.storage(1,{})
                    elif op=='list':result,_=manager.storage(2,a)
                    elif op=='offer':result=manager.offer(a['source'],a['name'],uid,a.get('cookies'))
                    elif op=='start':result=manager.start(a['id'],a['folder'],a['collision'],uid)
                    elif op=='cancel':result=manager.cancel(a['id'],uid)
                    else:raise ValueError('unsupported-operation')
                    response=dict(ok=True,result=result)
                except Exception:response=dict(ok=False,error='Unavailable or changed; refresh and try again.')
                try:conn.send(json.dumps(response).encode())
                except OSError:pass
    finally:listener.close();manager.close()

if __name__=='__main__':main()
