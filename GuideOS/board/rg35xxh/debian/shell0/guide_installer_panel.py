"""Shell-owned cartridge agreement and installed application controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os,sys,time,uuid
for p in (Path('/usr/lib/guideos/installer'),Path('/usr/lib/guideos/ipc'),Path(__file__).resolve().parents[4]/'package/guide-installer',Path(__file__).resolve().parents[4]/'package/guide-ipc/python'):
    if p.is_dir():sys.path.insert(0,str(p))
from guide_install_wire import call,INSTALLER,CATALOG
LABELS={'storage.private':'Private drafts and settings','output.visual.surface':'Show an application screen','input.actions':'Receive controller actions','input.text':'Use the system keyboard','media.library.browse':'Browse media','media.source.open':'Open selected media','media.session.control':'Control media playback'}

class InstallerPanel:
    def __init__(self,state):
        self.state=state;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-cartridge-ui');self.pending=None;self.operation='';self.view='installed';self.cursor=0;self.items=[];self.rows=[];self.notice='';self.preview=None;self.selected=None;self.status={};self.next_poll=0;self.busy=False;self.page=0;self.next_page=None;self.confirmation=None;self.shutdown_waiting=False;self.shutdown_ready=False;self.shutdown_deadline=0;self.installed_cache=[];self.installed_cache_next=None;self.installed_cache_valid=False
    @staticmethod
    def rpc(path,op,args):
        result,fds=call(path,op,args)
        for fd in fds:os.close(fd)
        if fds:raise ValueError('unexpected descriptor')
        return result
    def submit(self,operation,path,op,args=None):
        if self.pending:return False
        self.operation=operation;self.pending=self.pool.submit(self.rpc,path,op,args or {});return True
    def open(self,view):
        self.view=view;self.cursor=0;self.state.page='installer';self.page=0
        if view=='installed' and self.installed_cache_valid:
            self.items=list(self.installed_cache);self.next_page=self.installed_cache_next;self.notice=''
        else:
            self.notice='Reading…';self.refresh()
    def refresh(self):
        if self.view=='cartridges':return self.submit('list',CATALOG,1,{'offset':self.page})
        return self.submit('installed',INSTALLER,5,{'offset':self.page})
    def poll(self):
        changed=False
        if self.pending and self.pending.done():
            try:
                result=self.pending.result()
                if self.operation in ('list','installed'):
                    self.items=result['items'];self.next_page=result.get('next');self.notice=('Unsigned cartridges. Select one to verify.' if self.operation=='list' else 'Installed programs and retained data.') if self.items else ('No cartridges found.' if self.operation=='list' else 'No applications installed.')
                    if self.operation=='list':self.epoch=result['epoch'];self.generation=result['generation']
                    else:
                        self.installed_cache=list(self.items);self.installed_cache_next=self.next_page;self.installed_cache_valid=True
                elif self.operation=='status':
                    self.status=result['status'];self.busy=result['busy'];self.notice=result.get('error') or self.status.get('phase','idle').replace('-',' ').capitalize()
                    if result.get('preview') and self.view=='verifying':self.preview=result['preview'];self.view='agreement';self.cursor=0;self.notice='Unsigned. Integrity checked; authorship is not verified.'
                    if not self.busy and self.view=='progress' and self.status.get('phase') in ('committed','already-installed'):
                        self.view='complete'
                        action=self.status.get('operation')
                        self.notice='Program removed. Private drafts and settings are retained.' if action=='uninstall' else 'Retained private drafts and settings deleted.' if action=='delete-data' else 'Installed internally. The cartridge can be removed.'
                elif self.operation=='shutdown':self.shutdown_ready=result['ready']
                elif self.operation=='inspect':self.view='verifying';self.busy=True
                elif self.operation in ('install','remove','rollback'):
                    self.view='progress';self.busy=True;self.notice='Preparing…';self.installed_cache_valid=False
            except (OSError,ValueError,KeyError,TypeError,EOFError):
                self.notice='Unavailable or changed. Refresh and try again.';self.busy=False
                if self.view=='verifying':self.view='cartridges'
            self.pending=None;changed=True
        if not self.pending and self.state.page=='installer' and not self.shutdown_waiting and self.view in ('verifying','progress') and time.monotonic()>=self.next_poll:
            self.next_poll=time.monotonic()+.25;self.submit('status',INSTALLER,3)
        return changed
    def make_rows(self):
        if self.shutdown_waiting:return [('Cancel shutdown','cancel-shutdown',None)]
        rows=[]
        if self.view in ('cartridges','installed'):
            for item in self.items:rows.append((('Not installed · ' if item.get('state')=='uninstalled' else '')+item['name']+'  ·  '+item['version'],'select',item))
            if self.next_page is not None:rows.append(('Next page','next',self.next_page))
            if self.page:rows.append(('First page','next',0))
            if self.view=='cartridges':rows.append(('Refresh','refresh',None))
            rows.append(('Installation status','status',None))
        elif self.view=='agreement':
            p=self.preview
            rows=[(p['name']+'  ·  '+p['version'],'info',p['summary']),('Permissions','permissions',None),('Storage and memory','footprint',None),('Integrity details','integrity',None),('Agree and '+('reinstall' if p.get('previousState')=='uninstalled' else 'update' if p['previousVersion'] else 'install'),'agree',None),('Cancel','cancel-agreement',None)]
        elif self.view=='permissions':
            for cap in self.preview['capabilities']:
                optional=cap in self.preview['optionalCapabilities'];granted=cap in self.preview['granted'];prior=cap in self.preview['previousGranted']
                rows.append((LABELS[cap]+'  ·  '+('Allowed' if granted else 'Denied')+(' / optional' if optional else ' / required')+(' / new' if granted and not prior else ''),'toggle' if optional else 'info',cap if optional else 'This permission is required by this application.'))
            rows.append(('Back','agreement',None))
        elif self.view=='footprint':
            p=self.preview
            rows=[('Program  ·  '+str(p['expandedBytes'])+' bytes','info','Program is copied into internal storage.'),('Private data  ·  '+str(p['privateBytes']//1024)+' KiB','info','Previously '+str(p['previousPrivateBytes']//1024)+' KiB. Your existing drafts are retained.'),('Peak memory  ·  '+str(p['memoryPeakBytes']//1048576)+' MiB','info','Previously '+str(p['previousMemoryPeakBytes']//1048576)+' MiB.'),('Update history  ·  Two releases maximum','info','The last working release is retained. An older inactive release may be removed.'),('Back','agreement',None)]
        elif self.view=='integrity':
            h=self.preview['sha256'];rows=[('SHA-256 '+str(i+1)+'  ·  '+h[i*16:(i+1)*16],'info','Matches the verified archive.') for i in range(4)]+[('Back','agreement',None)]
        elif self.view=='detail':
            item=self.selected
            if item['state']=='committed':
                rows=[('Open','open',item['code']),('Remove program','confirm-remove',None)]
                for v in item.get('rollbackVersions',[]):rows.append(('Restore '+v,'confirm-rollback',v))
            else:
                rows=[('Not installed','info','Install from a cartridge to use this application.'),('Private data retained' if item.get('retainedData') else 'Installation record only','info','Private drafts and settings are retained.' if item.get('retainedData') else 'Identity and permissions are remembered. No private data store is present.')]
                if item.get('retainedData'):rows.append(('Delete retained private data','confirm-delete',None))
            rows.append(('Back','installed',None))
        elif self.view=='confirm':rows=[('Cancel','detail',None),('Confirm '+self.confirmation[0],'confirmed',None)]
        elif self.view in ('verifying','progress'):
            if self.busy and self.status.get('phase') not in ('commit-intent','committed'):rows.append(('Cancel operation','cancel',None))
            rows.append(('Back to applications','installed',None))
        elif self.view=='complete':
            if self.status.get('code') and self.status.get('operation') not in ('uninstall','delete-data'):rows.append(('Open','open',self.status['code']))
            rows.append(('Applications','installed',None))
        return rows
    def action(self,index):
        rows=self.make_rows()
        if not 0<=index<len(rows):return False
        _,action,value=rows[index];self.cursor=0
        if action=='cancel-shutdown':self.shutdown_waiting=False;self.state.shutdown_requested=False;self.notice='Shutdown cancelled.'
        elif action=='select':
            if self.view=='cartridges':
                if value['action']!='application.install.v0':self.notice='This cartridge is readable, but its installation action is not supported here.'
                else:self.submit('inspect',INSTALLER,1,dict(epoch=self.epoch,generation=self.generation,token=value['token']))
            else:self.selected=value;self.view='detail';self.notice=('Not installed · ' if value['state']=='uninstalled' else '')+value['name']+' '+value['version']
        elif action=='agree':
            p=self.preview;downgrade=False
            if p['previousVersion']:
                from guide_installer import version_key
                downgrade=version_key(p['version'])<version_key(p['previousVersion'])
            if downgrade:self.confirmation=('downgrade',None);self.view='confirm';self.notice='Install '+p['version']+', older than '+('the remembered ' if p.get('previousState')=='uninstalled' else 'the installed ')+p['previousVersion']+'? Saved data will be retained.'
            else:self.begin(False)
        elif action=='confirmed':
            kind,value=self.confirmation
            if kind=='downgrade':self.begin(True)
            else:self.submit('rollback' if kind=='rollback' else 'remove',INSTALLER,8 if kind=='rollback' else 7 if kind=='delete data' else 6,dict(id=self.selected['id'],expectedGeneration=self.selected['generation'],requestId=uuid.uuid4().hex,**({'version':value} if kind=='rollback' else {})))
        elif action.startswith('confirm-'):
            kind={'confirm-remove':'remove program','confirm-delete':'delete data','confirm-rollback':'rollback'}[action];self.confirmation=(kind,value);self.view='confirm';self.notice='Permanently delete retained private drafts and settings?' if kind=='delete data' else 'Restore '+value+'? Current saved data will be retained.' if kind=='rollback' else 'Remove the program? Private drafts and settings will be retained.'
        elif action=='open':self.state.open_application(value)
        elif action=='toggle':
            granted=self.preview['granted'];granted.remove(value) if value in granted else granted.append(value)
        elif action in ('permissions','footprint','integrity','agreement','detail'):self.view=action
        elif action=='installed' or action=='cancel-agreement':self.open('installed')
        elif action=='next':self.page=value;self.refresh()
        elif action=='refresh':self.refresh()
        elif action=='cancel':self.submit('cancel',INSTALLER,4)
        elif action=='status':self.view='progress';self.submit('status',INSTALLER,3)
        elif action=='info':self.notice=value
        self.state.revision+=1;return True
    def begin(self,downgrade):
        self.submit('install',INSTALLER,2,dict(token=self.preview['token'],requestId=uuid.uuid4().hex,granted=self.preview['granted'],downgrade=downgrade))
    def key(self,code):
        if code==316:self.state.go_home();return True
        if code==304:
            if self.view in ('permissions','footprint','integrity'):self.view='agreement'
            elif self.view=='confirm':self.view='agreement' if self.confirmation[0]=='downgrade' else 'detail'
            elif self.view=='detail':self.open('installed')
            else:self.state.go_back()
            self.cursor=0;return True
        rows=self.make_rows()
        if code in (544,545):self.cursor=max(0,min(len(rows)-1,self.cursor+(1 if code==545 else -1)))
        elif code==305:self.action(self.cursor)
        return True
    def model(self):
        from guide_ui_model import ScreenModel,MenuItem,ActionHint
        title={'cartridges':'External Card / Cartridges','installed':'Applications','agreement':'Cartridge / Agreement','permissions':'Agreement / Permissions','footprint':'Agreement / Footprint','integrity':'Cartridge / Integrity','progress':'Installation status','verifying':'Verifying cartridge','detail':'Application','complete':'Installation complete','confirm':'Confirm action'}[self.view]
        rows=self.make_rows();self.cursor=max(0,min(self.cursor,len(rows)-1))
        return ScreenModel('field-list',title,items=tuple(MenuItem('installer:'+str(i),row[0],'installer-action',i) for i,row in enumerate(rows)),focus_id='installer:'+str(self.cursor),notice=self.notice)
    def prepare_shutdown(self):
        if not self.shutdown_waiting:
            self.shutdown_waiting=True;self.shutdown_ready=False;self.shutdown_deadline=time.monotonic()+20
            self.state.page='installer';self.view='progress';self.notice='Finishing installation before shutdown…'
        if self.shutdown_ready:return True
        if time.monotonic()>self.shutdown_deadline:
            self.shutdown_waiting=False;self.state.shutdown_requested=False
            self.notice='Installation did not finish. Shutdown cancelled; try again.';return False
        if not self.pending and time.monotonic()>=self.next_poll:
            self.next_poll=time.monotonic()+.1;self.submit('shutdown',INSTALLER,9)
        return False
    def shutdown(self):
        self.pool.shutdown(wait=True,cancel_futures=True)
        # Shutdown waits outside the interactive loop; the service cancels only
        # before commit and completes/reconciles its bounded critical phase.
        end=time.monotonic()+20
        while time.monotonic()<end:
            try:
                result=self.rpc(INSTALLER,9,{})
                if result['ready']:return True
            except OSError:return True
            time.sleep(.1)
        return False
