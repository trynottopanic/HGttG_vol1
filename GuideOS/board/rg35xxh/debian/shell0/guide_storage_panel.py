"""Read bounded provider snapshots; the shell never opens or mounts TF2."""
import json
from pathlib import Path
import time

class StoragePanel:
    def __init__(self, path=Path('/run/guideos-storage/status.json')):
        self.path = path
        self.status = {}
        self.next_poll = 0

    def poll(self):
        now = time.monotonic()
        if now < self.next_poll:
            return False
        self.next_poll = now+1
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError('large snapshot')
            value = json.loads(raw)
            if not isinstance(value, dict) or not 0 <= now-value.get('updated', -100) <= 35:
                raise ValueError('stale snapshot')
            if not isinstance(value.get('message'), str) or len(value['message']) > 100 or not value['message'].isascii():
                raise ValueError('bad message')
            folders = value.get('folders', [])
            allowed = {'CARTRIDGES','APPLICATIONS','APPLICATIONS/GAMES','APPLICATIONS/BIOS','MEDIA','DOCUMENTS','GENERAL','MISC'}
            if not isinstance(folders,list) or len(folders)>8 or any(x not in allowed for x in folders):
                raise ValueError('bad folders')
            if value.get('filesystem', 'exfat') not in ('exfat','vfat','ext4') or type(value.get('packages',0)) is not int or not 0 <= value.get('packages',0) <= 512:
                raise ValueError('bad volume')
            value.pop('updated', None)
        except (OSError, ValueError, TypeError):
            value = dict(state='unavailable', message='Card service unavailable', folders=[])
        changed = value != self.status
        self.status = value
        return changed

    def rows(self):
        s = self.status
        folders = s.get('folders', [])
        rows = [('Status', s.get('message', 'Checking card service'))]
        if 'filesystem' in s:
            rows.append(('Volume', str(s['filesystem']) + ' / read-only'))
        if s.get('state') == 'guide':
            rows += [('Guide folders', ', '.join(x.title() for x in folders if '/' not in x)),
                     ('Cartridges', str(s.get('packages',0)) + ('+ files; unverified' if s.get('count_limited') else ' files; unverified'))]
        if s.get('state') in ('guide','incomplete','ordinary','invalid'):
            rows.append(('Access', 'Recognition only; installation is not enabled'))
        return rows

    def draw(self, screen, draw):
        screen._text(draw, (20,102), 'EXTERNAL CARD', 22, '#ffd166')
        y = 150
        for label, value in self.rows():
            screen._text(draw, (20,y), label, 14, '#9cacbf')
            line = ''
            for word in value.split():
                if len(line)+len(word)+1 > 45:
                    screen._text(draw, (155,y), line, 16); y += 23; line = ''
                line = (line+' '+word).strip()
            screen._text(draw, (155,y), line, 16); y += 42
