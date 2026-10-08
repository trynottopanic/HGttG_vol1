"""Resolve one generation before exec; workers inherit a fixed release path."""
import os
from pathlib import Path
from deploy_core import read_json, ID, require

base = Path('/opt/guideos/deploy')
active = read_json(base / 'active.json')
require(ID.fullmatch(active['release']), 'bad-active-release')
release = base / 'releases' / active['release']
require(release.is_dir() and not release.is_symlink(), 'missing-release')
os.environ.update(GUIDE_RELEASE_ID=active['release'], GUIDE_BUILD_ID=active['version'],
                  GUIDE_DEPLOY_RUNTIME='/run/guideos-deploy', PYTHONDONTWRITEBYTECODE='1',
                  PYTHONPATH='/usr/lib/guideos/deploy')
os.execv('/usr/bin/python3', ['python3', str(release / 'shell0/guide_shell.py')])
