"""Private bounded frontend channel. No website-to-host bridge."""
import json
import os
import socket
import struct
from gi.repository import GLib

class ControlServer:
    def __init__(self, path, dispatch):
        self.path, self.dispatch = path, dispatch
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.socket.bind(path)
        os.chmod(path, 0o600)
        self.socket.listen(2)
        self.socket.setblocking(False)
        self.clients = {}
        self.watch = GLib.io_add_watch(self.socket.fileno(), GLib.IO_IN, self.accept)

    def accept(self, *_):
        conn, _ = self.socket.accept()
        uid = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
        if uid not in (0, os.getuid()):
            conn.close()
            return True
        conn.setblocking(False)
        watch = GLib.io_add_watch(conn.fileno(), GLib.IO_IN | GLib.IO_HUP, self.receive, conn)
        self.clients[conn.fileno()] = (conn, watch)
        return True

    def receive(self, _fd, _condition, conn):
        try:
            raw, _anc, flags, _addr = conn.recvmsg(8192)
            if not raw or flags & socket.MSG_TRUNC:
                raise ValueError('invalid packet')
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError('invalid request')
            response = self.dispatch(request)
            conn.send(json.dumps(response).encode())
            return True
        except (OSError, ValueError, KeyError, TypeError):
            self.clients.pop(conn.fileno(), None)
            conn.close()
            return False

    def close(self):
        GLib.source_remove(self.watch)
        for conn, watch in self.clients.values():
            GLib.source_remove(watch)
            conn.close()
        self.clients.clear()
        self.socket.close()
        os.unlink(self.path)
