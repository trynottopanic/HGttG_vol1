#!/usr/bin/env python3
"""Stage browser files into an offline root; no package installs or live services."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('root', type=Path)
args=parser.parse_args()
root=args.root.resolve()
if str(root) == '/' or not (root/'etc/os-release').is_file():
    raise SystemExit('Select an offline image root containing etc/os-release')
source=Path(__file__).resolve().parent
files={p:'usr/lib/guideos/browser/'+p.name for p in source.glob('guide_*.py')}
files[source/'systemd/guide-browser.service']='usr/lib/systemd/system/guide-browser.service'
files[source/'systemd/guide-browser.sysusers']='usr/lib/sysusers.d/guide-browser.conf'
manifest={}
for src,relative in files.items():
    target=(root/relative).resolve()
    if not target.is_relative_to(root):
        raise SystemExit('Destination escapes the offline root: '+relative)
    if target.exists() and target.read_bytes()!=src.read_bytes():
        raise SystemExit('Refusing to overwrite a different browser file: '+relative)
for src,relative in files.items():
    dst=root/relative
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists() and dst.read_bytes()!=src.read_bytes():
        raise SystemExit('Refusing to overwrite a different browser file: '+relative)
    shutil.copyfile(src,dst)
    dst.chmod(0o644)
    manifest[relative]=hashlib.sha256(dst.read_bytes()).hexdigest()
print(json.dumps(manifest,indent=2))
