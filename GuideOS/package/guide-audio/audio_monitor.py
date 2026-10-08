"""Bounded codec/route evidence; no media names or Bluetooth addresses retained."""
from pathlib import Path
import re
import subprocess
import time
from guide_telemetry import emit


def route_snapshot(items, selected):
    for item in items:
        info = item.get('info', {})
        if info.get('props', {}).get('node.name') != selected:
            continue
        for props in info.get('params', {}).get('Props', []):
            volumes = props.get('channelVolumes', [])
            values = [v for v in volumes if type(v) in (int, float) and 0 <= v <= 4]
            if 'mute' in props:
                return dict(muted=int(bool(props['mute'])),
                            route_volume=round(max(values)*100, 2) if values else -1)
    return dict(muted=-1, route_volume=-1)


class Monitor:
    def __init__(self):
        self.next_sample = 0
        self.hardware_next = 0
        self.route = dict(muted=-1, route_volume=-1)

    def inventory(self, items, selected):
        self.route = route_snapshot(items, selected)

    def sample(self, player, outputs, selected):
        now = time.monotonic()
        if now < self.next_sample:
            return
        self.next_sample = now + 15
        emit('AUDIO_ROUTE', output_present=int(selected in {o['id'] for o in outputs}),
             volume=player.volume, **self.route)
        if now < self.hardware_next:
            return
        self.hardware_next = now + 60
        try:
            radios = [p for p in Path('/sys/class/rfkill').glob('rfkill*')
                      if (p/'type').read_text().strip() == 'bluetooth'][:8]
            emit('BLUETOOTH_HARDWARE', hci_count=len([p for p in Path('/sys/class/bluetooth').glob('hci*')
                                                    if re.fullmatch(r'hci\d+',p.name)][:8]),
                 radio_count=len(radios),
                 soft_blocked=sum((p/'soft').read_text().strip() == '1' for p in radios),
                 hard_blocked=sum((p/'hard').read_text().strip() == '1' for p in radios))
        except OSError:
            pass
        try:
            compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
            if b'anbernic,rg35xx-h' not in compatible:
                return
            result = subprocess.run(['amixer', '-c', 'Codec', 'contents'],
                                    capture_output=True, timeout=1, check=True)
            if len(result.stdout) > 32768:
                raise ValueError('Oversized mixer report')
            fields = {}
            names = {'DAC Playback Volume': 'dac_gain', 'Line Out Playback Volume': 'line_gain',
                     'Speaker Switch': 'speaker_on', 'Headphone Jack': 'headphone',
                     'DAC Playback Switch': 'dac_on', 'Line Out Playback Switch': 'line_on'}
            for block in result.stdout.decode(errors='replace').split('numid=')[1:]:
                name = re.search(r"name='([^']+)'", block)
                value = re.search(r': values=([^\n]+)', block)
                if not name or not value or name[1] not in names:
                    continue
                values = value[1].strip().split(',')
                fields[names[name[1]]] = (int(values[0]) if values[0].isdigit()
                                          else int(all(v == 'on' for v in values)))
            emit('AUDIO_MIXER', **fields)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            emit('AUDIO_MIXER_ERROR', error_number=getattr(error, 'errno', 0) or 0)
