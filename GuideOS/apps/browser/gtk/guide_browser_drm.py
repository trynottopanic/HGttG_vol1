"""Find the RG35XX H display controller without assuming DRM card numbering."""
import os
from pathlib import Path
import re

_CARD_NAME = re.compile(r"card[0-9]+\Z")


def find_display_card():
    """Return a Weston cardN identifier for the accessible sun4i display device."""
    drm_root = Path('/sys/class/drm')
    dev_root = Path('/dev/dri')
    found_driver = False
    for entry in sorted(drm_root.glob('card[0-9]*')):
        if not _CARD_NAME.fullmatch(entry.name):
            continue
        try:
            driver = (entry / 'device' / 'driver').resolve(strict=True).name
        except OSError:
            continue
        if driver != 'sun4i-drm':
            continue
        found_driver = True
        device = dev_root / entry.name
        if not device.exists():
            continue
        if not os.access(device, os.R_OK | os.W_OK):
            raise RuntimeError('Deck display device /dev/dri/' + entry.name + ' is not accessible to guide-browser')
        return entry.name
    if found_driver:
        raise RuntimeError('Deck sun4i display controller has no usable /dev/dri device node')
    raise RuntimeError('Deck display controller (sun4i-drm) was not found under /sys/class/drm')
