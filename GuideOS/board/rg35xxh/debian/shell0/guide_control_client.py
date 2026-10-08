"""Shell-side input stream; only the resident control service opens evdev."""
from collections import deque
import json
import os
import select
import socket
import time
from types import SimpleNamespace
from guide_platform_rg35xxh import InputEvent


class RemoteDeckInputs:
    def __init__(self, event_log=None, path=None):
        self.path=path or os.environ['GUIDE_CONTROL_SOCKET']
        self.connection=None
        self.devices=[]
        self.pending=deque(maxlen=512)
        self.next_connect=0
        self.snapshot=dict(left=None,right=None,generation=0,right_click=False)
        self._connect()

    def _connect(self):
        if self.connection or time.monotonic()<self.next_connect:return
        self.next_connect=time.monotonic()+.5
        connection=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        connection.settimeout(.05)
        try:
            connection.connect(self.path)
            connection.setblocking(False)
            self.connection=connection
        except OSError:connection.close()

    def poll(self, delay=.05):
        self._connect()
        if not self.connection:
            time.sleep(min(delay,.05))
            return []
        ready,_,_=select.select([self.connection],[],[],delay)
        if ready:
            for _ in range(128):
                try:
                    raw=self.connection.recv(16385)
                    if not raw or len(raw)>16384:raise OSError('Input broker disconnected')
                    packet=json.loads(raw)
                    if packet['type']=='overlay':
                        event=InputEvent(('Guide control',0,0,0),time.monotonic())
                        event.control_prepare=packet['token']
                        self.pending.append(event)
                    elif packet['type']=='reset':
                        self.pending.clear()
                        self.devices=[SimpleNamespace(name=name) for name in packet['devices']]
                        self.snapshot=packet['snapshot']
                        event=InputEvent(('Guide control',0,3,0),time.monotonic())
                        event.sticks=self.snapshot.copy()
                        event.control_resume=True
                        self.pending.append(event)
                    else:
                        for item in packet['events']:
                            event=InputEvent(tuple(item['values']),item['timestamp'])
                            if 'sticks' in item:
                                self.snapshot=item['sticks']
                                event.sticks=self.snapshot.copy()
                            self.pending.append(event)
                except BlockingIOError:break
                except (OSError,ValueError,KeyError,TypeError):
                    self.connection.close()
                    self.connection=None
                    self.pending.clear()
                    self.snapshot=dict(left=None,right=None,generation=self.snapshot['generation']+1,right_click=False)
                    break
        events=list(self.pending)
        self.pending.clear()
        return events

    def stick_snapshot(self):return self.snapshot.copy()

    def display_yielded(self,token):
        if self.connection:
            self.connection.send(json.dumps(dict(type='display-yielded',token=token)).encode())

    def close(self):
        if self.connection:self.connection.close()
        self.connection=None
        return []
