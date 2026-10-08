#!/usr/bin/python3
"""RG35XX H boot-only retry for an observed RTL8821CS probe timeout.

Never resets a controller, unloads modules, changes credentials or touches a
bound radio. NetworkManager starts after this bounded board-provider operation.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import time

CONTROLLER = '4021000.mmc'
DRIVER = 'rtw88_8821cs'
MAX_ATTEMPTS = 2
STARTUP_WAIT = 12.0
RETRY_WAIT = 3.0


class Radio:
    def __init__(self, sysroot=Path('/sys'), procroot=Path('/proc')):
        self.sysroot, self.procroot = Path(sysroot), Path(procroot)

    def supported(self):
        return b'anbernic,rg35xx-h' in (self.sysroot / 'firmware/devicetree/base/compatible').read_bytes().split(b'\0')

    def interface_ready(self):
        return any((path / 'wireless').exists() or (path / 'phy80211').exists()
                   for path in (self.sysroot / 'class/net').iterdir())

    def target(self):
        matches = []
        for path in (self.sysroot / 'bus/sdio/devices').glob('*'):
            try:
                actual = path.resolve(strict=True)
                if CONTROLLER not in actual.parts or 'mmc_host' not in actual.parts:
                    continue
                if int((path / 'vendor').read_text(), 16) != 0x024c or int((path / 'device').read_text(), 16) != 0xc821:
                    continue
                if re.fullmatch(r'mmc[0-9]+:0001:1', path.name):
                    matches.append(path)
            except (OSError, ValueError):
                continue
        return matches[0] if len(matches) == 1 else None

    def bound(self, target):
        return (target / 'driver').exists()

    def failed_probe(self, target):
        # Only the current boot's exact target and timeout, never arbitrary
        # exception text, an old boot, or unrelated removable-card faults.
        result = subprocess.run(['journalctl', '-b', '-k', '--no-pager', '-o', 'cat', '-n', '4',
                                 '--grep', DRIVER + '.*probe.*failed.*-110'],
                                capture_output=True, timeout=2, check=True)
        if len(result.stdout) > 4096:
            return False
        text = result.stdout.decode('utf-8', 'replace')
        return any(DRIVER in line and target.name in line and 'failed' in line and '-110' in line
                   for line in text.splitlines())

    def retry(self, target):
        # Revalidate immediately before the only hardware write. The kernel's
        # SDIO bind repeats claim/enable, power-on, firmware and chip setup.
        if self.interface_ready() or self.target() != target or self.bound(target):
            return False
        (self.sysroot / ('bus/sdio/drivers/' + DRIVER + '/bind')).write_text(target.name)
        return True


def recover(radio, claim, clock=time.monotonic, sleep=time.sleep, event=lambda **values: None):
    if not radio.supported():
        return 'unsupported-board'
    deadline = clock() + STARTUP_WAIT
    target = None
    while True:
        if radio.interface_ready():
            return 'already-ready'
        target = radio.target()
        if target is not None and radio.bound(target):
            # Driver core creates the link before probe finishes. Wait for a
            # usable interface or a recorded failure; never bind over that link.
            if clock() >= deadline:
                return 'already-bound'
            sleep(.25)
            continue
        if target is not None and radio.failed_probe(target):
            break
        if clock() >= deadline:
            return 'no-matching-probe-failure'
        sleep(.25)
    if not claim():
        return 'already-attempted-this-boot'
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if radio.interface_ready() or radio.bound(target):
            return 'recovered'
        if radio.target() != target:
            return 'target-changed'
        event(event='retry', attempt=attempt)
        try:
            if not radio.retry(target):
                return 'state-changed'
        except OSError:
            # A failed sysfs bind returns the driver's probe error. A second
            # retry is allowed, but a disappearing/changed target is refused.
            event(event='probe-retry-failed', attempt=attempt)
        deadline = clock() + RETRY_WAIT
        while clock() < deadline:
            if radio.interface_ready() or radio.bound(target):
                return 'recovered'
            if radio.target() != target:
                return 'target-changed'
            sleep(.25)
    return 'initialization-failed'


def main():
    runtime = Path('/run/guideos-wifi-radio')
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    marker = runtime / (boot + '.attempted')

    def claim():
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, 'w') as stream:
            stream.write('boot-only bounded probe retries consumed\n')
        return True

    def event(**values):
        print('GUIDE_WIFI_RADIO ' + json.dumps(values, sort_keys=True), flush=True)

    try:
        result = recover(Radio(), claim, event=event)
    except (OSError, ValueError, subprocess.SubprocessError):
        result = 'observation-unavailable'
    record = dict(boot=boot, result=result, observed=time.monotonic(), maxAttempts=MAX_ATTEMPTS)
    temporary = runtime / 'status.tmp'
    temporary.write_text(json.dumps(record))
    temporary.replace(runtime / 'status.json')
    event(event='result', result=result)


if __name__ == '__main__':
    main()
