"""Shell view of the audio service; display and input remain shell-owned."""
import json
from pathlib import Path
import socket
import time
import uuid
from guide_telemetry import Timings

UP, DOWN, A, B, MENU = 544, 545, 305, 304, 316


class AudioPanel:
    def __init__(self, runtime='/run/guideos-audio'):
        self.runtime = Path(runtime)
        self.view, self.cursor = 'player', 0
        self.status = dict(message='Waiting for audio service...', files=[], outputs=[], devices=[])
        self.notice, self.signature = '', None
        self.next_poll = 0
        self.pending = ''
        self.sent_at = 0
        self.timings = Timings()

    def rows(self):
        if self.view == 'audio':
            return [('view:outputs', 'Current audio output'),
                    ('view:bluetooth', 'Bluetooth earbuds'),
                    ('refresh', 'Refresh audio information')]
        if self.view == 'outputs':
            return [('output:' + r['id'], ('* ' if r['id'] == self.status.get('output') else '') + r['title'])
                    for r in self.status.get('outputs', [])] or [('refresh', 'Refresh available outputs')]
        if self.view == 'files':
            return [('refresh', 'Refresh music files')] + [('play:' + r['id'], r['title']) for r in self.status.get('files', [])]
        if self.view == 'bluetooth':
            rows = [('cancel', 'Cancel discovery / connection')] if self.status.get('busy') or self.status.get('scanning') else [('scan', 'Find earbuds (20 seconds)')]
            return rows + [(('disconnect:' if r['connected'] else 'connect:') + r['id'],
                            ('Disconnect ' if r['connected'] else 'Connect ' if r['paired'] else 'Pair ') + r['title'])
                           for r in self.status.get('devices', [])]
        playing = self.status.get('state') in ('playing', 'starting')
        return [('view:files', 'Music files'), ('view:outputs', 'Audio output'), ('view:bluetooth', 'Bluetooth earbuds'),
                ('pause' if playing else 'resume', 'Pause' if playing else 'Resume'),
                ('stop', 'Stop')]

    def output_summary(self):
        selected = next((row['title'] for row in self.status.get('outputs', [])
                         if row['id'] == self.status.get('output')), 'Unavailable')
        volume = self.status.get('volume')
        parts = ['Output: ' + selected]
        if type(volume) in (int, float):parts.append('Volume: %s%%' % volume)
        return ' · '.join(parts)

    def poll(self):
        if time.monotonic() < self.next_poll:
            return False
        self.next_poll = time.monotonic() + .5
        try:
            path = self.runtime / 'status.json'
            if path.stat().st_size > 128 * 1024:
                raise ValueError()
            status = json.loads(path.read_text())
            if time.monotonic() - status['observed'] > 12:
                raise ValueError()
            for key in ('files', 'outputs', 'devices'):
                if not isinstance(status[key], list) or len(status[key]) > 128:
                    raise ValueError()
                if any(not isinstance(r.get('id'), str) or not isinstance(r.get('title'), str) for r in status[key]):
                    raise ValueError()
            old = self.rows()[min(self.cursor, len(self.rows()) - 1)][0]
            self.status = status
            identities = [r[0] for r in self.rows()]
            self.cursor = identities.index(old) if old in identities else 0
            if self.pending and status.get('token') == self.pending:
                self.timings.add('audio_ack', time.monotonic()-self.sent_at)
                self.pending, self.notice = '', ''
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self.status = dict(message='Audio service unavailable', files=[], outputs=[], devices=[])
            self.cursor = 0
        signature = json.dumps({k:v for k,v in self.status.items() if k != 'observed'}, sort_keys=True)
        changed = signature != self.signature
        self.signature = signature
        self.timings.flush()
        return changed

    def activate(self, identity):
        if identity not in {row[0] for row in self.rows()} and identity not in ('quieter', 'louder', 'test'):
            return False
        if identity.startswith('view:'):
            self.view, self.cursor, self.notice = identity[5:], 0, ''
            return True
        action, separator, value = identity.partition(':')
        request = dict(action=action)
        if separator:
            request['id'] = value
        if action in ('quieter', 'louder'):
            request = dict(action='volume', value=self.status.get('volume', 20) + (-5 if action == 'quieter' else 5))
        self.pending = request['token'] = uuid.uuid4().hex
        self.sent_at = time.monotonic()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
                connection.settimeout(.03)
                connection.sendto(json.dumps(request).encode(), str(self.runtime / 'control.sock'))
            self.notice = 'Request sent'
        except OSError:
            self.pending, self.notice = '', 'Audio service unavailable'
        return True

    def key(self, code):
        if code == MENU:
            return 'home'
        if code == B:
            if self.view == 'player':
                return 'home'
            self.view, self.cursor, self.notice = 'player', 0, ''
        elif code in (UP, DOWN):
            self.cursor = (self.cursor + (1 if code == DOWN else -1)) % len(self.rows())
        elif code == A:
            self.activate(self.rows()[self.cursor][0])
        return 'changed'

    def draw(self, screen, draw):
        def text(x, y, value, size=16, color='#f1f5fa'):
            value = ''.join(c for c in str(value) if c.isprintable())[:140]
            while value and screen.text_width(value, size) > 580:
                value = value[:-2] + '…'
            screen._text(draw, (x, y), value, size, color)
        text(20, 91, 'AUDIO / ' + self.view.upper(), 22, '#ffd166')
        message = (self.status.get('bluetooth_message') or self.status.get('message', '')) if self.view == 'bluetooth' else self.status.get('message', '')
        text(20, 125, message, 14)
        rows = self.rows()
        start = max(0, min(self.cursor - 2, len(rows) - 5))
        for index in range(start, min(len(rows), start + 5)):
            y = 155 + (index - start) * 44
            draw.rounded_rectangle((20, y, 620, y+39), radius=5,
                                   fill='#354561' if index == self.cursor else '#203047',
                                   outline='#ffd166' if index == self.cursor else '#203047', width=2)
            text(30, y+10, rows[index][1])
        text(20, 385, 'Position: %ss' % self.status.get('position', 0), 14)
        text(20, 437, self.notice or 'Playback continues when leaving this screen.', 14, '#9cacbf')
