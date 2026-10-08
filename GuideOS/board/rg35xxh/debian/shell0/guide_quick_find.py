"""Offline, cancellable filename/application search over owner-facing providers.

No filesystem paths, document contents or persistent search index are read here.
The storage owner remains responsible for scopes, opaque identities and opening.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import threading
import time
import unicodedata

from guide_input import Keyboard, TextRequest, StickController, KEYBOARD_ACTIONS, renderer
from guide_ui_model import ScreenModel, MenuItem, ActionHint

FILES='/run/guideos-storage/files.sock'
APPS='/run/guideos/installer/control.sock'
SCOPES=(('all','Files and applications'),('internal','Internal files'),
        ('external','External card'),('apps','Applications'))
MAX_RESULTS,MAX_ENTRIES,MAX_FOLDERS,MAX_DEPTH=64,4096,128,12

def fold(value):
    return unicodedata.normalize('NFC',value).casefold()

def rpc(path,op,args):
    for directory in ('/usr/lib/guideos/installer','/usr/lib/guideos/ipc'):
        if directory not in sys.path:sys.path.insert(0,directory)
    from guide_install_wire import call
    result,fds=call(path,op,args,timeout=.5)
    for fd in fds:os.close(fd)
    return result

def search_names(query,scope,cancel,client=rpc,clock=time.monotonic):
    """One bounded worker. Pagination revisions are kept per folder."""
    needle=fold(query.strip())
    if not needle or len(query)>64 or scope not in dict(SCOPES):raise ValueError('Invalid search')
    results=[];partial=False;visited=0;folders=0;deadline=clock()+20
    def stopped():return cancel.is_set() or clock()>=deadline
    def request(path,op,args):
        while not stopped():
            result=client(path,op,args)
            if result.get('errorCode')=='listing-pending':
                cancel.wait(.05);continue
            if 'errorCode' in result:raise ValueError('Provider changed')
            return result
        raise TimeoutError('Search stopped')
    if scope in ('all','apps'):
        try:
            offset=0
            while not stopped():
                page=request(APPS,5,{'offset':offset})
                for app in page['items']:
                    visited+=1
                    if app.get('state')=='committed' and needle in fold(app['name']):
                        results.append(dict(kind='app',name=app['name'],code=app['code'],
                                            label='Application',id='app:'+str(app['code'])))
                    if len(results)>=MAX_RESULTS:return dict(results=results,partial=True)
                nxt=page.get('next')
                if nxt is None:break
                if type(nxt)is not int or nxt<=offset or visited>=128:partial=True;break
                offset=nxt
        except (OSError,ValueError,KeyError,TypeError,TimeoutError):partial=True
    if scope!='apps' and not stopped():
        queue=deque()
        try:
            for root in request(FILES,1,{})['locations']:
                location='internal' if root['id']=='internal' else 'external'
                if root.get('available') and scope in ('all',location):
                    queue.append((root['id'],location,(),root['name']))
            if scope in ('internal','external') and not queue:partial=True
        except (OSError,ValueError,KeyError,TypeError,TimeoutError):partial=True
        while queue and not stopped() and visited<MAX_ENTRIES and folders<MAX_FOLDERS:
            folder,location,parts,label=queue.popleft();folders+=1;offset=0;revision=None
            try:
                while not stopped() and visited<MAX_ENTRIES:
                    args=dict(folder=folder,offset=offset,async_listing=True)
                    if revision is not None:args['revision']=revision
                    page=request(FILES,2,args)
                    if revision is not None and page['revision']!=revision:raise ValueError('Changed listing')
                    revision=page['revision']
                    for entry in page['items']:
                        if visited>=MAX_ENTRIES:partial=True;break
                        visited+=1
                        if entry['kind']=='folder':
                            if len(parts)<MAX_DEPTH and folders+len(queue)<MAX_FOLDERS:
                                queue.append((entry['id'],location,parts+(entry['name'],),label))
                            else:partial=True
                        elif entry['kind']=='file' and needle in fold(entry['name']):
                            results.append(dict(kind='file',id=entry['id'],name=entry['name'],
                                entry=dict(entry),folder=folder,offset=offset,revision=revision,
                                location=location,parts=parts,label=label+(' / '+' / '.join(parts) if parts else '')))
                            if len(results)>=MAX_RESULTS:return dict(results=results,partial=True)
                    nxt=page.get('next')
                    if nxt is None:break
                    if type(nxt)is not int or nxt<=offset:raise ValueError('Invalid pagination')
                    offset=nxt
            except (OSError,ValueError,KeyError,TypeError,TimeoutError):partial=True
        partial=partial or bool(queue) or stopped() or visited>=MAX_ENTRIES
    return dict(results=results,partial=partial or stopped())

class QuickFind:
    def __init__(self,text_entries,client=rpc):
        self.text_entries=text_entries;self.client=client
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='guide-find')
        self.pending=None;self.queued=None;self.cancel=threading.Event();self.generation=0
        self.editor=self.stick_input=self.keyboard_renderer=None
        self.query='';self.scope='all';self.results=[];self.cursor=0
        self.notice='Search filenames and installed application names.';self.busy=False
        self.opened=None

    def open(self):self.edit()

    def edit(self):
        if self.editor:return
        self.editor=Keyboard(self.text_entries,TextRequest(owner_id='quick-find',field_id='query',
            label='Find files and applications',initial=self.query,max_length=64,min_length=1,
            max_bytes=256,submit_label='Find'))
        self.stick_input=StickController(self.editor)

    def finish_editor(self):
        if self.editor and self.editor.session.state!='editing':
            result=self.editor.take_result();self.editor=self.stick_input=None
            if result and result.state=='submitted':self.start(result.text)

    def start(self,query):
        if not query.strip():self.notice='Enter a filename or application name.';return
        self.stop();self.query=query;self.results=[];self.cursor=0;self.busy=True
        self.notice='Searching…';self.cancel=threading.Event()
        self.queued=(self.generation,query,self.scope,self.cancel)
        self.launch()

    def launch(self):
        if self.pending is None and self.queued:
            generation,query,scope,cancel=self.queued;self.queued=None
            self.pending=(generation,self.pool.submit(search_names,query,scope,cancel,self.client),'search',None)

    def stop(self):
        self.cancel.set();self.generation+=1;self.queued=None;self.busy=False;self.opened=None

    def leave(self):
        if self.busy:self.stop();self.notice='Search stopped. Find again to refresh results.'
        if self.editor:self.editor.close();self.editor=self.stick_input=None

    def poll(self):
        if self.pending is None or not self.pending[1].done():return False
        generation,future,operation,row=self.pending;self.pending=None
        if generation==self.generation:
            try:
                result=future.result()
                if operation=='open':
                    if 'errorCode' in result:raise ValueError('File changed')
                    self.opened=row;self.notice=''
                else:
                    self.results=result['results'];self.cursor=0
                    self.notice=('Showing available matches; some locations were unavailable or the search limit was reached.'
                                 if result['partial'] else f'{len(self.results)} matches.' if self.results else 'No matches. Try another name or location.')
            except (OSError,ValueError,KeyError,TypeError):
                self.notice='File changed or storage was removed. Find again.' if operation=='open' else 'Search unavailable. Try again.'
            self.busy=False
        self.launch();return True

    def rows(self):
        rows=[MenuItem('find:edit',self.query or 'Enter a name','find-action','edit'),
              MenuItem('find:scope','Search in: '+dict(SCOPES)[self.scope],'find-action','scope')]
        if self.busy:rows.append(MenuItem('find:stop','Stop search','find-action','stop'))
        for row in self.results:
            rows.append(MenuItem('find:'+row['id'],row['name'],'find-action',row,metadata=row['label']))
        return rows

    def activate(self,value):
        if value=='edit':self.edit()
        elif value=='scope':
            self.scope=SCOPES[(next(i for i,r in enumerate(SCOPES) if r[0]==self.scope)+1)%len(SCOPES)][0]
            if self.query:self.start(self.query)
        elif value=='stop':self.stop();self.notice='Search stopped.'
        elif isinstance(value,dict) and self.pending is None:
            if value['kind']=='app':self.opened=value
            else:
                self.busy=True;self.notice='Opening…'
                self.pending=(self.generation,self.pool.submit(self.client,FILES,3,{'entry':value['id']}),'open',value)

    def key(self,code):
        if self.editor:
            self.editor.handle(KEYBOARD_ACTIONS.get(code));self.finish_editor()
        elif code in (544,545):self.cursor=max(0,min(len(self.rows())-1,self.cursor+(1 if code==545 else -1)))
        elif code==305:self.activate(self.rows()[self.cursor].value)
        return True

    def sticks(self,sample,now=None):
        if not self.stick_input:return False
        changed=self.stick_input.update(left=sample.get('left'),right=sample.get('right'),
            generation=sample.get('generation',0),now=now)
        self.finish_editor();return changed

    def model(self):
        rows=self.rows();self.cursor=min(self.cursor,len(rows)-1)
        return ScreenModel('field-list','Quick Find',items=tuple(rows),focus_id=rows[self.cursor].identity,
            notice=self.notice,actions=(ActionHint('A','Select','blue'),ActionHint('B','Back','blue','back','key',304)))

    def draw_editor(self,sink):
        if self.keyboard_renderer is None:self.keyboard_renderer=renderer()
        sink.show(self.keyboard_renderer.render(self.editor,application_label='QUICK FIND'))

    def close(self):
        self.stop();self.leave();self.pool.shutdown(wait=True,cancel_futures=True)
