"""Shared bounded application cartridge verifier. Never imports cartridge code."""
import ast, hashlib, io, json, os, re, stat, struct, unicodedata, zipfile, zlib
from pathlib import Path
ARCHIVE_MAX=1048576
EXPANDED_MAX=2097152
METADATA_MAX=32768
CAPABILITIES={'storage.private':2,'output.visual.surface':3,'input.actions':4,'input.text':5,
              'media.library.browse':6,'media.source.open':7,'media.session.control':8}
IDENT=r'[a-z][a-z0-9_.-]{0,62}'
VERSION=r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
def require(ok,reason):
    if not ok:raise ValueError(reason)
def canonical(v):return json.dumps(v,ensure_ascii=True,separators=(',',':'),sort_keys=True).encode('ascii')
def digest(v):return hashlib.sha256(v).hexdigest()
def pairs(items):
    result={}
    for k,v in items:
        require(k not in result,'duplicate JSON key');result[k]=v
    return result
def json_read(raw):
    require(len(raw)<=METADATA_MAX,'metadata bound')
    v=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:require(False,'nonfinite JSON'))
    require(type(v)is dict,'metadata object');return v
def text(v,n):return type(v)is str and 0<len(v)<=n and all(ord(c)>=32 and ord(c)!=127 for c in v)
def path_check(name):
    require(type(name)is str and 0<len(name.encode('utf-8'))<=128,'path length')
    require(name==unicodedata.normalize('NFC',name),'path normalization')
    parts=name.split('/')
    require(len(parts)<=8 and all(p and p not in ('.','..') and not p.endswith(('.', ' ')) for p in parts),'path components')
    require(not any(c in name for c in '\\:*?"<>|') and all(ord(c)>=32 and ord(c)!=127 for c in name),'path characters')
    require(all(not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p,re.I) for p in parts),'reserved path')
def png_check(raw):
    require(len(raw)<=32768 and raw[:8]==b'\x89PNG\r\n\x1a\n','icon PNG')
    offset=8;first=True;ended=False;compressed=bytearray();channels=0
    while offset<len(raw):
        require(offset+12<=len(raw),'PNG chunk')
        size,kind=struct.unpack('>I4s',raw[offset:offset+8]);offset+=8
        require(size<=32768 and offset+size+4<=len(raw),'PNG bound')
        data=raw[offset:offset+size];offset+=size
        require(zlib.crc32(kind+data)&0xffffffff==struct.unpack('>I',raw[offset:offset+4])[0],'PNG CRC');offset+=4
        require(not ended,'PNG trailing bytes')
        if first:
            require(kind==b'IHDR' and size==13,'PNG header')
            w,h,depth,color,comp,filt,interlace=struct.unpack('>IIBBBBB',data)
            require((w,h,depth,comp,filt,interlace)==(64,64,8,0,0,0) and color in (2,6),'icon dimensions/encoding')
            channels=3 if color==2 else 4;first=False
        elif kind==b'IDAT':compressed.extend(data)
        elif kind==b'IEND':require(size==0,'PNG end');ended=True
        else:require(kind[0]&32 and kind not in (b'acTL',b'fcTL',b'fdAT'),'unsupported PNG chunk')
    require(ended and compressed,'PNG incomplete')
    dec=zlib.decompressobj();stride=64*channels;expected=(stride+1)*64
    pixels=dec.decompress(bytes(compressed),expected+1)
    require(len(pixels)==expected and dec.eof and not dec.unused_data and not dec.unconsumed_tail,'PNG expanded bound')
    previous=bytearray(stride)
    for row in range(64):
        start=row*(stride+1);kind=pixels[start];require(kind<=4,'PNG predictor')
        current=bytearray(pixels[start+1:start+1+stride])
        for x in range(stride):
            a=current[x-channels] if x>=channels else 0;b=previous[x];c=previous[x-channels] if x>=channels else 0
            p=a+b-c;distances=(abs(p-a),abs(p-b),abs(p-c))
            predictor=(0,a,b,(a+b)//2,(a,b,c)[distances.index(min(distances))])[kind]
            current[x]=(current[x]+predictor)&255
        previous=current

def metadata_check(m,app,content):
    require(set(m)=={'format','id','name','version','kind','summary','capabilities','installAction','entrypoint','files'},'manifest fields')
    require(m['format']=='GUIDE-CARTRIDGE-1' and m['kind']=='application' and m['installAction']=='application.install.v0','application profile')
    require(type(m['id'])is str and re.fullmatch(IDENT,m['id']),'application ID')
    require(type(m['version'])is str and len(m['version'])<=48 and re.fullmatch(VERSION,m['version']),'semantic version')
    require(all(not(s.isdigit() and len(s)>1 and s.startswith('0')) for s in m['version'].partition('-')[2].split('.')),'semantic prerelease')
    require(text(m['name'],64) and text(m['summary'],200),'display metadata')
    ep=m['entrypoint'];require(type(ep)is dict and set(ep)=={'runtime','interfaceMajor','module','callable'},'entrypoint fields')
    require(ep['runtime']=='guide.python-application' and type(ep['interfaceMajor'])is int and ep['interfaceMajor']==1,'runtime interface')
    for key in ('module','callable'):require(type(ep[key])is str and re.fullmatch(r'[a-z_][a-z0-9_]{0,62}',ep[key]),'entrypoint identifier')
    caps=m['capabilities'];require(type(caps)is list and 1<=len(caps)<=8 and all(type(c)is str and c in CAPABILITIES for c in caps) and len(caps)==len(set(caps)),'capabilities')
    require('storage.private' in caps,'checkpoint requires private storage')
    fields={'profile','icon','runtime','interfaceMajor','display','privateBytes','temporaryBytes','memoryMinimumBytes','memoryPeakBytes','dataSchema','lifecycle','offline','health','optionalCapabilities'}
    require(set(app)==fields and app['profile']=='guide.application.v0','application metadata profile')
    require(app['runtime']==ep['runtime'] and type(app['interfaceMajor'])is int and app['interfaceMajor']==1,'runtime mismatch')
    require(app['icon']=='assets/icon.png' and app['display']==[640,480],'display compatibility')
    for name,limit in [('privateBytes',524288),('temporaryBytes',131072),('memoryMinimumBytes',50331648),('memoryPeakBytes',67108864)]:
        require(type(app[name])is int and 0<app[name]<=limit,'footprint bound')
    require((app['memoryMinimumBytes'],app['memoryPeakBytes'],app['temporaryBytes'])==(50331648,67108864,131072),'v0 fixed runtime footprint')
    require(type(app['dataSchema'])is int and 1<=app['dataSchema']<=65535,'data schema')
    require(app['lifecycle']==['ready','checkpoint','stop'] and app['offline']is True and app['health']=='isolated-ready-checkpoint-v0','lifecycle')
    optional=app['optionalCapabilities'];require(type(optional)is list and all(type(c)is str and c in caps and c!='storage.private' for c in optional) and len(optional)==len(set(optional)),'optional capabilities')
    source='CONTENT/application/'+ep['module']+'.py';require(source in content,'entrypoint source')
    require(all(not n.endswith('.py') or n==source for n in content),'single module runtime')
    require(all(n.endswith(('.py','.json','.png','.txt')) for n in content),'unsupported payload')
    tree=ast.parse(content[source].decode('utf-8'),filename='<cartridge>')
    require(any(isinstance(n,ast.FunctionDef) and n.name==ep['callable'] for n in tree.body),'entrypoint function')
    for name,data in content.items():
        if name.endswith('.json'):json_read(data)
    png_check(content['CONTENT/assets/icon.png']);return source

def verify(stream,expected=None,extract=None):
    stream.seek(0);raw=stream.read(ARCHIVE_MAX+1);require(0<len(raw)<=ARCHIVE_MAX,'archive bound')
    sha=digest(raw);require(expected is None or sha==expected,'archive hash changed')
    require(len(raw)>=22 and raw[-22:-18]==b'PK\x05\x06','ZIP end record')
    disk,cdisk,count,allcount,csize,coffset,comment=struct.unpack('<4H2IH',raw[-18:])
    require(disk==cdisk==comment==0 and count==allcount and count<=65 and coffset+csize==len(raw)-22,'ZIP layout')
    require(raw[:4]==b'PK\x03\x04','ZIP preamble')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist();require(len(infos)==count,'ZIP count')
        names=set();content={};expanded=0;next_header=0
        for e in infos:
            name=e.filename;path_check(name)
            require(name==e.orig_filename and name.casefold() not in names,'duplicate archive path');names.add(name.casefold())
            require(name=='GUIDE/manifest.json' or name.startswith('CONTENT/'),'archive root')
            require(e.header_offset==next_header and e.extract_version<=20 and e.compress_type in (0,8) and not e.flag_bits&~0x800 and not e.extra and not e.comment,'unsupported ZIP feature')
            require(stat.S_IFMT(e.external_attr>>16) in (0,stat.S_IFREG) and not e.is_dir(),'nonregular entry')
            require(e.file_size<=EXPANDED_MAX and e.compress_size<=ARCHIVE_MAX,'entry bound')
            off=e.header_offset;require(off+30<=len(raw),'local ZIP header')
            local=struct.unpack('<4s5H3I2H',raw[off:off+30]);name_len,extra_len=local[-2:]
            require(local[0]==b'PK\x03\x04' and extra_len==0 and local[2]==e.flag_bits and local[3]==e.compress_type and local[6]==e.CRC and local[7]==e.compress_size and local[8]==e.file_size,'local central mismatch')
            next_header=off+30+name_len+extra_len+e.compress_size;require(next_header<=coffset,'ZIP overlap')
            with archive.open(e) as f:
                chunks=[];size=0
                while True:
                    chunk=f.read(min(65536,EXPANDED_MAX-expanded+1))
                    if not chunk:break
                    size+=len(chunk);expanded+=len(chunk);require(expanded<=EXPANDED_MAX,'expanded stream bound');chunks.append(chunk)
                require(size==e.file_size,'entry size')
            content[name]=b''.join(chunks)
        require(next_header==coffset,'ZIP unexplained bytes')
    require('GUIDE/manifest.json' in content,'manifest missing')
    m=json_read(content.pop('GUIDE/manifest.json'));inventory=m.get('files')
    require(type(inventory)is list and len(inventory)<=64,'inventory bound');declared=set()
    for item in inventory:
        require(type(item)is dict and set(item)=={'path','bytes','sha256'},'inventory fields')
        name=item['path'];require(type(name)is str and name in content and name not in declared,'inventory path');declared.add(name)
        require(type(item['bytes'])is int and item['bytes']==len(content[name]) and item['sha256']==digest(content[name]),'inventory integrity')
    require(declared==set(content),'undeclared payload')
    require('CONTENT/application/application.json' in content and 'CONTENT/assets/icon.png' in content,'application metadata missing')
    app=json_read(content['CONTENT/application/application.json']);source=metadata_check(m,app,content)
    if extract is not None:
        root=Path(extract);require(root.is_dir() and not root.is_symlink() and not any(root.iterdir()),'extract destination')
        for name,data in content.items():
            target=root/name.removeprefix('CONTENT/');target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return dict(manifest=m,application=app,sha256=sha,inventoryHash=digest(canonical(sorted(inventory,key=lambda f:f['path']))),sourceHash=digest(content[source]),archiveBytes=len(raw),expandedBytes=expanded,unsigned=True)

def build(source,manifest,output):
    source=Path(source);content={}
    for path in sorted(source.rglob('*')):
        require(not path.is_symlink(),'source symlink')
        if path.is_dir():continue
        name='CONTENT/'+path.relative_to(source).as_posix();path_check(name)
        require(path.stat().st_size<=EXPANDED_MAX,'source size');content[name]=path.read_bytes()
        require(len(content)<=64 and sum(map(len,content.values()))<=EXPANDED_MAX,'source bounds')
    m=dict(manifest);m['files']=[dict(path=n,bytes=len(d),sha256=digest(d)) for n,d in sorted(content.items())]
    content['GUIDE/manifest.json']=canonical(m);result=io.BytesIO()
    with zipfile.ZipFile(result,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=False,compresslevel=9) as archive:
        for name,data in sorted(content.items()):
            entry=zipfile.ZipInfo(name,(2000,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.create_system=3;entry.external_attr=(stat.S_IFREG|0o444)<<16
            archive.writestr(entry,data)
    result.seek(0);checked=verify(result);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(result.getvalue())
    output.with_suffix(output.suffix+'.sha256').write_text(checked['sha256']+'  '+output.name+'\n',encoding='ascii');return checked
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('archive');a=p.parse_args()
    with open(a.archive,'rb') as f:print(json.dumps(verify(f),ensure_ascii=True))
