import hashlib,json,zipfile,io
from pathlib import PurePosixPath
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat

FORMAT='GUIDE-SIGNED-BUNDLE-1'; ABS=2*1024**3; ENTRIES=4096
LIMITS={'org.hhgttg.guide-release':100_000_000,'org.hhgttg.runtime-pack':1024**3}
class Rejected(Exception):pass
def need(v,c):
 if not v: raise Rejected(c)
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def identity(m):
 b=dict(m);b.pop('bundleId',None);return 'sha256:'+sha(b'Guide signed bundle identity v1\0'+canon(b))
def key_id(pub):return 'sha256:'+sha(pub)
def path_ok(p):
 q=PurePosixPath(p);return p.startswith('payload/') and '\\' not in p and not q.is_absolute() and all(x not in ('','.','..') for x in q.parts)
def validate_profile(p):
 i=p['id'];v=p['version'];m=p['manifest'];need(v==1,'PROFILE_UNSUPPORTED')
 if i=='org.hhgttg.guide-release':
  need(m['strategy']=='immutable-release-switch-v1' and m['rollback']=='previous-release' and 15<=m['trialSeconds']<=300,'PROFILE_INVALID')
 elif i=='org.hhgttg.runtime-pack':need(m['representation'] in ('directory','squashfs-v1') and m['provides'],'PROFILE_INVALID')
 else:raise Rejected('PROFILE_UNKNOWN')
def build(profile,payloads,seed,target=None,free=1048576):
 pub=Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
 files=[{'path':p,'size':len(b),'sha256':sha(b)} for p,b in sorted(payloads.items())];need(all(path_ok(x['path']) for x in files),'PATH_INVALID')
 m={'format':FORMAT,'bundleId':'','profile':profile,'target':target or {'product':'GuideOS','architectures':['arm64'],'boardProfiles':['rg35xx-h']},'requirements':{'archiveBytes':0,'payloadBytes':sum(x['size'] for x in files),'requiredFreeBytes':free},'files':files,'signing':{'algorithm':'Ed25519','keyId':key_id(pub)},'extensions':{}}
 for _ in range(8):
  m['bundleId']=identity(m);mb=canon(m);sig=Ed25519PrivateKey.from_private_bytes(seed).sign(b'Guide signed bundle signature v1\0'+mb);o=io.BytesIO()
  with zipfile.ZipFile(o,'w',zipfile.ZIP_STORED,allowZip64=False) as z:
   for n,b in [('manifest.json',mb),('manifest.ed25519',sig),*payloads.items()]:
    x=zipfile.ZipInfo(n,(2020,1,1,0,0,0));x.external_attr=0o100644<<16;z.writestr(x,b)
  raw=o.getvalue()
  if m['requirements']['archiveBytes']==len(raw):return raw,m,pub
  m['requirements']['archiveBytes']=len(raw)
 raise RuntimeError('size convergence')
def verify(raw,pub):
 need(len(raw)<=ABS,'LIMIT_EXCEEDED')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist();need(3<=len(infos)<=ENTRIES,'ARCHIVE_INVALID');need([x.filename for x in infos[:2]]==['manifest.json','manifest.ed25519'],'ARCHIVE_INVALID');need(all(x.compress_type==0 and not x.extra for x in infos),'ARCHIVE_INVALID')
  mb=z.read('manifest.json');m=json.loads(mb);need(canon(m)==mb,'MANIFEST_NOT_CANONICAL');need(m['format']==FORMAT and identity(m)==m['bundleId'],'ID_MISMATCH');need(m['signing']['keyId']==key_id(pub),'SIGNER_UNKNOWN');Ed25519PublicKey.from_public_bytes(pub).verify(z.read('manifest.ed25519'),b'Guide signed bundle signature v1\0'+mb);validate_profile(m['profile']);need(len(raw)<=LIMITS[m['profile']['id']],'LIMIT_EXCEEDED');need(m['requirements']['archiveBytes']==len(raw),'ARCHIVE_INVALID')
  names=[x.filename for x in infos[2:]];need(names==[x['path'] for x in m['files']] and len(names)==len(set(n.lower() for n in names)),'INVENTORY_INVALID')
  for f in m['files']:b=z.read(f['path']);need(path_ok(f['path']) and len(b)==f['size'] and sha(b)==f['sha256'],'PAYLOAD_MISMATCH')
 return m
