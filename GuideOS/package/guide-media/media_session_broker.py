#!/usr/bin/python3
"""Envelope 0 broker for the Media Session 1 state machine."""
from __future__ import annotations

import os
import socket
import struct
import time

from guide_grants import GrantError
from guide_ipc import EVENT, REQUEST, REPLY, encode_packet, recv_packet, send_packet
from guide_ipc_interfaces import INTERFACES
from media_session import (InvalidTransition, ResourceDenied, SessionNotFound,
                           StaleSession, WrongOwner)

INTERFACE = "guide.media.session"
OK, INVALID_ARGUMENT, UNSUPPORTED_OPERATION, INCOMPATIBLE_INTERFACE = 0, 2, 3, 4
FAILED_PRECONDITION, DENIED, NOT_FOUND, STALE = 5, 6, 8, 11
RESOURCE_EXHAUSTED, DEADLINE_EXCEEDED, PROVIDER_FAILED = 14, 16, 17


class MediaSessionBroker:
    def __init__(self, manager, resolver, grants):
        self.manager = manager
        self.resolver = resolver
        self.grants = grants

    @staticmethod
    def _send(connection, message_class, request_id, payload):
        send_packet(connection, encode_packet(message_class, request_id, payload,
                    interface_major=1, interface_minor=0))

    @classmethod
    def _reply(cls, connection, request_id, outcome, body):
        cls._send(connection, REPLY, request_id, {0: outcome, 1: body})

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
        peer = self.resolver.resolve(pid, uid, gid)
        descriptors = []
        request_id = 1
        try:
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
            if operation not in range(1, 12):
                self._reply(connection, request_id, UNSUPPORTED_OPERATION, {0: 1})
                return
            grant_id = arguments.get(0)
            if hasattr(self.grants, "validate_peer"):
                context = self.grants.validate_peer(grant_id, peer,
                                          capability="media.session.control")
            else:
                context = peer.context
                self.grants.validate(grant_id, peer.context, provider=INTERFACE,
                                     interface_major=1,
                                     capability="media.session.control",
                                     operation=operation)
            result = self._dispatch(context, operation, arguments)
            if operation == 11:
                revision, events = result
                self._reply(connection, request_id, OK, {0: revision})
                for _, event_code, body in events:
                    self._send(connection, EVENT, 0, {0: event_code, 1: body})
            else:
                self._reply(connection, request_id, OK, result)
        except GrantError:
            self._reply(connection, request_id, DENIED, {0: 1})
        except WrongOwner:
            self._reply(connection, request_id, DENIED, {0: 2})
        except SessionNotFound:
            self._reply(connection, request_id, NOT_FOUND, {0: 1})
        except StaleSession:
            self._reply(connection, request_id, STALE, {0: 1})
        except InvalidTransition:
            self._reply(connection, request_id, FAILED_PRECONDITION, {0: 1})
        except ResourceDenied:
            self._reply(connection, request_id, RESOURCE_EXHAUSTED, {0: 1})
        except ValueError:
            self._reply(connection, request_id, INVALID_ARGUMENT, {0: 1})
        except Exception:
            self._reply(connection, request_id, PROVIDER_FAILED, {0: 1})
        finally:
            for descriptor in descriptors:
                os.close(descriptor)
            os.close(peer.pidfd)

    def _dispatch(self, context, operation, arguments):
        fields = {1: set(range(7)), 2: {0, 1, 2}, 3: {0, 1, 2},
                  4: {0, 1, 2, 3}, 5: {0, 1, 2, 3}, 6: {0, 1, 2, 3},
                  7: {0, 1, 2, 3}, 8: {0, 1, 2}, 9: {0, 1, 2},
                  10: {0, 1}, 11: {0, 1, 2}}
        if set(arguments) != fields[operation]:
            raise ValueError("invalid operation fields")
        if operation == 1:
            return self.manager.open(
                context, arguments[1], arguments[2], audio_track=arguments[3],
                subtitle_track=arguments[4], output_id=arguments[5],
                resume_position_ms=arguments[6] if arguments[6] is not None else 0)
        if operation == 2: return self.manager.play(context, arguments[1], arguments[2])
        if operation == 3: return self.manager.pause(context, arguments[1], arguments[2])
        if operation == 4: return self.manager.seek(context, arguments[1], arguments[2], arguments[3])
        if operation == 5: return self.manager.select_audio(context, arguments[1], arguments[2], arguments[3])
        if operation == 6: return self.manager.select_subtitle(context, arguments[1], arguments[2], arguments[3])
        if operation == 7: return self.manager.set_output(context, arguments[1], arguments[2], arguments[3])
        if operation == 8: return self.manager.checkpoint(context, arguments[1], arguments[2])
        if operation == 9: return self.manager.stop(context, arguments[1], arguments[2])
        if operation == 10: return self.manager.snapshot(context, arguments[1])
        session = self.manager._get(context, arguments[1])
        return session.revision, self.manager.events_after(context, arguments[1], arguments[2])
