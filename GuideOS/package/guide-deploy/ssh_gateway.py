#!/usr/bin/python3
"""No general shell, command interpolation, or user-controlled filesystem path."""
import os
import socket
import sys

LIMIT = 360000
if os.environ.get('SSH_ORIGINAL_COMMAND') != 'guide-deploy-v1':
    raise SystemExit('Only Guide deployment is available on this connection.')
while True:
    line = sys.stdin.buffer.readline(LIMIT + 1)
    if not line:
        break
    if len(line) > LIMIT or not line.endswith(b'\n'):
        raise SystemExit('Request limit exceeded.')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(50)
            connection.connect('/run/guideos-deploy/control.sock')
            connection.sendall(line)
            with connection.makefile('rb') as reader:
                response = reader.readline(LIMIT + 1)
        if len(response) > LIMIT or not response.endswith(b'\n'):
            raise OSError()
    except OSError:
        response = b'{"ok":false,"reason":"controller-unavailable"}\n'
    sys.stdout.buffer.write(response)
    sys.stdout.buffer.flush()
