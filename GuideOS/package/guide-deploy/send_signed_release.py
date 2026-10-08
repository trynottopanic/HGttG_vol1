"""UI calls run off the drawing loop. Existing pinned SSH transport is reused."""
import argparse,base64,json
from pathlib import Path
from deploy_core import digest,CHUNK
from guide_deploy import Remote

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);p.add_argument('--profile',type=Path,required=True);p.add_argument('--host',required=True);a=p.parse_args()
    remote=Remote(json.loads(a.profile.read_text()),a.host)
    try:
        status=remote.request('status')
        if status['protocol']!='GUIDE-SIGNED-BUNDLE-1':raise ValueError('Deck needs signed updater bootstrap')
        identity=digest(a.bundle);txn=remote.request('begin',id=identity,bytes=a.bundle.stat().st_size,base=status['active']['release'])
        if txn['state']=='receiving':
            with a.bundle.open('rb') as stream:
                stream.seek(txn['received']);offset=txn['received']
                while block:=stream.read(CHUNK):
                    result=remote.request('chunk',id=identity,offset=offset,data=base64.b64encode(block).decode());offset=result['received']
            txn=remote.request('validate',id=identity)
        print(json.dumps(dict(state=txn['state'],message='Review and install in Deck Updates',id=identity)))
    finally:remote.close()
