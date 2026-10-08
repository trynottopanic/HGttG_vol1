#!/usr/bin/python3 -I
"""Socket-activated owner installer; blocking work stays off the UI request loop."""
import os, select, signal, socket, sys, tempfile, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),'/usr/lib/guideos/ipc','/usr/lib/guideos/application-host']
from guide_cartridge import *
from guide_installer import Installer, helper
from guide_install_wire import CATALOG, call, serve

class Service:
    def __init__(self,installer):
        self.installer=installer;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-install');self.future=None;self.preview=None;self.error=None;self.inspect_id=None
    def busy(self):return self.future is not None and not self.future.done()
    def inspect(self,selection):
        result,fds=call(CATALOG,2,selection);require(len(fds)==1,'source descriptor')
        try:
            with tempfile.TemporaryDirectory(prefix='inspect-',dir=self.installer.staging) as temp:
                path=Path(temp)/'archive.guide';total=0
                with path.open('xb') as target:
                    while True:
                        self.installer.cancelled();chunk=os.read(fds[0],65536)
                        if not chunk:break
                        total+=len(chunk);require(total<=ARCHIVE_MAX,'archive bound');target.write(chunk)
                package=helper(path,result['index']['SHA256'])
            index=package['manifest'];declared=result['index']
            require(all(index[k]==declared[n] for k,n in [('id','ID'),('name','NAME'),('version','VERSION'),('kind','KIND'),('summary','SUMMARY'),('installAction','ACTION')]) and set(index['capabilities'])==set(declared['CAPABILITIES']),'index/archive mismatch')
            self.installer.cancelled();old=self.installer.record(index['id']);optional=package['application']['optionalCapabilities']
            granted=[c for c in index['capabilities'] if c not in optional or not old or c in old['agreement']['granted']]
            preview={'token':uuid.uuid4().hex,'selection':selection,'package':package,'granted':granted,'old':old}
            self.preview=preview;self.error=None
        finally:
            for fd in fds:os.close(fd)
    def preview_view(self):
        p=self.preview
        if not p:return None
        package=p['package'];m=package['manifest'];a=package['application'];old=p['old']
        return {'token':p['token'],'id':m['id'],'name':m['name'],'version':m['version'],'summary':m['summary'],'sha256':package['sha256'],'unsigned':True,'capabilities':m['capabilities'],'optionalCapabilities':a['optionalCapabilities'],'granted':p['granted'],'archiveBytes':package['archiveBytes'],'expandedBytes':package['expandedBytes'],'privateBytes':a['privateBytes'],'memoryPeakBytes':a['memoryPeakBytes'],'previousState':old['state'] if old else None,'previousVersion':old['package']['manifest']['version'] if old else None,'previousGranted':old['agreement']['granted'] if old else [],'previousPrivateBytes':old['package']['application']['privateBytes'] if old else 0,'previousMemoryPeakBytes':old['package']['application']['memoryPeakBytes'] if old else 0}
    def run_install(self,args,p):
        result,fds=call(CATALOG,2,p['selection']);require(len(fds)==1 and result['index']['SHA256']==p['package']['sha256'],'source changed')
        def current():
            result,fresh=call(CATALOG,2,p['selection'])
            for fd in fresh:os.close(fd)
            return result['index']['SHA256']==p['package']['sha256']
        try:return self.installer.install(fds[0],p['package'],args['granted'],args['requestId'],args['downgrade'],current)
        finally:
            for fd in fds:os.close(fd)
    def dispatch(self,op,args):
        if self.future is not None and self.future.done():
            try:self.future.result()
            except Exception as error:
                print('GUIDE_INSTALLER_FAILURE',type(error).__name__,flush=True)
                if os.environ.get('GUIDE_INSTALLER_TEST_TRACE')=='1':
                    import traceback;traceback.print_exc()
                self.error='Operation failed; the previous installation and saved data are retained.'
            self.future=None
        if op==3:
            require(not args,'status arguments');return {'busy':self.busy(),'status':self.installer.status,'preview':self.preview_view(),'error':self.error},[]
        if op==4:
            require(not args,'cancel arguments');require(self.installer.status.get('phase') not in ('commit-intent','committed'),'commit already started');self.installer.cancel.set();return {'accepted':True},[]
        if op==5:
            require(set(args)=={'offset'} and type(args['offset'])is int and 0<=args['offset']<=128 and args['offset']%16==0,'catalog arguments');items=self.installer.catalog();offset=args['offset'];return {'items':items[offset:offset+16],'next':offset+16 if len(items)>offset+16 else None},[]
        if op==9:
            require(not args,'shutdown arguments');self.installer.cancel.set();return {'ready':not self.busy()},[]
        require(not self.busy(),'installer busy');self.error=None;self.installer.cancel.clear()
        if op==1:
            require(set(args)=={'epoch','generation','token'},'inspect fields');self.preview=None;self.installer.status={'phase':'verifying','revision':self.installer.status.get('revision',0)+1};self.future=self.pool.submit(self.inspect,args)
        elif op==2:
            require(set(args)=={'token','requestId','granted','downgrade'} and type(args['downgrade'])is bool and self.preview and args['token']==self.preview['token'],'agreement changed')
            self.future=self.pool.submit(self.run_install,args,self.preview);self.preview=None
        elif op in (6,7):
            require(set(args)=={'id','requestId','expectedGeneration'} and type(args['expectedGeneration'])is int,'remove fields');self.future=self.pool.submit(self.installer.uninstall,args['id'],args['requestId'],op==7,args['expectedGeneration'])
        elif op==8:
            require(set(args)=={'id','version','requestId','expectedGeneration'} and type(args['expectedGeneration'])is int,'rollback fields');self.future=self.pool.submit(self.installer.rollback,args['id'],args['version'],args['requestId'],args['expectedGeneration'])
        else:raise ValueError('installer operation')
        return {'accepted':True},[]
    def close(self):self.installer.cancel.set();self.pool.shutdown(wait=True,cancel_futures=True);self.installer.close()

def main():
    # The board build supplies a measured root-budget reserve; fail closed when
    # that release-specific value has not been staged.
    reserve=int(Path('/etc/guideos/installer-reserve-bytes').read_text())
    require(0<reserve<=2147483648,'board free-space reserve')
    installer=Installer(reserve_bytes=reserve);installer.recover();service=Service(installer)
    listener=socket.socket(fileno=3);stopped=[False];last=time.monotonic()
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    try:
        while not stopped[0]:
            if select.select([listener],[],[],.2)[0]:
                peer,_=listener.accept();last=time.monotonic()
                with peer:
                    try:serve(peer,service.dispatch)
                    except (OSError,ValueError,EOFError):pass
            if not service.busy() and service.preview is None and time.monotonic()-last>60:break
    finally:service.close()
if __name__=='__main__':main()
