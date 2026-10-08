"""End all dedicated Browser-session helpers before admitting display recovery."""
import os
from pathlib import Path
import subprocess
import time
from resource_host import browser_group, fields


def cleanup_group(group):
    if group.exists() and fields(group/'cgroup.events').get('populated')=='1':
        fd=os.open(group,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            frozen=os.open('cgroup.freeze',os.O_WRONLY,dir_fd=fd)
            try:os.write(frozen,b'0\n')
            finally:os.close(frozen)
            kill=os.open('cgroup.kill',os.O_WRONLY,dir_fd=fd)
            try:os.write(kill,b'1\n')
            finally:os.close(kill)
        finally:os.close(fd)
        deadline=time.monotonic()+2
        while group.exists() and fields(group/'cgroup.events').get('populated')!='0' and time.monotonic()<deadline:
            time.sleep(.02)
        if group.exists() and fields(group/'cgroup.events').get('populated')!='0':
            raise RuntimeError('Browser session has not exited')


def main():
    cleanup_group(browser_group())
    # Leave the resident overlay visible if an owner recovery is in progress.
    if Path('/sys/class/tty/tty0/active').read_text().strip()=='tty2':
        subprocess.run(['chvt','1'],check=True,timeout=2)


if __name__=='__main__':main()
