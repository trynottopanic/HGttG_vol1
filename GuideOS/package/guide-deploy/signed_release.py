"""Streaming verifier for the approved signed Guide-release profile."""
import hashlib,json,os,re,stat,struct,unicodedata,zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from deploy_core import require,Rejected,LIMIT,CHUNK,valid_path,REQUIRED

PROFILE='org.hhgttg.guide-release'
ROOT={'format','bundleId','profile','target','requirements','files','signing','extensions'}
MAX_INT=9007199254740991

def canonical(value):
    def clean(v):
        if isinstance(v,dict):return {k:clean(v[k]) for k in sorted(v,key=lambda x:x.encode('utf-16-be'))}
        if isinstance(v,list):return [clean(x) for x in v]
        if type(v)is int:require(0<=v<=MAX_INT,'invalid-number')
        elif isinstance(v,str):v.encode('utf-8')
        else:require(v is None or type(v)is bool,'invalid-json-type')
        return v
    return json.dumps(clean(value),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')

def parse(raw):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'duplicate-key');result[k]=v
        return result
    def invalid(_):raise Rejected('invalid-number')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=invalid,parse_constant=invalid)
    require(canonical(value)==raw,'noncanonical-manifest')
    return value

def identity(m):
    value=dict(m);value.pop('bundleId',None)
    return 'sha256:'+hashlib.sha256(b'Guide signed bundle identity v1\0'+canonical(value)).hexdigest()

def profile(m,config,sequence):
    from release_version import valid_label
    require(set(m)==ROOT and isinstance(m['extensions'],dict) and m['format']=='GUIDE-SIGNED-BUNDLE-1' and m['bundleId']==identity(m),'invalid-manifest')
    p=m['profile'];require(set(p)=={'id','version','manifest'} and p['id']==PROFILE and type(p['version'])is int and p['version']==1,'unsupported-profile')
    p=p['manifest']
    require(set(p)=={'version','releaseSequence','baseReleaseSequences','power','strategy','serviceProfile','healthProfile','trialSeconds','rollback','state'},'invalid-release-profile')
    require(valid_label(p['version']),'invalid-version')
    require(type(p['releaseSequence'])is int and 1<=p['releaseSequence']<=MAX_INT,'invalid-sequence')
    require(isinstance(p['baseReleaseSequences'],list) and 1<=len(p['baseReleaseSequences'])<=64 and all(type(x)is int for x in p['baseReleaseSequences']) and sequence in p['baseReleaseSequences'],'incompatible-base')
    require(p['power'] in ('external','battery-allowed') and p['strategy']=='immutable-release-switch-v1' and p['serviceProfile']=='guide-shell-v1' and p['healthProfile']=='guide-shell-v1' and p['rollback']=='previous-release' and type(p['trialSeconds'])is int and 15<=p['trialSeconds']<=300,'unsupported-activation')
    state=p['state'];require(set(state)=={'resultSchema','acceptedInputSchemas','migration'} and state['migration']=='none' and type(state['resultSchema'])is int and isinstance(state['acceptedInputSchemas'],list) and all(type(x)is int for x in state['acceptedInputSchemas']) and state['resultSchema']==config['state_schema'] and config['state_schema'] in state['acceptedInputSchemas'],'state-incompatible')
    target=m['target'];require(set(target)=={'product','architectures','boardProfiles'} and target['product']=='GuideOS' and target['architectures']==['arm64'] and isinstance(target['boardProfiles'],list) and all(isinstance(x,str) for x in target['boardProfiles']) and config['board'] in target['boardProfiles'],'wrong-target')
    need=m['requirements'];require(set(need)=={'archiveBytes','payloadBytes','requiredFreeBytes'} and all(type(n)is int and 0<=n<=MAX_INT for n in need.values()) and need['archiveBytes']<=LIMIT and need['payloadBytes']<=LIMIT,'size-limit')
    require(set(m['signing'])=={'algorithm','keyId'} and m['signing']['algorithm']=='Ed25519','unsupported-signature')
    return p

def bounded_archive(path):
    with open(path,'rb') as stream:
        stream.seek(0,2);size=stream.tell()
        require(22<=size<=LIMIT,'size-limit');stream.seek(-22,2)
        e=struct.unpack('<IHHHHIIH',stream.read(22))
        require(e[0]==0x06054b50 and e[1]==e[2]==e[7]==0 and e[3]==e[4] and 3<=e[4]<=514 and e[5]<=262144 and e[5]+e[6]+22==size,'archive-end')
    return zipfile.ZipFile(path)

def verify(path,trust,config,sequence):
    require(Path(path).stat().st_size<=LIMIT,'size-limit')
    with open(path,'rb') as stream,bounded_archive(path) as archive:
        infos=archive.infolist();require(3<=len(infos)<=514 and not archive.comment,'archive-structure')
        require([x.filename for x in infos[:2]]==['manifest.json','manifest.ed25519'],'archive-order')
        require(infos[0].file_size<=262144 and infos[1].file_size==64,'metadata-limit')
        offset=0
        for info in infos:
            mode=info.external_attr>>16
            require(info.header_offset==offset and info.compress_type==0 and info.file_size==info.compress_size and not info.extra and not info.comment and not info.flag_bits&~0x800 and stat.S_IFMT(mode) in (0,stat.S_IFREG) and not info.is_dir(),'archive-structure')
            name=info.filename
            require(unicodedata.normalize('NFC',name)==name and not any(ord(c)<32 for c in name),'invalid-path')
            stream.seek(offset);header=stream.read(30)
            require(len(header)==30,'archive-structure')
            h=struct.unpack('<IHHHHHIIIHH',header)
            require(h[0]==0x04034b50 and h[2]==info.flag_bits and h[3]==0 and h[6]==info.CRC and h[7]==info.compress_size and h[8]==info.file_size and h[10]==0,'local-header-mismatch')
            encoded=stream.read(h[9]);require(encoded.decode('utf-8' if h[2]&0x800 else 'ascii')==name,'filename-mismatch')
            offset+=30+h[9]+info.file_size
        require(offset==archive.start_dir,'archive-trailing-content')
        # Bound the exact central directory and EOCD; no ZIP64 or trailing bytes.
        central=sum(46+len(i.filename.encode('utf-8')) for i in infos)
        stream.seek(offset+central);end=stream.read()
        require(len(end)==22,'archive-end')
        e=struct.unpack('<IHHHHIIH',end)
        require(e==(0x06054b50,0,0,len(infos),len(infos),central,offset,0),'archive-end')
        raw=archive.read('manifest.json');m=parse(raw);p=profile(m,config,sequence)
        require(m['requirements']['archiveBytes']==os.fstat(stream.fileno()).st_size,'archive-size')
        key=m['signing']['keyId'];require(re.fullmatch('sha256:[a-f0-9]{64}',key),'invalid-key')
        trust=Path(trust);require(not (trust/'revoked'/key[7:]).exists() and not (trust/'revoked'/(key[7:]+'.json')).exists(),'revoked-key')
        record=json.loads((trust/(key[7:]+'.json')).read_text())
        pub=bytes.fromhex(record['publicKey'])
        require('sha256:'+hashlib.sha256(pub).hexdigest()==key and record['profiles']==[PROFILE] and record['product']=='GuideOS' and record['architectures']==['arm64'] and config['board'] in record['boards'],'signer-scope')
        Ed25519PublicKey.from_public_bytes(pub).verify(archive.read('manifest.ed25519'),b'Guide signed bundle signature v1\0'+raw)
        records=m['files'];require(isinstance(records,list) and len(records)==len(infos)-2,'inventory')
        names=[r['path'] for r in records]
        require(names==sorted(names,key=lambda x:x.encode('utf-8')) and len({n.casefold() for n in names})==len(names) and names==[i.filename for i in infos[2:]],'inventory')
        total=0;files={}
        for r in records:
            require(set(r)=={'path','size','sha256'} and r['path'].startswith('payload/'),'inventory')
            name=r['path'][8:];valid_path(name)
            require(type(r['size'])is int and 0<=r['size']<=LIMIT and re.fullmatch('[a-f0-9]{64}',r['sha256']),'inventory')
            require(archive.getinfo(r['path']).file_size==r['size'],'payload-size')
            digest=hashlib.sha256();count=0
            with archive.open(r['path']) as f:
                while block:=f.read(CHUNK):digest.update(block);count+=len(block)
            require(count==r['size'] and digest.hexdigest()==r['sha256'],'payload-corrupt')
            total+=count;files[name]={'bytes':count,'sha256':r['sha256']}
        require(total==m['requirements']['payloadBytes'] and REQUIRED<=files.keys(),'incomplete-release')
        return m,files
