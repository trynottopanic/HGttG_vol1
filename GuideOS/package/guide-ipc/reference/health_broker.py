"""Harmless Envelope 0 reference broker: bounded health metadata only."""
from __future__ import annotations
import os, socket, struct, time
from guide_ipc import REQUEST, REPLY, ProtocolError, encode_packet, recv_packet, send_packet
from guide_grants import GrantError
from guide_ipc_interfaces import INTERFACES

INTERFACE="guide.broker.health"; OP_SNAPSHOT=1
OK=0; INVALID_ARGUMENT=2; INCOMPATIBLE_INTERFACE=4; DENIED=6; DEADLINE_EXCEEDED=16; INTERNAL_ERROR=18

class HealthBroker:
    def __init__(self,resolver,grants): self.resolver=resolver; self.grants=grants
    def _reply(self,connection,request_id,outcome,body): send_packet(connection,encode_packet(REPLY,request_id,{0:outcome,1:body}))
    def serve_connection(self,connection):
        raw=connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize("3i"))
        pid,uid,gid=struct.unpack("3i",raw); peer=self.resolver.resolve(pid,uid,gid)
        descriptors=[]
        try:
            header,payload,descriptors=recv_packet(connection)
            spec=INTERFACES[INTERFACE]
            if header.interface_major != spec["major"] or header.interface_minor > spec["minor"]:
                self._reply(connection,header.request_id,INCOMPATIBLE_INTERFACE,{0:1}); return
            if descriptors or header.message_class != REQUEST or set(payload) != {0,1,2} or type(payload[0]) is not int or type(payload[1]) is not dict or type(payload[2]) is not int:
                self._reply(connection,header.request_id,INVALID_ARGUMENT,{0:1}); return
            now=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            if payload[2] > now + 300_000_000_000:
                self._reply(connection,header.request_id,INVALID_ARGUMENT,{0:3}); return
            if payload[2] < now:
                self._reply(connection,header.request_id,DEADLINE_EXCEEDED,{0:1}); return
            if payload[0] != OP_SNAPSHOT or set(payload[1]) != {0}:
                self._reply(connection,header.request_id,INVALID_ARGUMENT,{0:2}); return
            self.grants.validate(payload[1][0],peer.context,provider=INTERFACE,interface_major=1,capability="system.diagnostics.read",operation=OP_SNAPSHOT)
            self._reply(connection,header.request_id,OK,{0:1,1:self.grants.revision})
        except GrantError:
            self._reply(connection,header.request_id,DENIED,{0:1})
        finally:
            for descriptor in descriptors: os.close(descriptor)
            os.close(peer.pidfd)
