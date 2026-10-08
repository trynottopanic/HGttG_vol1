"""Materialize the same malformed cartridges for Windows and Deck verification."""
from pathlib import Path
import copy,hashlib,io,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'package/guide-installer'))
from guide_cartridge import verify,canonical,digest
out=ROOT/'build/cartridge-installer-0/corpus';out.mkdir(parents=True,exist_ok=True)
source=ROOT/'build/cartridge-installer-0/cartridges/org.hhgtg.cartridge-proof-1.0.0.guide'
with zipfile.ZipFile(source) as z:original=[(copy.copy(e),z.read(e)) for e in z.infolist()]
def make(name,change=None,raw_change=None):
    entries=copy.deepcopy(original)
    if change:entries=change(entries)
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        for e,b in entries:z.writestr(e,b)
    raw=data.getvalue()
    if raw_change:raw=raw_change(raw)
    path=out/(name+'.guide');path.write_bytes(raw)
    try:verify(io.BytesIO(raw));accepted=True
    except Exception:accepted=False
    assert accepted==(name=='valid'),name
    return dict(file=path.name,accepted=accepted,sha256=digest(raw))
def rename(entries,name):entries[0][0].filename=name;return entries
def alter_content(entries,suffix,data):
    changed=[]
    for e,b in entries:
        if e.filename.endswith(suffix):b=data
        changed.append((e,b))
    inventory=[dict(path=e.filename,bytes=len(b),sha256=digest(b)) for e,b in changed if e.filename.startswith('CONTENT/')]
    result=[]
    for e,b in changed:
        if e.filename=='GUIDE/manifest.json':m=json.loads(b);m['files']=inventory;b=canonical(m)
        result.append((e,b))
    return result
cases=[make('valid'),make('duplicate',lambda e:e+[e[0]]),make('missing',lambda e:e[1:]),make('unlisted',lambda e:e+[(zipfile.ZipInfo('CONTENT/unlisted.txt'),b'no')])]
for name,path in [('traversal','CONTENT/../escape.py'),('absolute','/escape.py'),('backslash','CONTENT\\escape.py'),('ads','CONTENT/a:ads.py'),('reserved','CONTENT/NUL'),('non-nfc','CONTENT/e\u0301.txt')]:cases.append(make(name,lambda e,path=path:rename(e,path)))
for name,mode in [('link',0o120777),('special',0o020666)]:
    def mutate(entries,mode=mode):entries[0][0].external_attr=mode<<16;return entries
    cases.append(make(name,mutate))
def extra(entries):entries[0][0].extra=b'\x01\x00\x00\x00';return entries
cases.append(make('zip64',extra))
cases.append(make('trailing',raw_change=lambda b:b+b'extra'))
cases.append(make('truncated',raw_change=lambda b:b[:-1]))
cases.append(make('oversize',raw_change=lambda b:b+b'0'*1048576))
def duplicate_json(entries):return [(e,b'{"format":"duplicate",'+b[1:] if e.filename=='GUIDE/manifest.json' else b) for e,b in entries]
cases.append(make('duplicate-json',duplicate_json))
cases.append(make('bad-python',lambda e:alter_content(e,'reference.py',b'def application(:\n')))
cases.append(make('bad-icon',lambda e:alter_content(e,'icon.png',b'not a PNG')))
(out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');print('CORPUS_READY',len(cases))
