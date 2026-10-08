#!/usr/bin/python3
"""Client for Foundation's restricted provider-side grant validation."""
from __future__ import annotations
import os
from dataclasses import dataclass
import socket
import time

from guide_grants import GrantError
from guide_ipc import REQUEST, REPLY, encode_packet, recv_packet, send_packet

CAPABILITIES = {"media.library.browse": 6, "media.source.open": 7,
                "media.session.control": 8}


@dataclass(frozen=True)
class ValidatedOwner:
    instance_id: str
    generation: int


class ProviderGrantValidator:
    def __init__(self, endpoint="/run/guideos/brokers/provider.sock",
                 connector=None):
        self.endpoint = endpoint
        self.connector = connector or self._connect

    def _connect(self):
        value = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        value.settimeout(.5)
        value.connect(self.endpoint)
        return value

    def validate_peer(self, grant_id, peer, *, capability):
        code = CAPABILITIES.get(capability)
        if code is None:
            raise GrantError("unknown provider capability")
        connection = self.connector()
        try:
            deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 400_000_000
            arguments = {0: grant_id, 1: code, 2: peer.pid,
                         3: peer.uid, 4: peer.gid}
            send_packet(connection, encode_packet(
                REQUEST, 1, {0: 1, 1: arguments, 2: deadline},
                interface_major=1, interface_minor=0))
            header, payload, descriptors = recv_packet(connection)
            for descriptor in descriptors: os.close(descriptor)
            if descriptors or header.message_class != REPLY or header.interface_major != 1 or header.request_id != 1 or payload.get(0) != 0:
                raise GrantError("provider validation denied")
            body = payload.get(1)
            if (type(body) is not dict or body.get(0) != 1 or
                    type(body.get(1)) is not bytes or len(body.get(1)) != 16 or
                    type(body.get(2)) is not int or body.get(2) <= 0):
                raise GrantError("provider validation identity mismatch")
            context = getattr(peer, "context", None)
            if context is not None and (body.get(1) != bytes.fromhex(context.instance_id) or
                                        body.get(2) != context.generation):
                raise GrantError("provider validation identity mismatch")
            return ValidatedOwner(body[1].hex(), body[2])
        finally:
            connection.close()
