"""Cartridge catalog owned by the existing read-only storage provider."""
import hashlib, os, re, secrets, socket, stat
from pathlib import Path
from guide_cartridge import require, text, IDENT, VERSION
from guide_install_wire import serve

def regular(parent,name,limit):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
    try:
        st=os.fstat(fd);require(stat.S_ISREG(st.st_mode) and st.st_size<=limit,'regular bounded file')
        return fd,st
    except BaseException:os.close(fd);raise

def parse_index(raw):
    require(len(raw)<=4096,'index bound');lines=raw.decode('ascii').splitlines()
    require(lines and lines.pop(0)=='GUIDE-CARTRIDGE-INDEX-1','index format');record={};caps=[]
    for line in lines:
        key,sep,value=line.partition('=');require(sep and len(value)<=200,'index field')
        if key=='CAPABILITY':caps.append(value);continue
        require(key in ('ID','NAME','VERSION','KIND','SUMMARY','FILE','BYTES','SHA256','ACTION') and key not in record,'index fields');record[key]=value
    require(set(record)=={'ID','NAME','VERSION','KIND','SUMMARY','FILE','BYTES','SHA256','ACTION'},'index fields')
    require(re.fullmatch(IDENT,record['ID']) and re.fullmatch(VERSION,record['VERSION']) and text(record['NAME'],64) and text(record['SUMMARY'],200),'index display')
    require(re.fullmatch(r'[A-Za-z0-9_.-]{1,112}\.guide',record['FILE']) and re.fullmatch(r'[a-f0-9]{64}',record['SHA256']) and re.fullmatch(r'[1-9][0-9]{0,11}',record['BYTES']),'index archive')
    require(len(caps)<=16 and len(set(caps))==len(caps),'index capability bound');record['CAPABILITIES']=caps;return record

def fingerprint(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)

class Catalog:
    def __init__(self,mount,current):
        self.mount=Path(mount);self.current=current;self.epoch=secrets.token_hex(16);self.generation=0;self.card=None;self.items={};self.listener=None
    def invalidate(self,card=None):
        self.generation+=1;self.card=card;self.items={}
    def connect(self,path):
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        try:os.unlink(path)
        except FileNotFoundError:pass
        self.listener.bind(str(path));os.chmod(path,0o600);self.listener.listen(2)
    def directory(self):
        require(self.card is not None and self.current()==self.card,'card changed')
        fd=os.open(self.mount,os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            for expected in ('GUIDE','CARTRIDGES'):
                matches=[]
                with os.scandir(fd) as entries:
                    for number,e in enumerate(entries):
                        require(number<512,'directory entry bound')
                        if e.name.upper()==expected:matches.append(e.name)
                require(len(matches)==1,'ambiguous cartridge directory')
                child=os.open(matches[0],os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);os.close(fd);fd=child
            return fd
        except BaseException:os.close(fd);raise
    def listing(self,offset=0):
        require(type(offset)is int and 0<=offset<=128 and offset%16==0,"catalog page")
        if offset:return self.page(offset)
        self.items={};fd=self.directory();used=0;truncated=False;errors=0;seen=set()
        try:
            with os.scandir(fd) as entries:
                for number,e in enumerate(entries):
                    if number>=512 or len(self.items)>=128:truncated=True;break
                    if not e.name.lower().endswith('.gde'):continue
                    try:
                        key=e.name.casefold();require(key not in seen,'index collision');seen.add(key)
                        f,st=regular(fd,e.name,4096)
                        try:raw=os.read(f,4097)
                        finally:os.close(f)
                        used+=len(raw);require(used<=131072,'catalog cache bound')
                        record=parse_index(raw);token=secrets.token_hex(16)
                        self.items[token]=(e.name,fingerprint(st),record)
                    except (OSError,ValueError,UnicodeError):errors+=1
            require(self.current()==self.card,'card changed')
            self.truncated=truncated;self.errors=errors
            return self.page(0)
        finally:os.close(fd)
    def page(self,offset):
        require(self.card is not None and self.current()==self.card,'card changed')
        items=list(self.items.items())
        return {'epoch':self.epoch,'generation':self.generation,'items':[dict(token=t,id=r['ID'],name=r['NAME'],version=r['VERSION'],summary=r['SUMMARY'],action=r['ACTION'],unsigned=True) for t,(_,_,r) in items[offset:offset+16]],'next':offset+16 if len(items)>offset+16 else None,'truncated':self.truncated,'invalid':self.errors}
    def open(self,args):
        require(set(args)=={'epoch','generation','token'} and args['epoch']==self.epoch and args['generation']==self.generation and args['token'] in self.items,'stale selection')
        name,expected,record=self.items[args['token']];directory=self.directory();archive=-1
        try:
            fd,st=regular(directory,name,4096)
            try:require(fingerprint(st)==expected and parse_index(os.read(fd,4097))==record,'index changed')
            finally:os.close(fd)
            archive,st=regular(directory,record['FILE'],1048576);require(st.st_size==int(record['BYTES']),'archive size')
            try:
                sidecar,_=regular(directory,record['FILE']+'.sha256',256)
            except FileNotFoundError:pass
            else:
                try:receipt=os.read(sidecar,257).decode('ascii').split()
                finally:os.close(sidecar)
                require(len(receipt)==2 and receipt==[record['SHA256'],record['FILE']],'sidecar mismatch')
            require(self.current()==self.card,'card changed')
            result={'selection':args,'index':record};return result,[archive]
        except BaseException:
            if archive>=0:os.close(archive)
            raise
        finally:os.close(directory)
    def dispatch(self,op,args):
        if op==1:require(set(args)=={'offset'},'list arguments');return self.listing(args['offset']),[]
        if op==2:return self.open(args)
        raise ValueError('catalog operation')
    def poll(self):
        peer,_=self.listener.accept()
        with peer:
            try:serve(peer,self.dispatch)
            except (OSError,ValueError,EOFError):pass
    def close(self):
        if self.listener:self.listener.close()
