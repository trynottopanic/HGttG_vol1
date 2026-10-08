"""Bounded, local Guide release transactions. No shell commands from packages."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import time
import zipfile

LIMIT = 100_000_000
CHUNK = 262144
MAX_FILES = 512
MANIFEST_LIMIT = 262144
REQUIRED = {'shell0/guide_shell.py', 'shell0/guide_platform_rg35xxh.py',
            'shell0/guide_input.py', 'shell0/guide_menu_input.py', 'shell0/guide_wifi_panel.py',
            'input/guide_keyboard.py', 'input/guide_keyboard_view.py', 'input/guide_text_entry.py',
            'input/guide_stick_input.py', 'input/guide_pointer_input.py',
            'input/guide_pointer_view.py', 'input/guide_unicode.py', 'input/prototype_font.py'}
ID = re.compile(r'^[a-f0-9]{64}$')

class Rejected(Exception):
    """Only fixed, non-secret reason codes leave the controller."""

def require(condition, reason):
    if not condition:
        raise Rejected(reason)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

def digest(path):
    sha = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()

def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with open(temporary, 'wb') as stream:
        stream.write(canonical(value))
        # Release identity/version are public launcher metadata, never owner data.
        if path.name == 'active.json':os.fchmod(stream.fileno(), 0o644)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_dir(path.parent)

def read_json(path):
    with open(path, 'rb') as stream:
        raw = stream.read(MANIFEST_LIMIT + 1)
    require(len(raw) <= MANIFEST_LIMIT, 'metadata-too-large')
    return json.loads(raw)

def valid_path(name):
    require(isinstance(name, str) and 0 < len(name) <= 180, 'bad-path')
    parts = PurePosixPath(name).parts
    require(len(parts) == 2 and parts[0] in ('shell0', 'input', 'assets', 'browser')
            and all(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', p) for p in parts)
            and str(PurePosixPath(name)) == name and '\\' not in name, 'bad-path')
    require(Path(name).suffix in ('.py', '.json', '.png', '.ttf', '.otf', '.txt'), 'bad-file-type')
    if parts[0] in ('shell0', 'input', 'browser'):
        require(Path(name).suffix == '.py', 'unsupported-module')

def validate_manifest(m, device, base):
    require(isinstance(m, dict) and set(m) == {'format', 'device', 'base', 'version', 'arch', 'files'}, 'bad-manifest')
    require(m['format'] == 'GUIDE-DEPLOY-1' and m['arch'] == 'arm64', 'incompatible-runtime')
    require(m['device'] == device, 'wrong-device')
    require(m['base'] == base, 'stale-base')
    from release_version import valid_label
    require(valid_label(m['version']), 'bad-version')
    files = m['files']
    require(isinstance(files, dict) and REQUIRED <= files.keys() and len(files) <= MAX_FILES, 'bad-file-set')
    total = 0
    for name, entry in files.items():
        valid_path(name)
        require(isinstance(entry, dict) and set(entry) == {'bytes', 'sha256'}, 'bad-file-record')
        require(type(entry['bytes']) is int and 0 <= entry['bytes'] <= LIMIT, 'bad-file-size')
        require(isinstance(entry['sha256'], str) and ID.fullmatch(entry['sha256']), 'bad-file-hash')
        total += entry['bytes']
    require(total <= LIMIT, 'expanded-limit')
    return total

class Store:
    """Single serialized transaction; directories and socket are root-owned."""
    def __init__(self, base, host):
        self.base, self.host = Path(base), host
        self.releases = self.base / 'releases'
        self.active_file = self.base / 'active.json'
        self.record = self.base / 'transaction.json'
        self.archive = self.base / 'incoming.zip'
        self.staging = self.base / 'staging'
        self.config = read_json(self.base / 'config.json')

    def active(self):
        result = read_json(self.active_file)
        require(ID.fullmatch(result['release']), 'bad-active-release')
        return result

    def transaction(self):
        return read_json(self.record) if self.record.exists() else None

    def save(self, txn, state=None, reason=None):
        if state:
            txn['state'] = state
        if reason:
            txn['reason'] = reason
        txn['updated'] = time.time()
        atomic_json(self.record, txn)

    def status(self):
        self.config = read_json(self.base / 'config.json')
        txn = self.transaction()
        return dict(protocol='GUIDE-DEPLOY-1', device=self.config['device'], active=self.active(),
                    transaction=txn, limit_bytes=LIMIT, enabled=self.config['enabled'],
                    scope='guide-shell-and-input', previous=self.previous())

    def previous(self):
        path = self.base / 'previous.json'
        return read_json(path) if path.exists() else None

    def policy(self):
        # Read on every operation, allowing the owner to revoke admission.
        self.config = read_json(self.base / 'config.json')
        require(self.config['enabled'] is True, 'deployment-disabled')

    def begin(self, identity, size, base):
        self.policy()
        require(isinstance(identity, str) and ID.fullmatch(identity), 'bad-transaction-id')
        require(type(size) is int and 0 < size <= LIMIT, 'transfer-limit')
        txn = self.transaction()
        if txn and txn['id'] == identity:
            require(txn['bytes'] == size and txn['base'] == base, 'transaction-conflict')
            if txn['state'] not in ('cancelled', 'rejected'):
                return txn
        require(base == self.active()['release'], 'stale-base')
        require(not txn or txn['state'] in ('committed', 'rolled-back', 'cancelled', 'rejected'), 'transaction-busy')
        # Do not prune active/previous releases to make room for an update.
        # Reserve for the archive actually being received. Validation separately
        # checks the authenticated expanded payload before extraction, so holding
        # another full LIMIT here rejects small updates on otherwise healthy images.
        require(shutil.disk_usage(self.base).free >= size + 32_000_000, 'insufficient-storage')
        self.archive.unlink(missing_ok=True)
        if self.staging.exists():
            shutil.rmtree(self.staging)
        with open(self.archive, 'xb') as stream:
            stream.flush()
            os.fsync(stream.fileno())
        txn = dict(id=identity, bytes=size, base=base, received=0, state='receiving')
        self.save(txn)
        return txn

    def matching(self, identity, states):
        txn = self.transaction()
        require(txn and txn['id'] == identity and txn['state'] in states, 'transaction-state')
        return txn

    def chunk(self, identity, offset, data):
        self.policy()
        txn = self.matching(identity, ('receiving',))
        require(type(offset) is int and offset == txn['received'], 'offset-mismatch')
        require(isinstance(data, bytes) and 0 < len(data) <= CHUNK and offset + len(data) <= txn['bytes'], 'chunk-limit')
        # On crash, unacknowledged bytes are truncated to the durable checkpoint.
        with open(self.archive, 'r+b') as stream:
            stream.truncate(offset)
            stream.seek(offset)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        txn['received'] += len(data)
        self.save(txn)
        return txn['received']

    def validate(self, identity):
        self.policy()
        txn = self.matching(identity, ('receiving', 'validated'))
        if txn['state'] == 'validated':
            return txn
        require(txn['received'] == txn['bytes'] and digest(self.archive) == identity, 'incomplete-or-corrupt')
        try:
            with zipfile.ZipFile(self.archive) as archive:
                entries = archive.infolist()
                require(len(entries) <= MAX_FILES + 1, 'too-many-files')
                names = [entry.filename for entry in entries]
                require(len(set(names)) == len(names) and 'manifest.json' in names, 'duplicate-or-missing-manifest')
                for entry in entries:
                    mode = entry.external_attr >> 16
                    require(not entry.is_dir() and not stat.S_ISLNK(mode)
                            and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                            and entry.compress_type == zipfile.ZIP_STORED and entry.flag_bits & 1 == 0,
                            'unsupported-archive-entry')
                    require(entry.file_size == entry.compress_size and entry.file_size <= LIMIT, 'archive-limit')
                require(archive.getinfo('manifest.json').file_size <= MANIFEST_LIMIT, 'metadata-too-large')
                manifest = json.loads(archive.read('manifest.json'))
                total = validate_manifest(manifest, self.config['device'], self.active()['release'])
                require(set(names) == {'manifest.json'} | set(manifest['files']), 'undeclared-content')
                require(shutil.disk_usage(self.base).free >= total + 32_000_000, 'insufficient-storage')
                if self.staging.exists():
                    shutil.rmtree(self.staging)
                self.staging.mkdir(mode=0o755)
                self.staging.chmod(0o755)
                for name, entry in manifest['files'].items():
                    require(archive.getinfo(name).file_size == entry['bytes'], 'file-size-mismatch')
                    target = self.staging / name
                    target.parent.mkdir(exist_ok=True)
                    target.parent.chmod(0o755)
                    with archive.open(name) as source, open(target, 'xb') as output:
                        shutil.copyfileobj(source, output, CHUNK)
                        output.flush()
                        os.fsync(output.fileno())
                    require(digest(target) == entry['sha256'], 'file-hash-mismatch')
                    target.chmod(0o644)
                atomic_json(self.staging / 'manifest.json', manifest)
                for directory in (self.staging / 'shell0', self.staging / 'input', self.staging / 'assets'):
                    if directory.exists():
                        sync_dir(directory)
                sync_dir(self.staging)
            self.host.check_candidate(self.staging)
            txn['candidate'] = identity
            txn['version'] = manifest['version']
            self.save(txn, 'validated')
            return txn
        except (Rejected, ValueError, zipfile.BadZipFile, OSError) as exc:
            self.save(txn, 'rejected', str(exc) if isinstance(exc, Rejected) else 'invalid-package')
            raise Rejected(txn['reason']) from None

    def cancel(self, identity):
        txn = self.matching(identity, ('receiving', 'validated', 'queued', 'cancelled'))
        self.save(txn, 'cancelled')
        self.archive.unlink(missing_ok=True)
        if self.staging.exists():
            shutil.rmtree(self.staging)
        return txn

    def queue(self, identity):
        self.policy()
        txn = self.matching(identity, ('validated', 'queued', 'activating', 'trial', 'committed', 'rolled-back'))
        if txn['state'] == 'validated':
            require(txn['base'] == self.active()['release'], 'stale-base')
            self.save(txn, 'queued')
        if txn['state'] == 'queued':
            self.host.schedule()
        return txn

    def apply(self):
        txn = self.transaction()
        if not txn or txn['state'] != 'queued':
            return
        try:
            self.policy()
            require(txn['base'] == self.active()['release'], 'stale-base')
            self.host.admit()
            self.host.quiesce(txn['id'])
        except Rejected as exc:
            self.host.unquiesce()
            self.save(txn, 'validated', str(exc))
            return
        txn['old'] = self.active()
        self.save(txn, 'activating')  # durable recovery intent BEFORE stopping or switching
        try:
            self.host.stop()
            target = self.releases / txn['candidate']
            if txn.get('mode') != 'rollback':
                require(not target.exists(), 'release-already-present')
                os.replace(self.staging, target)
                sync_dir(self.releases)
            else:
                require(target.is_dir() and not target.is_symlink(), 'previous-release-missing')
            atomic_json(self.active_file, dict(release=txn['candidate'], version=txn['version']))
            self.save(txn, 'trial')
            self.host.unquiesce()
            self.host.start()
            self.host.healthy(txn['candidate'])
            atomic_json(self.base / 'previous.json', txn['old'])
            self.save(txn, 'committed')
            self.archive.unlink(missing_ok=True)
            self.prune()
        except Exception as exc:
            self.restore(txn, str(exc) if isinstance(exc, Rejected) else 'activation-failed')

    def restore(self, txn, reason, boot=False):
        self.save(txn, 'recovering', reason)
        try:
            if not boot:
                self.host.stop(recovery=True)
            atomic_json(self.active_file, txn['old'])
            self.host.unquiesce()
            if not boot:
                self.host.start()
                self.host.healthy(txn['old']['release'])
            self.save(txn, 'rolled-back', reason)
            if boot:
                txn['health'] = 'pending-boot'
                self.save(txn)
            self.prune()
        except Exception:
            self.save(txn, 'repair-required', 'recovery-failed')

    def recover(self):
        txn = self.transaction()
        if txn and txn['state'] in ('activating', 'trial', 'recovering'):
            self.restore(txn, 'interrupted-activation', boot=True)
        elif txn and txn['state'] == 'queued':
            self.save(txn, 'validated', 'activation-interrupted-before-start')
        self.host.unquiesce()

    def rescue(self):
        txn = self.transaction()
        if txn and txn['state'] in ('activating', 'trial', 'recovering'):
            self.restore(txn, 'activation-worker-failed')
        else:
            self.recover()

    def rollback(self):
        self.policy()
        txn = self.transaction()
        require(not txn or txn['state'] in ('committed', 'rolled-back', 'cancelled', 'rejected'), 'transaction-busy')
        previous = self.previous()
        require(previous and previous != self.active(), 'no-previous-release')
        txn = dict(id=hashlib.sha256(canonical([previous, time.time_ns()])).hexdigest(),
                   candidate=previous['release'], version=previous['version'], mode='rollback',
                   state='queued', bytes=0, received=0, base=self.active()['release'])
        self.save(txn)
        self.host.schedule()
        return txn

    def prune(self):
        keep = {self.active()['release']}
        previous = self.previous()
        if previous:
            keep.add(previous['release'])
        for path in self.releases.iterdir():
            if ID.fullmatch(path.name) and path.name not in keep and path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
