"""Resolve the immutable browser generation without changing the Home renderer."""
import os
from pathlib import Path
from deploy_core import read_json,require,ID
base=Path('/opt/guideos/deploy');active=read_json(base/'active.json')
require(ID.fullmatch(active['release']),'bad-active-release')
entry=base/'releases'/active['release']/'browser/guide_browser_session.py'
# The bootstrap browser is fixed until the first signed release includes it.
if not entry.is_file():entry=Path('/usr/lib/guideos/browser/guide_browser_session.py')
os.execv('/usr/bin/python3',['python3',str(entry),'--runtime','/run/guideos-browser'])
