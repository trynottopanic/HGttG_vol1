#!/usr/bin/python3
"""Envelope 0 broker for the first read-only storage media catalog."""
from __future__ import annotations

import os
import socket
import struct
import time

from guide_grants import GrantError
from guide_ipc import EVENT, REQUEST, REPLY, encode_packet, recv_packet, send_packet
from guide_ipc_interfaces import INTERFACES
from media_library import MediaNotFound, StaleMedia

INTERFACE = "guide.media.library"
OP_SNAPSHOT, OP_LIST, OP_DESCRIBE, OP_OPEN, OP_WATCH = range(1, 6)
OK = 0
INVALID_ARGUMENT = 2
UNSUPPORTED_OPERATION = 3
INCOMPATIBLE_INTERFACE = 4
DENIED = 6
NOT_FOUND = 8
STALE = 11
DEADLINE_EXCEEDED = 16
INTERNAL_ERROR = 18


class MediaLibraryBroker:
    def __init__(self, catalog, resolver, grants, watch=None):
        self.watch = watch
        self.catalog = catalog
        self.resolver = resolver
        self.grants = grants

    @staticmethod
    def _reply(connection, request_id, outcome, body, descriptors=None):
        descriptors = descriptors or []
        packet = encode_packet(REPLY, request_id, {0: outcome, 1: body},
                               len(descriptors), interface_major=1, interface_minor=0)
        send_packet(connection, packet, descriptors)

    @staticmethod
    def _request(payload):
        if (type(payload) is not dict or set(payload) != {0, 1, 2} or
                type(payload.get(0)) is not int or type(payload.get(1)) is not dict or
                type(payload.get(2)) is not int):
            raise ValueError("invalid request envelope")
        return payload[0], payload[1], payload[2]

    def serve_connection(self, connection):
        raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                    struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", raw)
        peer = None
        descriptors = []
        request_id = 1
        try:
            peer = self.resolver.resolve(pid, uid, gid)
            header, payload, descriptors = recv_packet(connection)
            request_id = header.request_id
            spec = INTERFACES[INTERFACE]
            if header.interface_major != spec["major"] or header.interface_minor > spec["minor"]:
                self._reply(connection, request_id, INCOMPATIBLE_INTERFACE, {0: 1})
                return
            if descriptors or header.message_class != REQUEST:
                self._reply(connection, request_id, INVALID_ARGUMENT, {0: 1})
                return
            operation, arguments, deadline = self._request(payload)
            now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            if deadline > now + 300_000_000_000:
                raise ValueError("deadline too distant")
            if deadline < now:
                self._reply(connection, request_id, DEADLINE_EXCEEDED, {0: 1})
                return
            if operation not in (OP_SNAPSHOT, OP_LIST, OP_DESCRIBE, OP_OPEN, OP_WATCH):
                self._reply(connection, request_id, UNSUPPORTED_OPERATION, {0: 1})
                return
            grant_id = arguments.get(0)
            capability = "media.source.open" if operation == OP_OPEN else "media.library.browse"
            if hasattr(self.grants, "validate_peer"):
                self.grants.validate_peer(grant_id, peer, capability=capability)
            else:
                self.grants.validate(grant_id, peer.context, provider=INTERFACE,
                                     interface_major=1, capability=capability,
                                     operation=operation)
            if operation == OP_WATCH:
                if set(arguments)!={0,1} or type(arguments[1]) is not int or not 0<=arguments[1]<=self.catalog.library_revision:
                    raise ValueError('invalid watch revision')
                if self.watch is None:
                    self._reply(connection, request_id, UNSUPPORTED_OPERATION, {0: 2});return
                if not self.watch(connection,peer,grant_id,deadline,arguments[1],request_id):
                    self._reply(connection,request_id,14,{0:1});return
                peer=None  # endpoint owns the pinned peer and connection now
                return True
            if operation == OP_SNAPSHOT:
                if set(arguments) != {0}:
                    raise ValueError("invalid snapshot fields")
                self._reply(connection, request_id, OK, self.catalog.snapshot())
            elif operation == OP_LIST:
                if set(arguments) != {0, 1, 2, 3, 4, 5}:
                    raise ValueError("invalid list fields")
                body = self.catalog.list(after_media_id=arguments[1], limit=arguments[2],
                                         source_class=arguments[3], media_kind=arguments[4],
                                         source_id=arguments[5])
                self._reply(connection, request_id, OK, body)
            elif operation == OP_DESCRIBE:
                if set(arguments) != {0, 1, 2}:
                    raise ValueError("invalid describe fields")
                self._reply(connection, request_id, OK,
                            self.catalog.describe(arguments[1], arguments[2]))
            else:
                if set(arguments) != {0, 1, 2, 3, 4}:
                    raise ValueError("invalid open fields")
                if arguments[3] is not None or arguments[4] is not None:
                    raise ValueError("first storage slice has no selectable tracks")
                descriptor = self.catalog.open_local(arguments[1], arguments[2])
                try:
                    body = {0: os.urandom(16), 1: 1, 2: None, 3: 0}
                    self._reply(connection, request_id, OK, body, [descriptor])
                finally:
                    os.close(descriptor)
        except GrantError:
            self._reply(connection, request_id, DENIED, {0: 1})
        except StaleMedia:
            self._reply(connection, request_id, STALE, {0: 1})
        except MediaNotFound:
            self._reply(connection, request_id, NOT_FOUND, {0: 1})
        except ValueError:
            self._reply(connection, request_id, INVALID_ARGUMENT, {0: 1})
        except Exception:
            self._reply(connection, request_id, INTERNAL_ERROR, {0: 1})
        finally:
            for descriptor in descriptors:
                os.close(descriptor)
            if peer is not None:
                os.close(peer.pidfd)
