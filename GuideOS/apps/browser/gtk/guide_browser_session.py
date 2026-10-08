#!/usr/bin/env python3
"""Run packaged Weston plus GTK; the service owns the process lifetime."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from guide_browser_drm import find_display_card


def stop(child):
    # Include WebKit/compositor descendants even if the immediate child exited.
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait(timeout=3)


def run(headless=False, runtime_path=None):
    raise RuntimeError('Web browsing is paused for now')


def retained_session(headless=False, runtime_path=None):
    # Retained implementation for a later integration. The installed entry
    # point above never starts Weston or imports WebKit in this release.
    if os.geteuid() == 0:
        raise RuntimeError('Browser session must run as its unprivileged user')
    if runtime_path:
        os.environ['XDG_RUNTIME_DIR'] = runtime_path
    if not headless:
        sys.path.insert(0, '/usr/lib/guideos/resources')
        from resource_host import verify_browser_limits
        # PAM moved this process into a login scope. Check the real ancestor,
        # not just the launcher's configured properties, before creating WebKit.
        verify_browser_limits()
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    socket_name = 'guide-browser-wayland'
    wayland = runtime / socket_name
    control = runtime / 'control.sock'
    if wayland.exists() or control.exists():
        raise RuntimeError('Browser session is already present; do not replace its sockets')
    children = []
    stopping = False
    def request_stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        args = ['weston', '--socket=' + socket_name, '--idle-time=0',
                '--shell=kiosk-shell.so', '--no-config']
        if headless:
            args += ['--backend=headless-backend.so', '--renderer=pixman',
                     '--width=640', '--height=480']
        else:
            # Identify the H700 display controller by its driver. DRM card
            # numbers are assigned dynamically and are not a stable identity.
            card = find_display_card()
            args += ['--backend=drm-backend.so', '--drm-device=' + card]
        compositor = subprocess.Popen(args, start_new_session=True)
        children.append(compositor)
        deadline = time.monotonic() + 15
        while not wayland.exists():
            if stopping or compositor.poll() is not None:
                return 1
            if time.monotonic() > deadline:
                raise RuntimeError('Display session startup timed out')
            time.sleep(.05)
        # The 640x480 toolbar/keyboard does not need a second GPU scene renderer.
        # WebKit retains its own page rendering; this choice is local to GTK.
        env = dict(os.environ, WAYLAND_DISPLAY=socket_name, GDK_BACKEND='wayland',
                   GSK_RENDERER='cairo')
        browser = subprocess.Popen([sys.executable,
            str(Path(__file__).with_name('guide_browser.py')),
            '--fullscreen', '--control', str(control)], env=env, start_new_session=True)
        children.append(browser)
        while not stopping and browser.poll() is None and compositor.poll() is None:
            time.sleep(.1)
        if stopping:
            return 0
        return browser.returncode if browser.returncode is not None else 1
    finally:
        for child in reversed(children):
            stop(child)
        # Owned private runtime only; systemd also removes it when the unit stops.
        if control.exists():
            control.unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--runtime')
    args = parser.parse_args()
    raise SystemExit(run(args.headless, args.runtime))
