"""Prototype destination picker and transfer list, shared with the browser UI."""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib
candidate=Path('/usr/lib/guideos/transfers')
if not candidate.exists():candidate=Path(__file__).resolve().parents[3]/'package/guide-transfers'
sys.path.insert(0,str(candidate))
from transfer_service import request

class TransferWindow(Gtk.Window):
    def __init__(self,parent,job=None):
        super().__init__(title='Transfers',transient_for=parent,modal=True)
        self.set_default_size(600,420)
        self.pool=ThreadPoolExecutor(max_workers=1)
        self.job=job;self.folder=None;self.history=[];self.offset=0;self.page=0;self.remoteoffset=0;self.alive=True;self.busy=False
        self.box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        scroll=Gtk.ScrolledWindow();scroll.set_child(self.box);self.set_child(scroll);self.connect('close-request',self.closed)
        self.refresh()
        self.timer=GLib.timeout_add_seconds(1,self.tick)
    def closed(self,*_):
        self.alive=False;self.pool.shutdown(wait=False,cancel_futures=True)
        if hasattr(self,'timer'):GLib.source_remove(self.timer)
        return False
    def tick(self):
        if not self.alive:return False
        if not self.job and not self.busy:self.refresh()
        return True
    def call(self,op,callback,**args):
        if self.busy:return
        self.busy=True
        future=self.pool.submit(request,op,**args)
        def completed(f):
            def show():
                self.busy=False
                if not self.alive:return False
                try:result=f.result()
                except Exception:self.message('Transfer service unavailable. Close and retry.');return False
                callback(result);return False
            GLib.idle_add(show)
        future.add_done_callback(completed)
    def clear(self):
        while self.box.get_first_child():self.box.remove(self.box.get_first_child())
    def text(self,text):
        label=Gtk.Label(label=text,xalign=0);label.set_wrap(True);self.box.append(label)
    def button(self,text,callback):
        b=Gtk.Button(label=text);b.connect('clicked',lambda *_:callback());self.box.append(b)
    def message(self,text):
        self.clear();self.text(text);self.button('Close',self.close)
    def refresh(self):
        if self.job:
            if self.folder:self.call('list',self.folders,folder=self.folder,offset=self.offset)
            else:self.call('locations',self.locations)
        else:self.call('snapshot',self.jobs,offset=self.remoteoffset)
    def locations(self,result):
        self.clear();self.text('Choose where to save '+self.job['name'])
        for row in result['locations']:
            if row['available']:self.button(row['name'],lambda r=row:self.enter(r['id']))
        self.button('Cancel download',lambda:self.call('cancel',lambda _:self.close(),id=self.job['id']))
    def enter(self,folder):
        self.history.append((self.folder,self.offset));self.folder=folder;self.offset=0;self.refresh()
    def back(self):
        self.folder,self.offset=self.history.pop() if self.history else (None,0);self.refresh()
    def folders(self,result):
        self.clear();self.text('Save '+self.job['name']+' in this folder?')
        self.button('Save here',lambda:self.call('start',self.started,id=self.job['id'],folder=self.folder,collision='ask'))
        for item in result['items']:
            if item['kind']=='folder':self.button(item['name'],lambda i=item:self.enter(i['id']))
        if self.offset:self.button('Previous folders',lambda:self.next(max(0,self.offset-32)))
        if result['next'] is not None:self.button('Next folders',lambda:self.next(result['next']))
        self.button('Back',self.back)
        self.button('Cancel download',lambda:self.call('cancel',lambda _:self.close(),id=self.job['id']))
    def next(self,offset):self.offset=offset;self.refresh()
    def started(self,_):self.job=None;self.folder=None;self.refresh()
    def jobs(self,result):
        self.clear();self.text('Transfers')
        jobs=result['jobs']
        for job in jobs[self.page:self.page+4]:
            progress=str(job['bytes'])+' bytes' if job.get('total') is None else str(job['bytes'])+' / '+str(job['total'])+' bytes'
            self.text(job['name']+' — '+job['state']+' — '+progress)
            if job.get('reason'):self.text(job['reason'].replace('-',' '))
            if job.get('reason')=='name-collision':
                self.button('Keep both: '+job['name'],lambda j=job:self.call('start',lambda _:self.refresh(),id=j['id'],folder=j['folder'],collision='keep-both'))
                self.button('Skip existing: '+job['name'],lambda j=job:self.call('start',lambda _:self.refresh(),id=j['id'],folder=j['folder'],collision='skip'))
            elif job['state'] in ('failed','cancelled'):
                self.button('Retry from beginning: '+job['name'],lambda j=job:self.choose(j))
            elif job.get('reason')=='choose-destination':self.button('Choose destination',lambda j=job:self.choose(j))
            if job['state'] not in ('completed','failed','cancelled','finalizing'):
                self.button('Cancel: '+job['name'],lambda j=job:self.call('cancel',lambda _:self.refresh(),id=j['id']))
        if not jobs:self.text('No transfers')
        if self.page:self.button('Previous transfers',lambda:self.jobs_page(max(0,self.page-4)))
        if self.page+4<len(jobs):self.button('More transfers',lambda:self.jobs_page(self.page+4))
        if self.remoteoffset:self.button('Earlier history page',lambda:self.history_page(max(0,self.remoteoffset-16)))
        if result.get('next') is not None:self.button('More history',lambda:self.history_page(result['next']))
        self.button('Close — transfers continue',self.close)
    def history_page(self,offset):self.remoteoffset=offset;self.page=0;self.refresh()
    def jobs_page(self,page):self.page=page;self.refresh()
    def choose(self,job):self.job=job;self.folder=None;self.history=[];self.refresh()
