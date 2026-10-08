"""Debian/systemd adapter, separate from replaceable Guide shell code."""
import os
from pathlib import Path
import subprocess
import time
from deploy_core import Rejected, atomic_json, read_json, require

RUNTIME = Path('/run/guideos-deploy')

class Host:
    def __init__(self, runtime=RUNTIME):
        self.runtime = Path(runtime)

    def systemctl(self, *args):
        try:
            return subprocess.run(['/usr/bin/systemctl', *args], check=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except (subprocess.SubprocessError, OSError):
            raise Rejected('service-operation-failed') from None

    def schedule(self):
        self.systemctl('start', '--no-block', 'guide-deploy-apply.service')

    def check_candidate(self, directory):
        command = ['/usr/bin/systemd-run', '--unit=guide-deploy-check', '--wait', '--collect', '--quiet',
                   '-p', 'User=nobody', '-p', 'Group=nogroup', '-p', 'ProtectSystem=strict',
                   '-p', 'ProtectHome=yes', '-p', 'PrivateNetwork=yes', '-p', 'PrivateTmp=yes',
                   '-p', 'NoNewPrivileges=yes', '-p', 'MemoryMax=192M', '-p', 'TasksMax=16',
                   '-p', 'RuntimeMaxSec=30', '-p', 'Environment=PYTHONDONTWRITEBYTECODE=1',
                   '-p', 'Environment=GUIDE_WIFI_DISCOVERY=1 GUIDE_WIFI_CONTROL=1',
                   '/usr/bin/python3', '/usr/lib/guideos/deploy/check_release.py', str(directory)]
        try:
            subprocess.run(command, check=True, timeout=40, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            raise Rejected('candidate-check-failed') from None

    def heartbeat(self):
        try:
            data = read_json(self.runtime / 'shell.json')
            require(time.monotonic() - data['monotonic'] < 3 and data['pid'] > 0, 'shell-unavailable')
            # A stale old-process heartbeat must not validate a restarted service.
            pid = subprocess.check_output(['/usr/bin/systemctl', 'show', 'guide-shell', '-p', 'MainPID', '--value'],
                                          timeout=3, text=True).strip()
            require(str(data['pid']) == pid, 'shell-unavailable')
            return data
        except (OSError, KeyError, ValueError, subprocess.SubprocessError):
            raise Rejected('shell-unavailable') from None

    def admit(self):
        supplies = Path('/sys/class/power_supply')
        online = False
        for supply in supplies.glob('*'):
            try:
                kind = (supply / 'type').read_text().strip()
                if kind in ('USB', 'USB_C', 'USB_PD', 'Mains'):
                    online |= (supply / 'online').read_text().strip() == '1'
                elif kind == 'Battery':
                    online |= (supply / 'status').read_text().strip() in ('Charging', 'Full')
            except OSError:
                pass
        require(online, 'external-power-required')
        beat = self.heartbeat()
        require(beat['ready'] and beat['can_restart'], 'shell-busy')

    def quiesce(self, token):
        atomic_json(self.runtime / 'quiesce.json', dict(token=token))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.heartbeat().get('quiesced') == token:
                return
            time.sleep(.1)
        raise Rejected('quiescence-not-acknowledged')

    def unquiesce(self):
        (self.runtime / 'quiesce.json').unlink(missing_ok=True)

    def stop(self, recovery=False):
        self.systemctl('stop', 'guide-shell.service')
        if not recovery:
            try:
                final = read_json(self.runtime / 'shell.json')
                require(final.get('stopped') is True and final.get('clean') is True, 'cleanup-unconfirmed')
            except (OSError, ValueError):
                raise Rejected('cleanup-unconfirmed') from None

    def start(self):
        self.systemctl('reset-failed', 'guide-shell.service')
        self.systemctl('start', 'guide-shell.service')

    def healthy(self, release):
        deadline = time.monotonic() + getattr(self, 'trial_seconds', 20)
        good_since, pid = None, None
        while time.monotonic() < deadline:
            try:
                beat = self.heartbeat()
                require(beat['release'] == release and beat['ready'] and not beat.get('stopped'), 'candidate-not-ready')
                if pid != beat['pid']:
                    pid, good_since = beat['pid'], time.monotonic()
                if time.monotonic() - good_since >= 3:
                    return
            except Rejected:
                good_since, pid = None, None
            time.sleep(.2)
        raise Rejected('candidate-health-failed')
