"""Install resource controls in an offline Debian image, resolving its real UID."""
import argparse
from pathlib import Path
import shutil


def stage(root):
    root=Path(root).resolve()
    if root==Path('/') or not (root/'etc/debian_version').is_file():
        raise ValueError('An offline Debian root is required')
    users=[line.split(':') for line in (root/'etc/passwd').read_text().splitlines()]
    browser=next(row for row in users if row[0]=='guide-browser')
    uid=int(browser[2])
    if uid==0 or sum(int(row[2])==uid for row in users)!=1:
        raise ValueError('Browser needs a dedicated non-root UID')
    source=Path(__file__).resolve().parent
    files={}
    def write(relative, text):
        dest=root/relative
        if not dest.resolve().is_relative_to(root):raise ValueError('Image path escapes root')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(text);dest.chmod(0o644);files[relative]=text
    for name in ('resource_host.py','resource_guard.py','zram_setup.py','browser_cleanup.py'):
        write('usr/lib/guideos/resources/'+name,(source/name).read_text())
    for name in ('guide-resources.service','guide-zram.service'):
        write('etc/systemd/system/'+name,(source/name).read_text())
        link=root/'etc/systemd/system/multi-user.target.wants'/name
        link.parent.mkdir(parents=True,exist_ok=True)
        if not link.exists():link.symlink_to('../'+name)
    write(f'etc/systemd/system/user-{uid}.slice.d/50-guide-browser-resources.conf',
          '[Slice]\nMemoryAccounting=yes\nMemoryHigh=320M\nMemoryMax=384M\nMemorySwapMax=64M\nTasksMax=256\n')
    write('etc/systemd/system/guide-resources.service.d/51-guide-browser-group.conf',
          f'[Unit]\nRequires=user-{uid}.slice\nAfter=user-{uid}.slice\n')
    protections={'system.slice':('[Slice]',48,192), 'guide-control.service':('[Service]',24,48),
        'systemd-logind.service':('[Service]',8,16), 'dbus.service':('[Service]',8,16),
        'guide-resources.service':('[Service]',8,16)}
    for unit,(section,minimum,low) in protections.items():
        write(f'etc/systemd/system/{unit}.d/50-guide-critical-memory.conf',
              f'{section}\nMemoryMin={minimum}M\nMemoryLow={low}M\n'+
              ('OOMScoreAdjust=-900\n' if section=='[Service]' else ''))
    write('etc/systemd/system/guide-shell.service.d/50-guide-memory.conf',
          '[Service]\nMemoryLow=64M\nMemoryHigh=192M\nMemoryMax=256M\nTasksMax=128\n')
    write('etc/systemd/system/guide-browser.service.d/50-guide-resources.conf',
          f'[Unit]\nRequires=guide-resources.service user-{uid}.slice\nAfter=guide-resources.service user-{uid}.slice\n'
          '[Service]\nMemoryHigh=320M\nMemoryMax=384M\nMemorySwapMax=64M\nOOMPolicy=kill\nOOMScoreAdjust=300\n'
          'CacheDirectory=guideos-browser\nCacheDirectoryMode=0700\n'
          'Environment=XDG_CACHE_HOME=/var/cache/guideos-browser\nEnvironment=MESA_SHADER_CACHE_MAX_SIZE=16M\n'
          'ReadWritePaths=-/sys/fs/cgroup/user.slice\n'
          'ExecStopPost=\nExecStopPost=+/usr/bin/python3 /usr/lib/guideos/resources/browser_cleanup.py\n')
    write('etc/systemd/system/guide-shell.service.d/51-guide-overlay.conf',
          '[Service]\nEnvironment=GUIDE_CONTROL_SOCKET=/run/guideos-control/input.sock\n')
    # The overlay owns VT3; logind must not start an automatic text login there.
    for name in ('getty@tty3.service','autovt@tty3.service'):
        path=root/'etc/systemd/system'/name
        if path.is_symlink() and path.readlink()==Path('/dev/null'):continue
        if path.exists() or path.is_symlink():raise ValueError('Overlay VT already has configured ownership')
        path.symlink_to('/dev/null')
    return sorted(files)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path)
    print('\n'.join(stage(parser.parse_args().root)))
