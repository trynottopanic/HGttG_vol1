"""Packaged Weston -> real GTK/WebKit -> frontend command integration."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from guide_browser_session import stop

with tempfile.TemporaryDirectory(prefix='guide-browser-test-') as directory:
    env=dict(os.environ, XDG_RUNTIME_DIR=directory)
    process=subprocess.Popen(['dbus-run-session','--',sys.executable,
        str(Path(__file__).with_name('guide_browser_session.py')),'--headless'],
        env=env,start_new_session=True)
    def request(action, **values):
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as conn:
            conn.settimeout(2)
            conn.connect(directory+'/control.sock')
            conn.send(json.dumps(dict(action=action,**values)).encode())
            return json.loads(conn.recv(8192))
    try:
        deadline=time.monotonic()+25
        while not Path(directory,'control.sock').exists():
            if process.poll() is not None: raise RuntimeError('Session failed')
            if time.monotonic()>deadline: raise RuntimeError('Session startup timeout')
            time.sleep(.1)
        assert request('status')['ready']
        assert request('adapted',enabled=True)['adapted']
        assert request('address')['keyboard']
        assert not request('keyboard')['keyboard']
        request('close')
        assert process.wait(timeout=12)==0
        assert not Path(directory,'control.sock').exists()
        assert not Path(directory,'guide-browser-wayland').exists()
        print('SESSION_PASS: compositor, frontend IPC, keyboard, close, child cleanup')
    finally:
        stop(process)
