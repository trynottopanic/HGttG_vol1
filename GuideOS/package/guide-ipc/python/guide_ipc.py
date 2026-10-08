"""GuideOS IPC Envelope 0 compatibility-spike codec."""
from __future__ import annotations

import dataclasses
import os
import socket
import struct
from typing import Any

import cbor2

MAGIC = b"GIPC"
HEADER = struct.Struct(">4sBBBBHHQHBB")
HEADER_SIZE = 24
MAX_PAYLOAD = 32768
MAX_PACKET = HEADER_SIZE + MAX_PAYLOAD
MAX_DESCRIPTORS = 4
MAX_DEPTH = 6
MAX_MAP = 32
MAX_ARRAY = 64
MAX_VALUES = 256
MAX_STRING = 24576
ENVELOPE_MAJOR = 1
ENVELOPE_MINOR = 0
INTERFACE_MAJOR = 1
INTERFACE_MINOR = 0
REQUEST, REPLY, EVENT, CANCEL = 1, 2, 3, 4


class ProtocolError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class Header:
    message_class: int
    request_id: int
    payload_length: int
    descriptor_count: int = 0
    envelope_major: int = ENVELOPE_MAJOR
    envelope_minor: int = ENVELOPE_MINOR
    flags: int = 0
    interface_major: int = INTERFACE_MAJOR
    interface_minor: int = INTERFACE_MINOR
    reserved: int = 0


class _Cursor:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.values = 0

    def take(self, amount: int) -> bytes:
        end = self.pos + amount
        if amount < 0 or end > len(self.data):
            raise ProtocolError("truncated CBOR")
        value = self.data[self.pos:end]
        self.pos = end
        return value

    def head(self) -> tuple[int, int]:
        initial = self.take(1)[0]
        major, ai = initial >> 5, initial & 31
        if ai < 24:
            return major, ai
        widths = {24: 1, 25: 2, 26: 4, 27: 8}
        if ai not in widths:
            raise ProtocolError("indefinite or reserved CBOR length")
        raw = self.take(widths[ai])
        value = int.from_bytes(raw, "big")
        minimum = {24: 24, 25: 256, 26: 65536, 27: 1 << 32}[ai]
        if value < minimum:
            raise ProtocolError("nonminimal CBOR integer or length")
        return major, value

    def item(self, depth: int = 1) -> None:
        if depth > MAX_DEPTH:
            raise ProtocolError("CBOR nesting limit")
        self.values += 1
        if self.values > MAX_VALUES:
            raise ProtocolError("CBOR value-count limit")
        major, value = self.head()
        if major == 0:
            return
        if major == 1:
            if value > (1 << 63) - 1:
                raise ProtocolError("negative integer outside int64")
            return
        if major in (2, 3):
            if value > MAX_STRING:
                raise ProtocolError("CBOR string limit")
            raw = self.take(value)
            if major == 3:
                try:
                    raw.decode("utf-8", "strict")
                except UnicodeDecodeError as exc:
                    raise ProtocolError("invalid UTF-8") from exc
            return
        if major == 4:
            if value > MAX_ARRAY:
                raise ProtocolError("CBOR array limit")
            for _ in range(value):
                self.item(depth + 1)
            return
        if major == 5:
            if value > MAX_MAP:
                raise ProtocolError("CBOR map limit")
            previous = -1
            for _ in range(value):
                self.values += 1
                if self.values > MAX_VALUES:
                    raise ProtocolError("CBOR value-count limit")
                key_major, key = self.head()
                if key_major != 0:
                    raise ProtocolError("map key is not an unsigned integer")
                if key <= previous:
                    raise ProtocolError("map keys duplicate or out of order")
                previous = key
                self.item(depth + 1)
            return
        if major == 7 and value in (20, 21, 22):
            return
        raise ProtocolError("forbidden CBOR type")


def validate_cbor(payload: bytes) -> None:
    if not payload or payload[0] >> 5 != 5:
        raise ProtocolError("payload is not one top-level map")
    cursor = _Cursor(payload)
    cursor.item()
    if cursor.pos != len(payload):
        raise ProtocolError("trailing CBOR data")


def validate_object(value: Any, depth: int = 1, count: list[int] | None = None) -> None:
    if count is None:
        count = [0]
    if depth > MAX_DEPTH:
        raise ProtocolError("object nesting limit")
    count[0] += 1
    if count[0] > MAX_VALUES:
        raise ProtocolError("object value-count limit")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if value < -(1 << 63) or value > (1 << 64) - 1:
            raise ProtocolError("integer limit")
        return
    if type(value) is bytes:
        if len(value) > MAX_STRING:
            raise ProtocolError("byte-string limit")
        return
    if type(value) is str:
        if len(value.encode("utf-8")) > MAX_STRING:
            raise ProtocolError("text-string limit")
        return
    if type(value) is list:
        if len(value) > MAX_ARRAY:
            raise ProtocolError("array limit")
        for item in value:
            validate_object(item, depth + 1, count)
        return
    if type(value) is dict:
        if len(value) > MAX_MAP:
            raise ProtocolError("map limit")
        previous = -1
        for key in sorted(value):
            if type(key) is not int or key < 0 or key <= previous:
                raise ProtocolError("map keys must be unique nonnegative integers")
            previous = key
            count[0] += 1
            if count[0] > MAX_VALUES:
                raise ProtocolError("object value-count limit")
            validate_object(value[key], depth + 1, count)
        return
    raise ProtocolError("unsupported object type")


def encode_payload(value: dict[int, Any]) -> bytes:
    if type(value) is not dict:
        raise ProtocolError("top-level payload must be a map")
    validate_object(value)
    payload = cbor2.dumps(value, canonical=True)
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("payload limit")
    validate_cbor(payload)
    return payload


def decode_payload(payload: bytes) -> dict[int, Any]:
    validate_cbor(payload)
    value = cbor2.loads(payload)
    validate_object(value)
    if cbor2.dumps(value, canonical=True) != payload:
        raise ProtocolError("payload is not deterministic")
    return value


def encode_packet(message_class: int, request_id: int, payload: dict[int, Any],
                  descriptor_count: int = 0, *, interface_major: int = INTERFACE_MAJOR,
                  interface_minor: int = INTERFACE_MINOR) -> bytes:
    body = encode_payload(payload)
    if not 0 <= descriptor_count <= MAX_DESCRIPTORS:
        raise ProtocolError("descriptor-count limit")
    if message_class == EVENT:
        if request_id != 0:
            raise ProtocolError("events use request ID zero")
    elif request_id == 0:
        raise ProtocolError("non-events use a nonzero request ID")
    return HEADER.pack(MAGIC, ENVELOPE_MAJOR, ENVELOPE_MINOR, message_class, 0,
                       interface_major, interface_minor, request_id, len(body),
                       descriptor_count, 0) + body


def decode_packet(packet: bytes, descriptor_count: int = 0) -> tuple[Header, dict[int, Any]]:
    if len(packet) < HEADER_SIZE or len(packet) > MAX_PACKET:
        raise ProtocolError("packet length")
    fields = HEADER.unpack_from(packet)
    magic, emaj, emin, cls, flags, imaj, imin, req, length, expected_fds, reserved = fields
    if magic != MAGIC:
        raise ProtocolError("magic")
    if emaj != ENVELOPE_MAJOR:
        raise ProtocolError("envelope major")
    if cls not in (REQUEST, REPLY, EVENT, CANCEL):
        raise ProtocolError("message class")
    if flags or reserved:
        raise ProtocolError("reserved header bits")
    if imaj == 0:
        raise ProtocolError("interface major zero")
    if (cls == EVENT) != (req == 0):
        raise ProtocolError("request ID class rule")
    if expected_fds != descriptor_count or expected_fds > MAX_DESCRIPTORS:
        raise ProtocolError("descriptor count")
    if len(packet) != HEADER_SIZE + length:
        raise ProtocolError("declared payload length")
    header = Header(cls, req, length, expected_fds, emaj, emin, flags, imaj, imin, reserved)
    return header, decode_payload(packet[HEADER_SIZE:])


def recv_packet(sock: socket.socket) -> tuple[Header, dict[int, Any], list[int]]:
    control_size = socket.CMSG_SPACE(MAX_DESCRIPTORS * struct.calcsize("i"))
    data, ancillary, flags, _ = sock.recvmsg(MAX_PACKET, control_size,
                                             getattr(socket, "MSG_CMSG_CLOEXEC", 0))
    descriptors: list[int] = []
    try:
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ProtocolError("truncated data or ancillary data")
        for level, kind, raw in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                raise ProtocolError("unexpected ancillary message")
            usable = len(raw) - (len(raw) % struct.calcsize("i"))
            descriptors.extend(struct.unpack(f"={usable // 4}i", raw[:usable]))
        header, payload = decode_packet(data, len(descriptors))
        return header, payload, descriptors
    except Exception:
        for descriptor in descriptors:
            os.close(descriptor)
        raise


def send_packet(sock: socket.socket, packet: bytes, descriptors: list[int] | None = None) -> None:
    descriptors = descriptors or []
    ancillary = []
    if descriptors:
        ancillary.append((socket.SOL_SOCKET, socket.SCM_RIGHTS,
                          struct.pack(f"={len(descriptors)}i", *descriptors)))
    sent = sock.sendmsg([packet], ancillary, getattr(socket, "MSG_NOSIGNAL", 0))
    if sent != len(packet):
        raise OSError("partial sequential-packet send")
