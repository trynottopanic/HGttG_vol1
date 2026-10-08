#!/usr/bin/python3
"""TF2 read-only recognition provider. No installation or application grants.

Board identity is supplied by the board's systemd unit. Status is a private
shell integration snapshot, not the future shared broker wire contract.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

RUNTIME = Path('/run/guideos-storage')
MOUNT = RUNTIME / 'card'
LIMIT = 512
FOLDERS = ('CARTRIDGES', 'APPLICATIONS', 'MEDIA', 'DOCUMENTS', 'GENERAL', 'MISC')
SUPPORTED = {'exfat', 'vfat', 'ext4'}

class InvalidLayout(Exception):
    pass


def children(fd):
    result = {}
    with os.scandir(fd) as entries:
        for index, entry in enumerate(entries):
            if index >= LIMIT:
                raise InvalidLayout('Directory has too many entries to recognize')
            key = entry.name.upper()
            result.setdefault(key, []).append(entry.name)
    return result


def directory(fd, names, name):
    matches = names.get(name, [])
    if len(matches) > 1:
        raise InvalidLayout('Conflicting folder names')
    if not matches:
        return None
    try:
        return os.open(matches[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    except OSError as exc:
        raise InvalidLayout('Guide folders must be real directories') from exc


def recognize(root):
    """Bounded directory evidence only; no package trust or execution implied."""
    fds = []
    try:
        top = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW); fds.append(top)
        guide = directory(top, children(top), 'GUIDE')
        if guide is None:
            return dict(state='ordinary', message='Readable card; no GUIDE folder', folders=[])
        fds.append(guide)
        names = children(guide)
        found = []
        packages = 0
        capped = False
        for name in FOLDERS:
            folder = directory(guide, names, name)
            if folder is None:
                continue
            try:
                found.append(name)
                if name == 'APPLICATIONS':
                    apps = children(folder)
                    for sub in ('GAMES', 'BIOS'):
                        child = directory(folder, apps, sub)
                        if child is not None:
                            found.append(name + '/' + sub); os.close(child)
                if name == 'CARTRIDGES':
                    with os.scandir(folder) as entries:
                        for index, entry in enumerate(entries):
                            if index >= LIMIT:
                                capped = True; break
                            if entry.name.lower().endswith('.guide') and entry.is_file(follow_symlinks=False):
                                packages += 1
            finally:
                os.close(folder)
        return dict(state='guide' if found else 'incomplete',
                    message='Guide layout recognized' if found else 'GUIDE folder has no standard folders',
                    folders=found, packages=packages, count_limited=capped)
    except InvalidLayout as exc:
        return dict(state='invalid', message=str(exc), folders=[])
    finally:
        for fd in reversed(fds):
            os.close(fd)


def discover(controller, base=Path('/sys/class/block')):
    """Pin to the physical TF2 controller, never to a guessed mmcblk number."""
    cards = []
    for disk in base.glob('mmcblk*'):
        if not re.fullmatch(r'mmcblk[0-9]+', disk.name):
            continue
        try:
            if controller not in disk.resolve().parts or (disk/'device/type').read_text().strip() != 'SD':
                continue
            # diskseq distinguishes removal/reinsert even for the same CID.
            identity = tuple((disk/name).read_text().strip() for name in ('device/cid', 'diskseq', 'dev', 'size'))
            parts = sorted(x.name for x in base.glob(disk.name+'p*') if (x/'partition').is_file())
            cards.append(dict(disk=disk.name, identity=identity, devices=parts or [disk.name]))
        except (OSError, ValueError):
            continue
    if len(cards) > 1:
        raise RuntimeError('Ambiguous external slot')
    return cards[0] if cards else None


def command(*args, timeout=8):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=timeout, text=True).stdout.strip()


def mounted_devices(text):
    return {line.split()[2] for line in text.splitlines() if len(line.split()) >= 6}


def device_number(name):
    if not re.fullmatch(r'mmcblk[0-9]+(?:p[0-9]+)?', name):
        raise ValueError('Invalid device')
    expected = (Path('/sys/class/block')/name/'dev').read_text().strip()
    info = os.stat('/dev/'+name)
    if not stat.S_ISBLK(info.st_mode) or expected != f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}':
        raise ValueError('Device identity changed')
    return expected


def probe(controller):
    card = discover(controller)
    if not card:
        return dict(state='absent', message='No card in external slot', folders=[])
    mounted = mounted_devices(Path('/proc/self/mountinfo').read_text())
    # Refuse every partition of an already-mounted card, including the seed.
    all_names = [card['disk']] + card['devices']
    if any(device_number(name) in mounted for name in set(all_names)):
        return dict(state='busy', message='Card already mounted by another owner', folders=[])
    usable = []
    for name in card['devices']:
        try:
            kind = command('/usr/sbin/blkid', '-p', '-s', 'TYPE', '-o', 'value', '/dev/'+name)
        except subprocess.CalledProcessError:
            continue
        if kind in SUPPORTED:
            usable.append((name, kind))
    if len(usable) != 1:
        return dict(state='unsupported', message='Choose a card with one exFAT, FAT or ext4 volume' if not usable
                    else 'Multiple readable volumes; card is ambiguous', folders=[])
    name, kind = usable[0]
    if discover(controller) != card:
        raise RuntimeError('Card changed during recognition')
    number = device_number(name)
    options = 'ro,nodev,nosuid,noexec,noatime' + (',noload' if kind == 'ext4' else ',iocharset=utf8')
    command('/usr/bin/mount', '-t', kind, '-o', options, '/dev/'+name, str(MOUNT))
    rows = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    if not any(row[2] == number and row[4] == str(MOUNT) and
               {'ro','nodev','nosuid','noexec'} <= set(row[5].split(',')) for row in rows):
        raise RuntimeError('Read-only mount not verified')
    result = recognize(MOUNT)
    if discover(controller) != card:
        raise RuntimeError('Card removed during recognition')
    result.update(filesystem=kind, capacity_bytes=int(card['identity'][3])*512)
    return result


def publish(result):
    value = dict(result, updated=time.monotonic())
    temporary = RUNTIME/'status.tmp'
    temporary.write_text(json.dumps(value), encoding='ascii')
    temporary.chmod(0o644)
    temporary.replace(RUNTIME/'status.json')


def unmount():
    # A removed card can make stat/lstat fail, so ismount() can report False
    # while the kernel still holds its mount. Inspect our namespace instead;
    # never touch the departed filesystem just to decide whether to detach it.
    rows = (line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines())
    if any(len(row) >= 6 and row[4] == str(MOUNT) for row in rows):
        command('/usr/bin/umount', '-l', str(MOUNT))


def serve(controller, catalog_factory=None, wait=None, media_factory=None, files_factory=None):
    RUNTIME.mkdir(mode=0o755, exist_ok=True); MOUNT.mkdir(mode=0o700, exist_ok=True)
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    import select
    for location in ('/usr/lib/guideos/installer','/usr/lib/guideos/ipc'):
        if location not in sys.path:sys.path.insert(0,location)
    from cartridge_catalog import Catalog
    catalog=(catalog_factory or Catalog)(MOUNT,lambda:discover(controller))
    catalog.connect(RUNTIME/'cartridges.sock')
    media=media_factory(MOUNT) if media_factory else None
    files = None
    def enable_card_writes():
        # Only the mount owner may change access. ext4 noload mounts stay read-only.
        if result.get('filesystem') not in ('exfat','vfat') or discover(controller)!=previous:
            return False
        command('/usr/bin/mount','-o','remount,rw,nodev,nosuid,noexec',str(MOUNT))
        rows=[line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
        allowed=any(row[4]==str(MOUNT) and {'rw','nodev','nosuid','noexec'}<=set(row[5].split(',')) for row in rows)
        if allowed:result['writable']=True
        return allowed
    if files_factory or os.environ.get('GUIDE_FILES')=='1':
        from storage_files import Files
        files=(files_factory or Files)(MOUNT,Path('/data/guideos/files'),lambda:discover(controller),enable_card_writes)
        files.write_available=lambda:result.get('filesystem') in ('exfat','vfat')
        files.connect()
    previous = None
    generation = 0
    retry = 0
    result = dict(state='absent', message='No card in external slot', folders=[], generation=generation)
    try:
        unmount()
        while not stopped:
            card = discover(controller)
            if card != previous:
                generation += 1
            if card != previous or (card and result['state'] in ('absent','error','busy','unsupported') and time.monotonic() >= retry):
                catalog.invalidate()
                if files:files.refresh(None,generation)
                unmount()
                result = dict(state='absent', message='No card in external slot', folders=[], generation=generation)
                if media:
                    media.invalidate(generation)
                if card:
                    publish(dict(state='checking', message='Reading external card', folders=[], generation=generation))
                    try:
                        raw = command(sys.executable, str(Path(__file__).resolve()), '--controller', controller, '--probe', timeout=25)
                        result = json.loads(raw)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                        unmount()
                        result = dict(state='error', message='Card could not be read; retrying automatically', folders=[], generation=generation)
                    if discover(controller) != card:
                        unmount(); previous = None; continue
                previous = card; retry = time.monotonic()+10
                result['generation'] = generation
                if result['state']=='guide':catalog.invalidate(card)
                if media:
                    try:
                        media.refresh(result)
                        result['media_library']='ready'
                    except Exception:
                        result['media_library']='failed'
            if files:files.refresh(previous if result['state'] in ('guide','ordinary','incomplete') else None,generation)
            publish(result)
            if wait:wait(catalog)
            else:
                until=time.monotonic()+1
                while not stopped and time.monotonic()<until:
                    listeners=[catalog.listener]
                    if files:listeners.append(files.listener)
                    if media and media.listener:listeners.append(media.listener)
                    ready=select.select(listeners,[],[],min(.1,max(0,until-time.monotonic())))[0]
                    if catalog.listener in ready:catalog.poll()
                    if files and files.listener in ready:files.poll()
                    if files:files.tick()
                    if media and media.listener in ready:media.poll()
                    if media and hasattr(media,"tick"):media.tick()
    finally:
        if files:files.close()
        if media:
            media.invalidate(generation);media.close()
        catalog.invalidate();catalog.close()
        unmount()
        publish(dict(state='unavailable', message='Card service stopped', folders=[], generation=generation))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--controller', required=True)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe(args.controller)))
    else:
        media_factory = None
        if os.environ.get('GUIDE_MEDIA_LIBRARY') == '1':
            # The media runtime imports shared IPC before serve() initializes
            # the cartridge provider. Establish both dependencies first.
            for location in ('/usr/lib/guideos/ipc', '/usr/lib/guideos/media'):
                if location not in sys.path:
                    sys.path.insert(0, location)
            from storage_media_runtime import create_storage_media_host
            def media_factory(mount):
                listen_pid = int(os.environ.get('LISTEN_PID', '0'))
                listen_fds = int(os.environ.get('LISTEN_FDS', '0'))
                if listen_pid != os.getpid() or listen_fds != 1:
                    raise RuntimeError('Media Library socket was not supplied by systemd')
                return create_storage_media_host(mount, endpoint=__import__('socket').socket(fileno=3),
                    internal_source=os.environ.get('GUIDE_MEDIA_PLAYER')=='1')
        serve(args.controller, media_factory=media_factory)
