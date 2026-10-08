"""Guide-owned transfer history, destination selection and collision decisions."""
import sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from guide_ui_model import ScreenModel,MenuItem
candidate=Path('/usr/lib/guideos/transfers')
if not candidate.exists():candidate=Path(__file__).resolve().parents[1]/'guide-transfers'
sys.path.insert(0,str(candidate))
from transfer_service import request

class TransfersPanel:
    def __init__(self,client=request):
        self.client=client;self.pool=ThreadPoolExecutor(max_workers=1);self.future=None
        self.jobs=[];self.listing={};self.selected=None;self.folder=None;self.history=[];self.offset=0
        self.view='jobs';self.error='';self.next_poll=0;self.joboffset=0;self.next_jobs=None
    @property
    def busy(self):return self.future is not None
    def submit(self,kind,op,**args):
        if self.busy:return
        self.kind=kind;self.error='';self.future=self.pool.submit(self.client,op,**args)
    def poll(self):
        changed=False
        if self.future and self.future.done():
            f=self.future;self.future=None
            try:
                value=f.result()
                if self.kind=='jobs':
                    self.jobs=value['jobs'];self.next_jobs=value.get('next')
                    if self.view=='details':self.selected=next((j for j in self.jobs if j['id']==self.selected['id']),self.selected)
                elif self.kind=='offer':self.selected=value;self.destinations()
                elif self.kind=='folders':self.listing=value
                else:self.view='jobs';self.next_poll=0
            except Exception as exc:self.error=str(exc)[:160]
            changed=True
        if not self.busy and self.view in ('jobs','details') and time.monotonic()>=self.next_poll:
            self.next_poll=time.monotonic()+1;self.submit('jobs','snapshot',offset=self.joboffset)
        return changed
    def offer_copy(self,entry,name):self.submit('offer','offer',source={'entry':entry},name=name)
    def destinations(self):
        self.view='destination';self.folder=None;self.offset=0;self.history=[];self.submit('folders','locations')
    def act(self,action,value=None):
        if self.busy:return
        if action=='jobs-page':self.joboffset=value;self.next_poll=0
        elif action=='details':self.selected=next(j for j in self.jobs if j['id']==value);self.view='details'
        elif action=='destination':self.destinations()
        elif action=='folder':
            self.history.append((self.folder,self.offset));self.folder=value;self.offset=0
            self.submit('folders','list',folder=value,offset=0)
        elif action=='page':self.offset=value;self.submit('folders','list',folder=self.folder,offset=value)
        elif action=='save':self.submit('started','start',id=self.selected['id'],folder=self.folder,collision='ask')
        elif action in ('keep-both','skip'):self.submit('started','start',id=self.selected['id'],folder=self.selected['folder'],collision=action)
        elif action=='cancel':self.submit('cancelled','cancel',id=self.selected['id'])
        elif action=='back':
            if self.view=='destination' and self.history:
                self.folder,self.offset=self.history.pop()
                if self.folder:self.submit('folders','list',folder=self.folder,offset=self.offset)
                else:self.submit('folders','locations')
            else:self.view='jobs';self.next_poll=0
    def model(self):
        items=[];notice=self.error or ('Working…' if self.busy else '')
        if self.view=='jobs':
            title='Transfers'
            for j in self.jobs:items.append(MenuItem(j['id'],j['name']+' — '+j['state'],'details',j['id']))
            if not items:notice=notice or 'No transfers'
            if self.joboffset:items.append(MenuItem('previous-jobs','Previous transfers','jobs-page',max(0,self.joboffset-16)))
            if self.next_jobs is not None:items.append(MenuItem('next-jobs','More transfers','jobs-page',self.next_jobs))
        elif self.view=='destination':
            title='Choose destination'
            notice=notice or self.selected['name']
            if self.folder:items.append(MenuItem('save','Save in this folder','save'))
            for r in self.listing.get('locations',[]):
                if r['available'] and r['writable']:items.append(MenuItem(r['id'],r['name'],'folder',r['id']))
            for e in self.listing.get('items',[]):
                if e['kind']=='folder':items.append(MenuItem(e['id'],e['name'],'folder',e['id']))
            if self.offset:items.append(MenuItem('previous','Previous folders','page',max(0,self.offset-32)))
            if self.listing.get('next') is not None:items.append(MenuItem('next','Next folders','page',self.listing['next']))
        else:
            title='Transfer details';j=self.selected
            total='unknown total' if j.get('total') is None else str(j['total'])+' bytes total'
            notice=notice or j.get('reason','').replace('-',' ')
            for identity,label in [('name',j['name']),('state',j['state']),('bytes',str(j['bytes'])+' bytes / '+total)]:items.append(MenuItem(identity,label,'noop',enabled=False))
            if j.get('reason')=='name-collision':items += [MenuItem('keep','Keep both','keep-both'),MenuItem('skip','Skip existing file','skip')]
            elif j['state'] in ('failed','cancelled') or j.get('reason')=='choose-destination':items.append(MenuItem('retry','Choose destination / restart','destination'))
            if j['state'] not in ('completed','failed','cancelled','finalizing'):items.append(MenuItem('cancel','Cancel transfer','cancel'))
            if j['state']=='completed':notice=notice or 'Saved. No independent source checksum was supplied.'
        if self.view!='jobs':items.append(MenuItem('back','Back — transfers continue','back'))
        return ScreenModel(pattern='standard-menu',title=title,items=tuple(items),notice=notice)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
