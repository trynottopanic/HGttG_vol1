#!/usr/bin/env python3
import os, socket, sys, time
sys.path.insert(0, sys.argv[1])
from guide_ipc import REQUEST, encode_packet, recv_packet, send_packet

mode = sys.argv[2] if len(sys.argv) > 2 else 'launch'
sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
sock.connect('/run/guideos/supervisor/control.sock')
deadline = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 5_000_000_000
if mode == 'launch':
    request = {0: 1, 1: {0: 9001}, 2: deadline}
elif mode in ('stop', 'stop-denied') and len(sys.argv) == 5:
    request = {0: 3, 1: {0: bytes.fromhex(sys.argv[3]), 1: int(sys.argv[4])}, 2: deadline}
else:
    raise SystemExit('usage: owner_client.py PYTHON_PATH [launch|stop ID GENERATION]')
send_packet(sock, encode_packet(REQUEST, 1, request))
header, payload, descriptors = recv_packet(sock)
for descriptor in descriptors:
    os.close(descriptor)
sock.close()
assert header.request_id == 1
if mode == 'stop-denied':
    assert payload[0] == 6, payload
    print('GUIDE_OWNER_STOP_DENIED_PASS')
    raise SystemExit(0)
assert payload[0] == 0, payload
if mode == 'launch':
    instance = payload[1][0]
    generation = payload[1][1]
    assert isinstance(instance, bytes) and len(instance) == 16 and generation > 0
    print(f'{instance.hex()} {generation}')
else:
    assert payload[1][0] == 1
    print('GUIDE_OWNER_STOP_PASS')
