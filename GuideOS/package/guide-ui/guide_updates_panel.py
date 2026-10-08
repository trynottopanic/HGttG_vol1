"""Asynchronous Guide-owned Updates UI; never exposed to web content."""
import json,socket,time
from concurrent.futures import ThreadPoolExecutor
from guide_ui_model import ScreenModel,MenuItem,Fact

def deploy(op,**args):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(120 if op=='import-file' else 5)
        s.connect('/run/guideos-deploy/control.sock')
        s.sendall(json.dumps(dict(op=op,**args)).encode()+b'\n')
        with s.makefile('rb') as f:raw=f.readline(360001)
        if len(raw)>360000:raise ValueError('Response too large')
        r=json.loads(raw)
        if not r['ok']:raise ValueError(r['reason'].replace('-',' '))
        return r['result']

class UpdatesPanel:
    def __init__(self,client=deploy,files=None):
        self.client=client;self.files=files;self.pool=ThreadPoolExecutor(max_workers=1)
        self.future=None;self.status={};self.error='';self.view='overview';self.preview_id=None
        self.next_poll=0;self.folder=None;self.history=[];self.listing={};self.offset=0
        self._blocks_display=False
    @property
    def busy(self):return self.future is not None
    @property
    def display_busy(self):
        return bool(self.future is not None and not self.future.done() and self._blocks_display)
    def submit(self,operation,blocks_display=False):
        if self.busy:return
        self.error='';self._blocks_display=blocks_display;self.future=self.pool.submit(operation)
    def poll(self):
        changed=False
        if self.future and self.future.done():
            future=self.future;self.future=None;self._blocks_display=False
            try:
                kind,result=future.result()
                if kind=='status':self.status=result
                else:self.listing=result
            except Exception as exc:self.error=str(exc)[:160]
            changed=True
        if not self.busy and self.view not in ('files','confirm') and time.monotonic()>=self.next_poll:
            self.next_poll=time.monotonic()+1
            self.submit(lambda:('status',self.client('status')))
        return changed
    def storage(self,op,args):
        if self.files:return self.files(op,args)
        from guide_files_panel import FilesPanel
        return FilesPanel.storage(op,args)
    def act(self,action,value=None):
        if self.busy:return
        if action=='refresh':self.submit(lambda:('status',self.client('status')))
        elif action=='files':
            self.view='files';self.folder=None;self.history=[];self.offset=0
            self.submit(lambda:('files',self.storage(1,{})))
        elif action=='folder':
            self.history.append((self.folder,self.offset));self.folder=value;self.offset=0
            self.submit(lambda:('files',self.storage(2,dict(folder=value,offset=0))))
        elif action=='next':
            revision=self.listing.get('revision')
            self.offset=value;self.submit(lambda:('files',self.storage(2,dict(folder=self.folder,offset=value,revision=revision))))
        elif action=='back':
            if self.view=='files' and self.history:
                self.folder,self.offset=self.history.pop()
                self.submit(lambda:('files',self.storage(2,dict(folder=self.folder,offset=self.offset)) if self.folder else self.storage(1,{})))
            else:self.view='overview';self.preview_id=None
        elif action=='import':
            self.view='overview'
            def imported():self.client('import-file',entry=value);return 'status',self.client('status')
            self.submit(imported)
        elif action=='review':self.view='confirm';self.preview_id=value
        elif action in ('install','downgrade'):
            if self.view!='confirm' or value!=self.preview_id:raise ValueError('Review this exact update first')
            self.view='overview'
            def install():
                self.client('authorize',id=value,downgrade=action=='downgrade')
                self.client('activate',id=value)
                return 'status',self.client('status')
            self.submit(install,blocks_display=True)
        elif action=='cancel':self.submit(lambda:('status',self.cancel(value)))
        elif action=='review-rollback':self.view='rollback'
        elif action=='rollback' and self.view=='rollback':
            self.view='overview';self.submit(lambda:('status',self.rollback()),blocks_display=True)
    def cancel(self,identity):self.client('cancel',id=identity);return self.client('status')
    def rollback(self):self.client('rollback');return self.client('status')
    def model(self):
        txn=self.status.get('transaction') or {};items=[];facts=[];notice=self.error or ('Working…' if self.busy else '')
        if self.view=='files':
            for location in self.listing.get('locations',[]):
                if location['available']:items.append(MenuItem(location['id'],location['name'],'folder',location['id']))
            for entry in self.listing.get('items',[]):
                items.append(MenuItem(entry['id'],entry['name'],'folder' if entry['kind']=='folder' else 'import',entry['id']))
            if self.offset:items.append(MenuItem('previous','Previous page','next',max(0,self.offset-32)))
            if self.listing.get('next') is not None:items.append(MenuItem('next','Next page','next',self.listing['next']))
            items.append(MenuItem('back','Back','back'))
            title='Choose update file'
        elif self.view=='confirm':
            review=txn.get('review',{});title='Review update'
            facts=[Fact('Source',review.get('source','Unknown')),Fact('Version',review.get('version','Unknown')),Fact('Signer',review.get('signer','Unknown')),Fact('Size',str(review.get('bytes',0))+' bytes'),Fact('Changes',', '.join(review.get('components',[]))),Fact('Restart','Guide interface only'),Fact('Recovery','Previous release retained')]
            if txn.get('id')==self.preview_id and txn.get('state')=='validated':
                downgrade=txn.get('sequence',0)<=self.status.get('highest_sequence',self.status.get('sequence',0))
                label='Install older/same release' if downgrade else 'Install now'
                items.append(MenuItem('install',label+'  ·  '+review.get('version','Unknown'),'downgrade' if downgrade else 'install',txn['id']))
            items.append(MenuItem('later','Keep for later','back'))
            notice=notice or 'External power required. Owner files retained.'
        elif self.view=='rollback':
            title='Restore previous release?';notice=notice or 'Guide restarts. Owner files remain. Physical acceptance is checked separately.'
            items=[MenuItem('restore','Restore previous release','rollback'),MenuItem('back','Cancel','back')]
        else:
            title='Updates'
            active=self.status.get('active',{})
            facts=[Fact('Installed',active.get('version','Checking…')),Fact('Update',txn.get('state','No pending update').replace('-',' '))]
            if txn.get('reason'):notice=notice or txn['reason'].replace('-',' ')
            signed=self.status.get('protocol')=='GUIDE-SIGNED-BUNDLE-1'
            if signed:
                items.append(MenuItem('files','Choose update file','files'))
                if txn.get('state')=='validated':items.append(MenuItem('review','Review ready update','review',txn['id']))
                if txn.get('state') in ('receiving','validated','queued'):items.append(MenuItem('cancel','Cancel pending update','cancel',txn['id']))
                if self.status.get('previous') and txn.get('state') in ('committed','rolled-back','cancelled','rejected',None):items.append(MenuItem('rollback','Recovery: previous release','review-rollback'))
                if txn.get('state')=='committed':notice=notice or 'Installed; automated health passed. Physical acceptance is separate.'
            else:notice=notice or 'Signed updater bootstrap is required on this Seed.'
            items.append(MenuItem('refresh','Refresh','refresh'))
        # Existing menu renderers do not draw facts; retain them as visible rows.
        information=[MenuItem('fact:'+str(i),f.label+': '+(f.value if f.label!='Signer' else f.value[:23]+'…'+f.value[-12:]),'noop',enabled=False) for i,f in enumerate(facts)]
        # The confirm screen must keep its owner actions inside the fixed-size
        # renderer. Review facts remain in the model for richer renderers, while
        # the version is repeated on the install row.
        if self.view!='confirm':items=information+items
        return ScreenModel(pattern='standard-menu',title=title,items=tuple(items),facts=tuple(facts),notice=notice,notice_state='warning' if self.error else 'neutral')
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
