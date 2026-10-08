#!/bin/bash
set -euo pipefail
root=${1:?Mounted Debian root required}
here=$(cd -- "$(dirname -- "$0")" && pwd)
test "$root" != / && test -f "$root/etc/debian_version"
profile=$root/usr/share/alsa/ucm2/Allwinner/sun4i-h616/HiFi.conf
test -f "$profile"
install -m644 "$here/HiFi.conf" "$profile"
install -m644 "$here/60-codec.conf" "$root/etc/guideos/audio/wireplumber/wireplumber.conf.d/60-codec.conf"
# One-time conservative volume migration when introducing the new analog gain.
python3 - "$root" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); folder=root/'var/lib/guideos-audio'
folder.mkdir(parents=True, exist_ok=True)
marker=folder/'codec-gain-v2'
if not marker.exists():
    path=folder/'state.json'
    if path.exists():
        original=path.read_bytes()
        state=json.loads(original)
        backup=folder/'codec-gain-v2-state.json'
        if not backup.exists():
            backup.write_bytes(original)
            backup.chmod(0o600)
        state['volume']=min(20,max(0,int(state.get('volume',20))))
        temporary=path.with_suffix('.gain-v2.tmp')
        temporary.write_text(json.dumps(state))
        temporary.chmod(path.stat().st_mode & 0o777)
        import os
        os.chown(temporary,path.stat().st_uid,path.stat().st_gid)
        temporary.replace(path)
    marker.write_text('RG35XX H speaker DAC=63 line=31; initial software volume <=20\n')
PY
