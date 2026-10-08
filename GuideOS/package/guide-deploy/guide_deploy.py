#!/usr/bin/python3
"""Paired-PC client. All network operations use a pinned SSH identity."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import selectors
import sys
import time
import zipfile
from deploy_core import CHUNK, LIMIT, REQUIRED, canonical, digest, require, Rejected, validate_manifest

def pack(project, output, device, base, version):
    project, output = Path(project), Path(output)
    files = {}
    ui_modules = {'shell0/guide_ui_model.py', 'shell0/guide_field_ui.py'}
    for name in sorted(REQUIRED | {'shell0/guide_application_panel.py', 'shell0/guide_installer_panel.py', 'shell0/guide_storage_panel.py', 'shell0/guide_audio_panel.py', 'shell0/guide_telemetry.py', 'shell0/guide_control_client.py', 'shell0/guide_status_bar.py', 'shell0/guide_v3_ui.py'} | ui_modules):
        folder, filename = name.split('/')
        source = project / ('package/guide-ui' if name in ui_modules else
                            'board/rg35xxh/debian/shell0' if folder == 'shell0' else
                            'package/guide-input') / filename
        files[name] = source
    manifest = dict(format='GUIDE-DEPLOY-1', device=device, base=base, arch='arm64', version=version,
                    files={name: dict(bytes=path.stat().st_size, sha256=digest(path)) for name, path in files.items()})
    validate_manifest(manifest, device, base)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', canonical(manifest))
        for name, path in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    if output.stat().st_size > LIMIT:
        output.unlink()
        raise Rejected('transfer-limit')
    return dict(id=digest(output), bytes=output.stat().st_size, base=base, version=version)

class Remote:
    def __init__(self, profile, host, port=None):
        require(host and not host.startswith('-') and all(c.isalnum() or c in '.:-' for c in host), 'bad-host')
        argv = ['ssh', '-T', '-p', str(port or profile.get('port', 2222)), '-i', profile['identity'],
                '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile=' + profile['known_hosts'], '-o', 'HostKeyAlias=' + profile['device'],
                '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                'guide-deploy@' + host, 'guide-deploy-v1']
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def request(self, op, _timeout=60, **values):
        self.process.stdin.write(canonical(dict(op=op, **values)) + b'\n')
        self.process.stdin.flush()
        raw = bytearray()
        deadline=time.monotonic()+_timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout,selectors.EVENT_READ)
            while not raw.endswith(b'\n'):
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):
                    self.process.kill()
                    raise Rejected('connection-timeout')
                block=os.read(self.process.stdout.fileno(),min(65536,360001-len(raw)))
                if not block: break
                raw.extend(block)
                if len(raw)>360000: break
        require(raw and len(raw) <= 360000, 'connection-lost-resume-available')
        response = json.loads(raw)
        require(response.get('ok'), response.get('reason', 'invalid-reply'))
        return response['result']

    def close(self):
        try: self.process.stdin.close()
        except OSError: pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process.stdout.close()

def upload(remote, package):
    package = Path(package)
    require(0 < package.stat().st_size <= LIMIT, 'transfer-limit')
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
    identity = digest(package)
    if manifest.get('format') == 'GUIDE-SIGNED-BUNDLE-1':
        status = remote.request('status')
        require(status.get('protocol') == 'GUIDE-SIGNED-BUNDLE-1', 'signed-bootstrap-required')
        require(status.get('sequence') in manifest['profile']['manifest']['baseReleaseSequences'], 'incompatible-base')
        base = status['active']['release']
    else:
        base = manifest['base']
    txn = remote.request('begin', id=identity, bytes=package.stat().st_size, base=base)
    if txn['state'] == 'receiving':
        with package.open('rb') as stream:
            offset = txn['received']
            stream.seek(offset)
            while data := stream.read(CHUNK):
                offset = remote.request('chunk', id=identity, offset=offset,
                                        data=base64.b64encode(data).decode('ascii'))['received']
        txn = remote.request('validate', id=identity)
    require(txn['state'] in ('validated', 'queued', 'activating', 'trial', 'committed', 'rolled-back'), 'transaction-state')
    return identity, txn

def wait(remote, identity):
    deadline = time.monotonic() + 110
    while time.monotonic() < deadline:
        status = remote.request('status')
        txn = status['transaction']
        require(txn and txn['id'] == identity, 'transaction-changed')
        if txn['state'] not in ('queued', 'activating', 'trial', 'recovering'):
            return status
        time.sleep(.5)
    raise Rejected('activation-still-running-check-status')

def main():
    parser = argparse.ArgumentParser(description='Guide local network delivery, at most 100 MB per complete release')
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int)
    sub = parser.add_subparsers(dest='op', required=True)
    sub.add_parser('status')
    sub.add_parser('rollback')
    packer = sub.add_parser('pack')
    packer.add_argument('--project', type=Path, required=True)
    packer.add_argument('--output', type=Path, required=True)
    packer.add_argument('--version', required=True)
    for name in ('stage', 'deploy'):
        action = sub.add_parser(name)
        action.add_argument('package', type=Path)
    cancel = sub.add_parser('cancel')
    cancel.add_argument('id')
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    remote = Remote(profile, args.host, args.port)
    try:
        status = remote.request('status')
        require(status['device'] == profile['device'], 'wrong-device')
        if args.op == 'status':
            result = status
        elif args.op == 'pack':
            result = pack(args.project, args.output, status['device'], status['active']['release'], args.version)
        elif args.op == 'cancel':
            result = remote.request('cancel', id=args.id)
        elif args.op == 'rollback':
            txn = remote.request('rollback')
            result = wait(remote, txn['id'])
        else:
            identity, result = upload(remote, args.package)
            if args.op == 'deploy':
                remote.request('activate', id=identity)
                result = wait(remote, identity)
        print(json.dumps(result, indent=2))
        txn = result.get('transaction', result)
        if args.op in ('deploy', 'rollback') and txn.get('state') != 'committed':
            return 2
        return 0
    finally:
        remote.close()

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Rejected, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, Rejected) else 'Local or connection failure; check status before retrying.', file=sys.stderr)
        raise SystemExit(1)
