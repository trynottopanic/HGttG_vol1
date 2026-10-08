#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import socket
import struct
import sys
import time

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "python"))

import guide_ipc as ipc

REQUEST_ID = 0x1020304050607080


def listener(path: str) -> socket.socket:
    if os.environ.get("LISTEN_PID") == str(os.getpid()) and os.environ.get("LISTEN_FDS") == "1":
        return socket.socket(fileno=3)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    sock.bind(path)
    sock.listen(8)
    return sock


def run_server(path: str) -> int:
    listening = listener(path)
    connection, _ = listening.accept()
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    pidfd = os.pidfd_open(pid)
    descriptors: list[int] = []
    try:
        header, payload, descriptors = ipc.recv_packet(connection)
        if header.message_class != ipc.REQUEST or payload[0] != 1 or len(descriptors) != 1:
            raise ipc.ProtocolError("unexpected spike request")
        os.fstat(descriptors[0])
        reply = ipc.encode_packet(ipc.REPLY, header.request_id,
                                  {0: 0, 1: {0: pid, 1: True}})
        ipc.send_packet(connection, reply)
        print(f"PY_SERVER_PASS peer_pid={pid} uid={uid} gid={gid} pidfd={pidfd}")
        return 0
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
        os.close(pidfd)
        connection.close()
        listening.close()
        if "LISTEN_FDS" not in os.environ:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def run_client(path: str) -> int:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    sock.connect(path)
    deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 30_000_000_000
    packet = ipc.encode_packet(ipc.REQUEST, REQUEST_ID, {0: 1, 1: {}, 2: deadline}, 1)
    descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    try:
        ipc.send_packet(sock, packet, [descriptor])
    finally:
        os.close(descriptor)
    header, payload, descriptors = ipc.recv_packet(sock)
    try:
        if descriptors or header.message_class != ipc.REPLY or header.request_id != REQUEST_ID:
            raise ipc.ProtocolError("unexpected spike reply")
        if payload[0] != 0 or payload[1][1] is not True:
            raise ipc.ProtocolError("unexpected reply body")
        print(f"PY_CLIENT_PASS reply_bytes={ipc.HEADER_SIZE + header.payload_length}")
        return 0
    finally:
        for received in descriptors:
            os.close(received)
        sock.close()


def run_malformed(path: str, kind: str) -> int:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    sock.connect(path)
    if kind == "magic":
        packet = bytearray(ipc.encode_packet(ipc.REQUEST, REQUEST_ID, {0: 1, 1: {}, 2: 1}))
        packet[:4] = b"FAIL"
    elif kind == "duplicate":
        payload = bytes.fromhex("a200010002")
        packet = ipc.HEADER.pack(ipc.MAGIC, 1, 0, ipc.REQUEST, 0, 1, 0,
                                 REQUEST_ID, len(payload), 0, 0) + payload
    elif kind == "length":
        packet = bytearray(ipc.encode_packet(ipc.REQUEST, REQUEST_ID, {0: 1, 1: {}, 2: 1}))
        packet[20:22] = (len(packet) + 1).to_bytes(2, "big")
    else:
        raise SystemExit("unknown malformed case")
    sock.send(bytes(packet))
    sock.shutdown(socket.SHUT_WR)
    received = sock.recv(1)
    sock.close()
    if received:
        raise ipc.ProtocolError("malformed request unexpectedly received a reply")
    print(f"PY_MALFORMED_PASS kind={kind}")
    return 0


def profile_tests() -> int:
    valid = {0: 1, 1: {}, 2: time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 1_000_000_000}
    encoded = ipc.encode_payload(valid)
    assert ipc.decode_payload(encoded) == valid
    invalid = {
        "duplicate": bytes.fromhex("a200010002"),
        "indefinite": bytes.fromhex("bf0001ff"),
        "float": bytes.fromhex("a100f93c00"),
        "tag": bytes.fromhex("a100c001"),
        "nonminimal": bytes.fromhex("a1180001"),
        "text-key": bytes.fromhex("a1616101"),
        "trailing": encoded + b"\x00",
    }
    for name, payload in invalid.items():
        try:
            ipc.validate_cbor(payload)
        except ipc.ProtocolError:
            continue
        raise AssertionError(f"invalid profile accepted: {name}")
    print(f"PY_PROFILE_PASS invalid_cases={len(invalid)}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: guide_ipc_spike.py server|client|malformed|profile ...")
    mode = sys.argv[1]
    if mode == "profile" and len(sys.argv) == 2:
        return profile_tests()
    if mode in ("server", "client") and len(sys.argv) == 3:
        return run_server(sys.argv[2]) if mode == "server" else run_client(sys.argv[2])
    if mode == "malformed" and len(sys.argv) == 4:
        return run_malformed(sys.argv[2], sys.argv[3])
    raise SystemExit("invalid arguments")


if __name__ == "__main__":
    raise SystemExit(main())
