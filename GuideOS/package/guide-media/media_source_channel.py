"""Private storage-to-session descriptor channel; never an application API."""
import os
import pwd
import socket
import struct
import stat
import time
from pathlib import Path
from guide_ipc import REQUEST, REPLY, encode_packet, recv_packet, send_packet

PATH = '/run/guideos-storage/media-source.sock'


def provider_peer(connection):
    pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != pwd.getpwnam('guide-audio').pw_uid:
        raise PermissionError('source provider identity')
    pidfd = os.pidfd_open(pid)
    try:
        groups = Path('/proc/%d/cgroup' % pid).read_text().splitlines()
        if '0::/system.slice/guide-media-player.service' not in groups:
            raise PermissionError('source provider service')
    finally:
        os.close(pidfd)


class SourceEndpoint:
    def __init__(self, catalog, path=PATH, authorize=provider_peer):
        self.catalog, self.path, self.authorize = catalog, Path(path), authorize
        if self.path.exists():
            if not stat.S_ISSOCK(self.path.lstat().st_mode):raise RuntimeError('source socket path conflict')
            self.path.unlink()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.listener.bind(str(path))
        os.chmod(path, 0o660)
        import grp
        os.chown(path, 0, grp.getgrnam('audio').gr_gid)
        self.listener.listen(4); self.listener.setblocking(False)

    def poll(self):
        connection, _ = self.listener.accept()
        fd = None; received = []
        try:
            connection.settimeout(.2)
            self.authorize(connection)
            header, payload, received = recv_packet(connection)
            if received or header.message_class != REQUEST or header.interface_major != 1:
                raise ValueError('invalid source message')
            op, args, deadline = payload[0], payload[1], payload[2]
            now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            if not now < deadline <= now + 2_000_000_000:raise ValueError('source deadline')
            if op == 1 and not args: result = self.catalog.snapshot()
            elif op == 2 and set(args) == {0,1}:
                result = self.catalog.list(after_media_id=args[0], limit=32, media_kind=args[1])
            elif op in (3,4) and set(args) == {0,1}:
                result = self.catalog.describe(args[0], args[1])
                if op == 4:fd = self.catalog.open_local(args[0],args[1])
            else:raise ValueError('invalid source operation')
            send_packet(connection,encode_packet(REPLY,header.request_id,{0:0,1:result},int(fd is not None)),
                        [] if fd is None else [fd])
        except (OSError,ValueError,KeyError,TypeError,RuntimeError):
            try:send_packet(connection,encode_packet(REPLY,1,{0:11,1:{}}))
            except OSError:pass
        finally:
            if fd is not None:os.close(fd)
            for value in received:os.close(value)
            connection.close()

    def close(self):
        self.listener.close()
        self.path.unlink(missing_ok=True)


class SourceClient:
    def __init__(self,path=PATH):self.path=path
    def request(self,op,args):
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as connection:
            connection.settimeout(.5);connection.connect(self.path)
            send_packet(connection,encode_packet(REQUEST,1,{0:op,1:args,
                2:time.clock_gettime_ns(time.CLOCK_BOOTTIME)+450_000_000}))
            header,payload,fds=recv_packet(connection)
        if header.message_class!=REPLY or payload.get(0)!=0 or len(fds)!=(1 if op==4 else 0):
            for fd in fds:os.close(fd)
            raise RuntimeError('Media source is unavailable or changed')
        return payload[1],fds
    def snapshot(self):return self.request(1,{})[0]
    def list(self,after=None,kind=None):return self.request(2,{0:after,1:kind})[0]
    def describe(self,identity,generation):return self.request(3,{0:identity,1:generation})[0]
    def open_local(self,identity,generation):return self.request(4,{0:identity,1:generation})[1][0]
