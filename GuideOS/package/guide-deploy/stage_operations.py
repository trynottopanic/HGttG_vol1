"""Stage fixed services into an offline root; never write a physical device."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from deploy_core import read_json,atomic_json
from build_signed_release import trust

def stage(root,data,public,sequence,state_schema):
    root,data=Path(root).resolve(),Path(data).resolve()
    if root==Path('/') or data==Path('/') or root==data or not (root/'etc/os-release').is_file():raise ValueError('Offline root and data partition required')
    if len(public)!=32:raise ValueError('Raw Ed25519 public key must be 32 bytes')
    for relative in ('opt/guideos/deploy','var/lib/guideos/update','etc/systemd/system/multi-user.target.wants'):
        if not (root/relative).resolve().is_relative_to(root):raise ValueError('Offline system path escapes root')
    base=root/'opt/guideos/deploy'
    config=read_json(base/'config.json');active=read_json(base/'active.json')
    (base/'active.json').chmod(0o644)
    mapping={}
    for folder,destination,patterns in [
        (ROOT/'package/guide-deploy','usr/lib/guideos/deploy',['*.py']),
        (ROOT/'package/guide-transfers','usr/lib/guideos/transfers',['transfers.py','transfer_service.py']),
        (ROOT/'package/guide-storage','usr/lib/guideos/storage',['storage_service.py','storage_files.py']),
        (ROOT/'package/guide-ui','usr/lib/guideos/ui',['guide_ui_model.py','guide_updates_panel.py','guide_transfers_panel.py','guide_files_panel.py','guide_operations_frontend.py']),
        (ROOT/'apps/browser/gtk','usr/lib/guideos/browser',['guide_*.py'])]:
        for pattern in patterns:
            for source in folder.glob(pattern):
                if not source.name.startswith('test_'):mapping[source]=destination+'/'+source.name
    mapping[ROOT/'package/guide-installer/guide_install_wire.py']='usr/lib/guideos/installer/guide_install_wire.py'
    mapping[ROOT/'package/guide-deploy/guide-deploy-apply.service']='usr/lib/systemd/system/guide-deploy-apply.service'
    mapping[ROOT/'package/guide-transfers/guide-transfers.service']='usr/lib/systemd/system/guide-transfers.service'
    mapping[ROOT/'board/rg35xxh/debian/storage/guide-storage.service']='usr/lib/systemd/system/guide-storage.service'
    mapping[ROOT/'apps/browser/gtk/systemd/guide-browser.service']='usr/lib/systemd/system/guide-browser.service'
    mapping[ROOT/'apps/browser/gtk/systemd/guide-browser.sysusers']='usr/lib/sysusers.d/guide-browser.conf'
    for relative in mapping.values():
        if not (root/relative).resolve().is_relative_to(root):raise ValueError('Offline destination escapes root')
    # Data is the separately mounted/captured owner partition, not root/data.
    owner_files=data/'guideos/files'
    if not owner_files.resolve().is_relative_to(data):raise ValueError('Owner files directory escapes data root')
    owner_files.mkdir(parents=True,exist_ok=True,mode=0o700)
    records=[]
    for source,relative in mapping.items():
        target=root/relative;before=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        target.parent.mkdir(parents=True,exist_ok=True);target.parent.chmod(0o755);shutil.copyfile(source,target);target.chmod(0o644)
        records.append(dict(path=relative,before=before,after=hashlib.sha256(target.read_bytes()).hexdigest()))
    # Reuse the deployed release reference while selecting the browser generation.
    unit=root/'usr/lib/systemd/system/guide-browser.service'
    text=unit.read_text(encoding='utf-8').replace('/usr/lib/guideos/browser/guide_browser_session.py --runtime /run/guideos-browser','/usr/lib/guideos/deploy/launch_browser.py')
    unit.write_text(text,encoding='utf-8')
    for record in records:record['after']=hashlib.sha256((root/record['path']).read_bytes()).hexdigest()
    update_base=root/'var/lib/guideos/update';update_base.mkdir(parents=True,exist_ok=True,mode=0o700)
    key=trust(update_base,public)
    config.update(signed_updates=True,board='rg35xx-h',release_sequence=sequence,state_schema=state_schema,trust_root='/var/lib/guideos/update/trust')
    atomic_json(base/'config.json',config)
    wants=root/'etc/systemd/system/multi-user.target.wants';wants.mkdir(parents=True,exist_ok=True)
    link=wants/'guide-transfers.service'
    if not link.exists() and not link.is_symlink():link.symlink_to('/usr/lib/systemd/system/guide-transfers.service')
    return dict(files=records,publicKeyId=key,activeReleasePreserved=read_json(base/'active.json')==active,
                remaining=['Create guide-browser with systemd-sysusers in the offline image','Install resolved ARM64 WebKitGTK/Weston/python3-cryptography/python3-evdev dependencies','Wire Guide panels and browser display lease in the new GUI','Run integrated image and physical acceptance'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--public-key',type=Path,required=True);p.add_argument('--sequence',type=int,required=True);p.add_argument('--state-schema',type=int,default=1);a=p.parse_args()
    print(json.dumps(stage(a.root,a.data,a.public_key.read_bytes(),a.sequence,a.state_schema),indent=2))
