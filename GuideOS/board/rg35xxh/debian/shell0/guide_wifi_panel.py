"""Local Wi-Fi controls. No credentials in argv, reports or persisted UI state."""
import json
from pathlib import Path
import socket
import time
from concurrent.futures import ThreadPoolExecutor
import subprocess
import uuid
from guide_telemetry import Timings
from guide_input import TextEntryManager, TextRequest, Keyboard, StickController, KEYBOARD_ACTIONS, renderer

UP, DOWN, LEFT, RIGHT, A, B, MENU = 544, 545, 546, 547, 305, 304, 316
RUNTIME = Path('/run/guideos-wifi')


class WiFiPanel:
    def __init__(self, runtime=RUNTIME, text_entries=None):
        self.runtime = Path(runtime)
        self.status = dict(state='starting', message='Waiting for Wi-Fi service...', networks=[], busy=False)
        self.view = 'list'
        self.cursor = 0
        self.detail_cursor = 0
        self.target = None
        self.text_entries = text_entries if text_entries is not None else TextEntryManager()
        self.editor = None
        self.stick_input = None
        self.keyboard_renderer = None
        self.notice = ''
        self.next_poll = 0
        self.last_signature = None
        self.pending_token = ''
        self.sent_at = 0
        self.timings = Timings()
        self._address_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='wifi-address')
        self._address_future = None
        self._next_address = 0
        self._ipv4 = ''

    @staticmethod
    def _wifi_address():
        try:
            result = subprocess.run(['/usr/sbin/ip', '-j', '-4', 'addr', 'show'],
                                    capture_output=True, timeout=2, check=True)
            for interface in json.loads(result.stdout):
                name = interface.get('ifname', '')
                if not (Path('/sys/class/net') / name / 'wireless').exists():
                    continue
                for address in interface.get('addr_info', []):
                    if address.get('family') == 'inet' and address.get('scope') == 'global':
                        return address.get('local', '')
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return ''

    def _poll_address(self):
        if self._address_future is not None and self._address_future.done():
            self._ipv4 = self._address_future.result()
            self._address_future = None
        if self._address_future is None and time.monotonic() >= self._next_address:
            self._next_address = time.monotonic() + 5
            self._address_future = self._address_worker.submit(self._wifi_address)

    def rows(self):
        return [('scan', 'Rescan nearby networks'), ('disconnect', 'Disconnect / pause auto-reconnect')] + [
            (r['id'], r['ssid']) for r in self.status['networks']]

    def selected(self):
        return next((r for r in self.status['networks'] if r['id'] == self.target), None)

    def clear(self):
        if self.editor:
            self.editor.close()
            self.editor = None
        self.stick_input = None
        self.view = 'list'
        self.notice = ''

    def poll(self):
        if time.monotonic() < self.next_poll:
            return False
        self.next_poll = time.monotonic() + .25
        self._poll_address()
        try:
            path = self.runtime / 'status.json'
            if path.stat().st_size > 128 * 1024:
                raise ValueError('Oversized status')
            status = json.loads(path.read_text())
            if time.monotonic() - status['observed'] > 15:
                raise ValueError('Stale provider')
            if not isinstance(status['networks'], list) or len(status['networks']) > 128:
                raise ValueError('Invalid network list')
            old_id = self.rows()[min(self.cursor, len(self.rows()) - 1)][0]
            self.status = status
            self.status['ipv4'] = self._ipv4
            if self.pending_token and status.get('token') == self.pending_token:
                self.timings.add('wifi_ack', time.monotonic()-self.sent_at)
                self.pending_token = ''
                self.notice = ''
            elif self.pending_token and time.monotonic() - self.sent_at > 3:
                self.notice = 'Service has not acknowledged the request.'
            ids = [r[0] for r in self.rows()]
            self.cursor = ids.index(old_id) if old_id in ids else min(self.cursor, len(ids) - 1)
            self.status['next_check_seconds'] = (status.get('next_check_seconds', 0) + 59) // 60
            signature = json.dumps({k: v for k, v in self.status.items() if k not in ('observed', 'next_check_seconds')}, sort_keys=True) + self.notice
        except (OSError, ValueError, KeyError, TypeError):
            self.status = dict(state='unavailable', message='Wi-Fi service unavailable. Try again shortly.', networks=[], busy=False)
            signature = 'unavailable'
        changed = signature != self.last_signature
        self.last_signature = signature
        self.timings.flush()
        return changed

    def send(self, action, **values):
        try:
            self.pending_token = uuid.uuid4().hex
            self.sent_at = time.monotonic()
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                sock.sendto(json.dumps(dict(action=action, token=self.pending_token, requested_at=self.sent_at, **values)).encode(), str(self.runtime / 'control.sock'))
            self.notice = 'Request sent...'
        except OSError:
            self.notice = 'Wi-Fi service unavailable. Retry shortly.'

    def begin_password(self):
        row = self.selected()
        self.editor = Keyboard(self.text_entries, TextRequest(
            owner_id='system.wifi', field_id='password:' + self.target,
            label='Password for ' + (row['ssid'] if row else 'selected network'),
            purpose='password', secret=True, min_length=8, max_length=63, max_bytes=63,
            allowed_characters=''.join(chr(i) for i in range(32, 127)), submit_label='JOIN'))
        self.stick_input = StickController(self.editor)
        self.view = 'password'
        self.notice = ''

    def finish_editor(self):
        if self.editor is None or self.editor.session.state == 'editing':
            return
        result = self.editor.take_result()
        self.editor = None
        self.stick_input = None
        if result is not None and result.state == 'submitted':
            try:
                self.send('connect', id=self.target, password=result.text)
                self.view = 'working'
            finally:
                result = None
        else:
            self.view = 'detail'

    def sticks(self, sample, now=None):
        if self.view != 'password' or self.editor is None or self.stick_input is None:
            return False
        changed = self.stick_input.update(
            left=sample.get('left'),
            right=None if sample.get('right_click') else sample.get('right'),
            generation=sample.get('generation', 0), now=now)
        self.finish_editor()
        return changed

    def key(self, code):
        if code == MENU:
            self.clear()
            return 'home'
        if self.view == 'password':
            if self.editor is None:
                self.clear()
                return 'changed'
            # A click or edit must never also commit an old neighbor on release.
            if self.stick_input is not None:
                if code in (317, 310, 311):
                    self.stick_input.reset()
                elif code in KEYBOARD_ACTIONS:
                    self.stick_input.reset_right()
            self.editor.handle(KEYBOARD_ACTIONS.get(code))
            self.finish_editor()
            return 'changed'
        if code == B:
            if self.view == 'list':
                return 'home'
            if self.view == 'working' and (self.status.get('busy') or self.pending_token):
                self.send('cancel')
            self.clear()
            return 'changed'
        if self.view == 'working':
            if not self.status.get('busy') and not self.pending_token and code == A:
                self.clear()
            return 'changed'
        if self.view == 'detail':
            row = self.selected()
            if not row:
                self.notice = 'Network disappeared. Rescan to update the list.'
                return 'changed'
            if code in (UP, DOWN):
                self.detail_cursor = 1 - self.detail_cursor if row['saved'] else 0
            elif code == A:
                if self.detail_cursor == 1:
                    self.view = 'forget'
                elif not row['available'] or not row['supported']:
                    self.notice = 'Unavailable or unsupported security. Rescan or choose another.'
                elif row['active']:
                    self.send('disconnect')
                    self.view = 'working'
                elif row['saved'] or row['security'] == 'Open':
                    self.send('connect', id=self.target)
                    self.view = 'working'
                else:
                    self.begin_password()
            return 'changed'
        if self.view == 'forget':
            if code == A:
                self.send('forget', id=self.target)
                self.view = 'working'
            return 'changed'
        if code in (UP, DOWN):
            self.cursor = (self.cursor + (1 if code == DOWN else -1)) % len(self.rows())
        elif code == A:
            identity = self.rows()[self.cursor][0]
            self.notice = ''
            if self.status.get('busy'):
                self.view = 'working'
            elif identity in ('scan', 'disconnect'):
                self.send(identity)
                self.view = 'working'
            else:
                self.target = identity
                self.detail_cursor = 0
                self.view = 'detail'
        return 'changed'

    def draw(self, screen, draw):
        def text(x, y, value, size=16, color='#f1f5fa', width=590):
            value = str(value)
            while screen.text_width(value, size) > width:
                value = value[:-2] + '…'
            screen._text(draw, (x, y), value, size, color)
        def box(y, label, selected):
            draw.rounded_rectangle((20, y, 620, y + 39), radius=5, fill='#354561' if selected else '#203047',
                                   outline='#ffd166' if selected else '#203047', width=2)
            text(30, y + 10, label)
        text(20, 91, 'WI-FI', 22, '#ffd166')
        if self.view == 'working':
            text(20, 145, self.notice if self.pending_token else self.status['message'], 16)
            connected = self.status.get('connected')
            row = next((r for r in self.status['networks'] if r['id'] == connected), None)
            text(20, 187, 'Link: ' + (row['ssid'] if row else 'not connected'))
            text(20, 245, 'Initial connection: up to 30 seconds.')
            text(20, 277, 'Switch attempt: 5 seconds; cleanup failures are shown.')
            return
        if self.view in ('detail', 'forget'):
            row = self.selected()
            text(20, 136, row['ssid'] if row else 'Network no longer available', 22)
            if row:
                text(20, 178, row['security'] + '  /  ' + (str(row['signal']) + '% signal' if row['available'] else 'not in range'))
                text(20, 209, 'Saved credentials' if row['saved'] else 'Not saved')
                if self.view == 'forget':
                    text(20, 270, 'Remove saved credentials for this network?')
                    text(20, 310, 'If connected, this also disconnects Wi-Fi.')
                    draw.rounded_rectangle((20, 355, 300, 398), radius=5,
                                           fill='#203047', outline='#ffd166', width=2)
                    text(35, 368, 'Forget network')
                else:
                    box(258, 'Disconnect' if row['active'] else 'Connect / switch to this network', self.detail_cursor == 0)
                    if row['saved']:
                        box(304, 'Forget saved network', self.detail_cursor == 1)
                    text(20, 366, self.notice, 14)
            return
        text(20, 125, self.status['message'], 14, '#9cacbf')
        entries = self.rows()
        start = max(0, min(self.cursor - 2, len(entries) - 5))
        for index in range(start, min(len(entries), start + 5)):
            identity, label = entries[index]
            y = 155 + (index - start) * 44
            if index >= 2:
                row = self.status['networks'][index - 2]
                label = ('* ' if row['active'] else '+ ' if row['saved'] else '  ') + label
                box(y, '', index == self.cursor)
                text(30, y + 10, label, width=365)
                text(411, y + 10, str(row['signal']) + '% ' + row['security'] if row['available'] else 'not in range', 14, width=198)
            else:
                box(y, label, index == self.cursor)
        text(20, 385, 'Auto-reconnect paused by Disconnect.' if self.status.get('hold') else 'Auto-reconnect: 5-30 min; no internet pings.', 14, '#9cacbf')
        text(20, 437, '* connected  + saved  |  Signal: cached readings, rescan to refresh', 14, '#9cacbf')

    def draw_editor(self, sink):
        if self.keyboard_renderer is None:
            self.keyboard_renderer = renderer()
        sink.show(self.keyboard_renderer.render(self.editor, application_label='WI-FI'))
