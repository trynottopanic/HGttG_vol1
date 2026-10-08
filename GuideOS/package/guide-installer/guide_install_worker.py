#!/usr/bin/python3 -I
"""One bounded archive request, under an unprivileged systemd service."""
import ctypes,errno,os,re,resource,socket,struct,sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent),'/usr/lib/guideos/ipc']
from guide_cartridge import verify,canonical,json_read,require
from guide_ipc import REQUEST,REPLY,encode_packet,send_packet,recv_packet
from guide_install_wire import now

def restrict():
    require(os.geteuid()!=0,'parser must be unprivileged')
    sec=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    sec.seccomp_init.argtypes=[ctypes.c_uint32];sec.seccomp_init.restype=ctypes.c_void_p
    sec.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];sec.seccomp_syscall_resolve_name.restype=ctypes.c_int
    sec.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    sec.seccomp_load.argtypes=[ctypes.c_void_p];sec.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=sec.seccomp_init(0x7fff0000);require(bool(ctx),'parser sandbox')
    try:
        for name in 'execve execveat fork vfork clone clone3 socket connect ptrace process_vm_readv process_vm_writev mount umount2 unshare setns setuid setgid setresuid setresgid setgroups'.split():
            number=sec.seccomp_syscall_resolve_name(name.encode())
            if number>=0:require(sec.seccomp_rule_add(ctx,0x00050000|errno.EPERM,number,0)>=0,'parser sandbox rule')
        require(sec.seccomp_load(ctx)>=0,'parser sandbox load')
    finally:sec.seccomp_release(ctx)
    resource.setrlimit(resource.RLIMIT_AS,(96*1024*1024,96*1024*1024))
    resource.setrlimit(resource.RLIMIT_FSIZE,(2097152,2097152))
    resource.setrlimit(resource.RLIMIT_NPROC,(0,0))

def main():
    listener=socket.socket(fileno=3);listener.settimeout(10)
    peer,_=listener.accept();listener.close();fds=[]
    with peer:
        peer.settimeout(12)
        require(struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]==0,'parser owner')
        h,p,fds=recv_packet(peer)
        try:
            require(h.message_class==REQUEST and h.interface_major==1 and set(p)=={0,1,2} and p[0]==1 and type(p[2])is int and now()<p[2]<=now()+15_000_000_000 and len(fds)==1,'parser request')
            args=json_read(p[1][0]);require(set(args)=={'sha256','transaction'} and re.fullmatch(r'[a-f0-9]{64}',args['sha256']),'parser arguments')
            transaction=args['transaction'];require(transaction is None or re.fullmatch(r'[a-f0-9]{32}',transaction),'parser transaction')
            target=Path('/var/lib/guideos/installer/staging')/transaction/'release' if transaction else None
            restrict()
            with os.fdopen(fds.pop(),'rb') as stream:result=verify(stream,args['sha256'],target)
            encoded=canonical(result);require(len(encoded)<=24576,'parser result bound')
            send_packet(peer,encode_packet(REPLY,h.request_id,{0:0,1:{0:encoded}}))
        except Exception:
            send_packet(peer,encode_packet(REPLY,h.request_id,{0:6,1:{0:b'{"error":"Invalid cartridge"}'}}))
        finally:
            for fd in fds:os.close(fd)
if __name__=='__main__':main()
