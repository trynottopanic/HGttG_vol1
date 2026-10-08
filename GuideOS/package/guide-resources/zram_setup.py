"""Bounded compressed RAM swap; never falls back to a Seed swapfile."""
from pathlib import Path
import subprocess


def run(*args):
    subprocess.run(args, check=True, timeout=5)


def main():
    run('modprobe', 'zram', 'num_devices=1')
    root = Path('/sys/block/zram0')
    if int((root/'disksize').read_text()) != 0:
        raise RuntimeError('zram0 already belongs to another owner')
    algorithms=(root/'comp_algorithm').read_text().replace('[','').replace(']','').split()
    if 'lzo-rle' not in algorithms:
        raise RuntimeError('Required bounded zram compressor unavailable')
    (root/'comp_algorithm').write_text('lzo-rle\n')
    (root/'disksize').write_text(str(128*1024**2)+'\n')
    (root/'mem_limit').write_text(str(64*1024**2)+'\n')
    run('mkswap', '/dev/zram0')
    run('swapon', '--priority', '100', '/dev/zram0')


if __name__ == '__main__':
    main()
