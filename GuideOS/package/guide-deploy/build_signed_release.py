"""Offline signer and bootstrap helper. Private keys stay on the development PC."""
import argparse,hashlib,json,os,sys,zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from signed_release import canonical,identity,PROFILE
from deploy_core import valid_path,digest,LIMIT,atomic_json

def build(release,output,seed,version,sequence,base_sequence,state_schema=1):
    from release_version import valid_build_label
    if not valid_build_label(version):raise ValueError('Use 0.4.3.xx with a two-digit revision from 01 to 99; historical 0.4.2 labels remain supported')
    release,output=Path(release),Path(output)
    if output.exists():raise ValueError('Output exists')
    key=Ed25519PrivateKey.from_private_bytes(seed)
    pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    files=[]
    for path in sorted(release.rglob('*')):
        if path.is_symlink():raise ValueError('No links in release')
        if path.is_dir() or path.name in ('manifest.json','signed-manifest.json'):continue
        name=path.relative_to(release).as_posix();valid_path(name)
        files.append(dict(path='payload/'+name,size=path.stat().st_size,sha256=digest(path)))
    files.sort(key=lambda x:x['path'].encode('utf-8'))
    p=dict(version=version,releaseSequence=sequence,baseReleaseSequences=[base_sequence],power='external',strategy='immutable-release-switch-v1',serviceProfile='guide-shell-v1',healthProfile='guide-shell-v1',trialSeconds=20,rollback='previous-release',state=dict(resultSchema=state_schema,acceptedInputSchemas=[state_schema],migration='none'))
    m=dict(format='GUIDE-SIGNED-BUNDLE-1',bundleId='',profile=dict(id=PROFILE,version=1,manifest=p),target=dict(product='GuideOS',architectures=['arm64'],boardProfiles=['rg35xx-h']),requirements=dict(archiveBytes=0,payloadBytes=sum(f['size'] for f in files),requiredFreeBytes=sum(f['size'] for f in files)+32_000_000),files=files,signing=dict(algorithm='Ed25519',keyId='sha256:'+hashlib.sha256(pub).hexdigest()),extensions={})
    temporary=output.with_name(output.name+'.building')
    if temporary.exists():raise ValueError('Build already exists')
    try:
        for _ in range(8):
            m['bundleId']=identity(m);raw=canonical(m)
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
                z.writestr('manifest.json',raw);z.writestr('manifest.ed25519',key.sign(b'Guide signed bundle signature v1\0'+raw))
                for f in files:z.write(release/f['path'][8:],f['path'])
            size=temporary.stat().st_size
            if size>LIMIT:raise ValueError('Release exceeds 100 MB')
            if size==m['requirements']['archiveBytes']:
                # Publish without silently replacing an existing output.
                os.link(temporary,output);return m,pub
            m['requirements']['archiveBytes']=size
        raise ValueError('Size convergence failed')
    finally:temporary.unlink(missing_ok=True)

def trust(base,pub):
    base=Path(base);folder=base/'trust';folder.mkdir(mode=0o700,exist_ok=True)
    identity=hashlib.sha256(pub).hexdigest()
    record=dict(publicKey=pub.hex(),profiles=[PROFILE],product='GuideOS',architectures=['arm64'],boards=['rg35xx-h'])
    target=folder/(identity+'.json')
    if target.exists() and json.loads(target.read_text())!=record:raise ValueError('Trust record conflict')
    new=not target.exists()
    public=folder/(identity+'.pub')
    if not public.exists():
        with public.open('xb') as f:f.write(pub);f.flush();os.fsync(f.fileno())
    atomic_json(target,record)
    if new:
        journal=folder/'journal';journal.mkdir(mode=0o700,exist_ok=True)
        import time
        atomic_json(journal/(str(time.time_ns())+'.json'),dict(action='add-public-key',keyId=identity,profiles=[PROFILE]))
    return identity

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('release',type=Path);p.add_argument('output',type=Path);p.add_argument('--key',required=True,type=Path);p.add_argument('--version',required=True);p.add_argument('--sequence',required=True,type=int);p.add_argument('--base-sequence',required=True,type=int);a=p.parse_args()
    m,_=build(a.release,a.output,a.key.read_bytes(),a.version,a.sequence,a.base_sequence)
    print(json.dumps(dict(bundleId=m['bundleId'],bytes=a.output.stat().st_size,sha256=digest(a.output))))
