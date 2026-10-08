"""Bounded Envelope 0 JSON control records for installer and storage owner."""
import json, os, socket, struct, time
from guide_ipc import REQUEST, REPLY, encode_packet, send_packet, recv_packet, ProtocolError
from guide_cartridge import canonical, json_read, require
INSTALLER='/run/guideos/installer/control.sock'
CATALOG='/run/guideos-storage/cartridges.sock'
def now():return time.clock_gettime_ns(time.CLOCK_BOOTTIME)
def call(path,op,args=None,*,timeout=.8):
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        require(isinstance(timeout,(int,float)) and 0<timeout<=10,'response timeout')
        s.settimeout(timeout);s.connect(path)
        send_packet(s,encode_packet(REQUEST,1,{0:op,1:{0:canonical(args or {})},2:now()+2_000_000_000}))
        h,p,fds=recv_packet(s)
        try:
            require(h.message_class==REPLY and h.request_id==1 and h.interface_major==1,'reply correlation')
            result=json_read(p[1][0])
            if p[0]!=0:raise ValueError(result.get('error','operation denied'))
            return result,fds
        except BaseException:
            for fd in fds:os.close(fd)
            raise

def serve(peer,handler):
    peer.settimeout(.15);fds=[]
    try:
        _,uid,_=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        require(uid==0,'owner-only control')
        h,p,fds=recv_packet(peer)
        require(not fds and h.message_class==REQUEST and h.interface_major==1 and set(p)=={0,1,2} and type(p[0])is int and type(p[2])is int and now()<p[2]<=now()+3_000_000_000 and type(p[1])is dict and set(p[1])=={0} and type(p[1][0])is bytes,'request envelope')
        args=json_read(p[1][0])
        try:result,outfds=handler(p[0],args);outcome=0
        except (ValueError,OSError,KeyError,TypeError):result={'error':'Unavailable or changed; refresh and try again.'};outfds=[];outcome=6
        try:send_packet(peer,encode_packet(REPLY,h.request_id,{0:outcome,1:{0:canonical(result)}},descriptor_count=len(outfds)),outfds)
        finally:
            for fd in outfds:os.close(fd)
    finally:
        for fd in fds:os.close(fd)
