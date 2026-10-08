"""Notepad internal-draft preview. Uses only the mediated application API."""
import json
import time
import unicodedata

MAX_CHARS=5120
MAX_BYTES=20480
MAX_DRAFTS=16

def text_checked(text):
    if type(text) is not str:raise ValueError('Text must be UTF-8.')
    text=text.removeprefix('\ufeff').replace('\r\n','\n').replace('\r','\n')
    if len(text)>MAX_CHARS or len(text.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Document exceeds 5120 characters or 20480 bytes.')
    return text

def name_checked(name):
    if type(name) is not str:raise ValueError('Enter a draft name.')
    name=unicodedata.normalize('NFC',name)
    if not 1<=len(name)<=32 or name in ('.','..') or name[-1] in ' .':
        raise ValueError('Use 1 to 32 characters; no trailing space or period.')
    if any(unicodedata.category(c).startswith('C') or c in '/\\:*?"<>|' for c in name):
        raise ValueError('This name contains an unsupported character.')
    stem=name.split('.')[0].upper()
    if stem in ('CON','PRN','AUX','NUL') or stem in tuple(p+str(i) for p in ('COM','LPT') for i in range(1,10)):
        raise ValueError('This filename is reserved.')
    return name

def encode_checkpoint(doc):
    if doc is None:return 'NOTEPAD1\nnull\n'
    text=text_checked(doc['text'])
    meta={k:doc[k] for k in ('name','slot','dirty','caret')}
    meta.update(location='Internal draft' if doc['slot'] is not None else 'Unsaved',card=None,generation=None,expected=None)
    # Raw text avoids JSON escaping multiplying document storage requirements.
    result='NOTEPAD1\n'+json.dumps(meta,ensure_ascii=False,separators=(',',':'))+'\n'+text
    if len(result.encode('utf-8'))>24576:raise ValueError('Recovery checkpoint is too large.')
    return result

def decode_checkpoint(raw):
    if not raw:return None
    if len(raw.encode('utf-8'))>24576:raise ValueError('Invalid recovery checkpoint.')
    magic,header,text=raw.split('\n',2)
    if magic!='NOTEPAD1':raise ValueError('Unknown recovery format.')
    meta=json.loads(header)
    if meta is None:
        if text:raise ValueError('Invalid empty checkpoint.')
        return None
    if type(meta)is not dict or set(meta)!={'name','slot','dirty','caret','location','card','generation','expected'}:
        raise ValueError('Invalid recovery metadata.')
    name=name_checked(meta['name']) if meta['name'] else ''
    slot=meta['slot']
    if slot is not None and (type(slot)is not int or not 0<=slot<16):raise ValueError('Invalid recovery draft.')
    if type(meta['dirty'])is not bool or type(meta['caret'])is not int or not 0<=meta['caret']<=len(text):raise ValueError('Invalid recovery state.')
    if meta['location'] not in ('Internal draft','Unsaved') or any(meta[k] is not None for k in ('card','generation','expected')):raise ValueError('Unsupported recovery destination.')
    return dict(name=name,slot=slot,dirty=meta['dirty'],caret=meta['caret'],text=text_checked(text))

class Notepad:
    def __init__(self,api):
        self.api=api
        self.private=api.acquire(2);self.visual=api.acquire(3);self.actions=api.acquire(4);self.text_grant=api.acquire(5)
        self.index=[];self.doc=None;self.recovery=None;self.page=0;self.view='list';self.notice=''
        self.handlers=[];self.text_mode=None;self.pending_name=None;self.blocked=False;self.preview_page=0
        self.previews={};self.close_after_save=False
        try:
            raw=api.read(self.private,'draft-index')
            if raw:
                rows=json.loads(raw)
                if type(rows)is not list or len(rows)>16:raise ValueError('Invalid draft index.')
                seen=set()
                for row in rows:
                    if type(row)is not dict or set(row)!={'name','slot'} or type(row['slot'])is not int or not 0<=row['slot']<16:raise ValueError('Invalid draft index.')
                    name=name_checked(row['name'])
                    if name.casefold() in seen or any(r['slot']==row['slot'] for r in self.index):raise ValueError('Ambiguous draft index.')
                    seen.add(name.casefold());self.index.append(dict(name=name,slot=row['slot']))
                if len(raw.encode('utf-8'))>65536:raise ValueError('Metadata exceeds its limit.')
            self.recovery=decode_checkpoint(api.read(self.private,'checkpoint'))
            if self.recovery is not None:
                clean=self.recovery
                row=next((r for r in self.index if r['slot']==clean['slot'] and r['name']==clean['name']),None)
                matches=False
                if not clean['dirty'] and row:
                    raw=api.read(self.private,'draft-'+str(row['slot']))
                    matches=raw.startswith('TEXT1\n') and text_checked(raw[6:])==clean['text']
                if matches:self.recovery=None
                elif not clean['dirty'] and clean['slot'] is None and not clean['text']:self.recovery=None
                else:self.view='recovery'
            for row in self.index:
                raw=api.read(self.private,'draft-'+str(row['slot']))
                self.previews[row['slot']]=self.summary(text_checked(raw[6:])) if raw.startswith('TEXT1\n') else 'Saved note unavailable.'
        except (ValueError,KeyError,TypeError,UnicodeError,OSError,PermissionError):
            self.blocked=True;self.notice='Stored draft metadata or recovery is invalid. Existing data has been left unchanged.'
        self.render();api.ready()

    @staticmethod
    def summary(text):
        return ' '.join(''.join(c if not unicodedata.category(c).startswith('C') else ' ' for c in text).split())[:96] or '(Empty note)'

    def checkpoint(self):
        if self.blocked:raise ValueError('Recovery data needs review; it has not been replaced.')
        return self.api.write(self.private,'checkpoint',encode_checkpoint(self.recovery if self.view=='recovery' else self.doc))

    def open_draft(self,row):
        raw=self.api.read(self.private,'draft-'+str(row['slot']))
        if not raw.startswith('TEXT1\n'):raise ValueError('The saved draft is missing or invalid; it was left unchanged.')
        text=text_checked(raw[6:])
        self.doc=dict(name=row['name'],slot=row['slot'],dirty=False,caret=0,text=text)
        self.preview_page=0;self.view='editor';self.notice='';self.checkpoint()

    def new(self):
        self.doc=dict(name='',slot=None,dirty=False,caret=0,text='');self.view='editor';self.preview_page=0;self.notice='';self.checkpoint();self.edit()

    def edit(self):
        self.text_mode='edit';self.api.text(self.text_grant,self.doc['text'],MAX_CHARS,label='Note text',multiline=True,caret=self.doc['caret'],submit_label='Done')

    def save_as(self):
        self.text_mode='name';self.api.text(self.text_grant,self.doc['name'],32,label='Note name',multiline=False,caret=len(self.doc['name']),submit_label='Save')

    def save(self):
        if self.doc['slot'] is None:return self.save_as()
        self.persist(self.doc['name'],self.doc['slot'])

    def persist(self,name,slot):
        text=text_checked(self.doc['text'])
        # Sixteen bounded documents total <= 320 KiB, below the 384 KiB ceiling.
        self.api.write(self.private,'draft-'+str(slot),'TEXT1\n'+text)
        rows=[r for r in self.index if r['slot']!=slot]+[dict(name=name,slot=slot)]
        rows.sort(key=lambda r:r['slot'])
        encoded=json.dumps(rows,ensure_ascii=False,separators=(',',':'))
        self.api.write(self.private,'draft-index',encoded)
        self.index=rows;self.doc.update(name=name,slot=slot,dirty=False)
        self.previews[slot]=self.summary(text)
        self.notice='';self.view='editor';self.checkpoint()
        if self.close_after_save:
            self.close_after_save=False;self.close_document()

    def accept_name(self,value):
        name=name_checked(value)
        existing=next((r for r in self.index if r['name'].casefold()==name.casefold()),None)
        if existing:
            self.pending_name=existing;self.view='replace';return
        used={r['slot'] for r in self.index}
        if len(used)>=16:raise ValueError('All 16 draft slots are used. Save As an existing name to request replacement, or return to editing.')
        self.persist(name,next(i for i in range(16) if i not in used))

    def close_document(self):
        if self.doc and self.doc['dirty']:self.view='close';return
        self.api.write(self.private,'checkpoint',encode_checkpoint(None))
        self.doc=None;self.view='list';self.close_after_save=False

    def discard(self):
        self.api.write(self.private,'checkpoint',encode_checkpoint(None))
        self.doc=None;self.recovery=None;self.view='list';self.close_after_save=False;self.notice='Changes discarded. Saved drafts are unchanged.'

    def restore(self):
        self.doc=self.recovery;self.recovery=None;self.doc['dirty']=True
        self.view='editor';self.notice='Recovered unsaved buffer; no saved draft was overwritten.'
        self.checkpoint()

    def save_and_close(self):
        self.close_after_save=True;self.save()

    def render(self):
        entries=[];title='Notepad';body=self.notice;presentation=None
        def add(label,fn):entries.append((label,fn))
        if self.blocked:
            body=self.notice+' Return Home; retained data requires review.'
        elif self.view=='recovery':
            body='An interrupted edit is available. Restore it or explicitly discard it.'
            add('Restore recovery',self.restore);add('Discard recovery',lambda:self.set_view('discard'))
        elif self.view=='list':
            add('New note',self.new)
            for row in self.index:add(row['name'],lambda row=row:self.open_draft(row))
            presentation={0:'notes',1:'Internal drafts',4:['']+[self.previews.get(r['slot'],'Saved note unavailable.') for r in self.index]}
        elif self.view=='editor':
            body=self.doc['text']
            add('Edit text',self.edit);add('Save internal draft',self.save)
            add('Actions',lambda:self.set_view('actions'));add('Close note',self.close_document)
            presentation={0:'document',1:self.doc['name'] or 'Untitled',2:'Internal draft' if self.doc['slot'] is not None else 'Unsaved',3:'unsaved' if self.doc['dirty'] or self.doc['slot'] is None else 'saved',5:{0:0,1:1,2:2,3:3},6:self.notice}
        elif self.view=='actions':
            add('Save As internal draft',self.save_as);add('Close note',self.close_document);add('Back to note',lambda:self.set_view('editor'))
            presentation={0:'menu',5:{3:2}}
        elif self.view=='replace':
            body='Replace the internal draft named '+self.pending_name['name']+'? This changes its saved text.'
            add('Replace draft',lambda:self.persist(self.pending_name['name'],self.pending_name['slot']));add('Return to note',lambda:self.set_view('editor'))
            presentation={0:'menu',5:{3:1}}
        elif self.view=='close':
            body='This note has unsaved changes. Save an internal draft, discard changes, or continue editing.'
            add('Keep as internal draft',self.save_and_close);add('Discard changes',lambda:self.set_view('discard'));add('Continue editing',lambda:self.set_view('editor'))
            presentation={0:'menu',5:{3:2}}
        elif self.view=='discard':
            body='Discard this unsaved buffer? Existing saved drafts remain unchanged.'
            add('Confirm discard',self.discard);add('Keep editing',lambda:self.set_view('recovery' if self.recovery is not None else 'editor'))
            presentation={0:'menu',5:{3:1}}
        self.handlers=[fn for label,fn in entries]
        self.api.present(self.visual,title,body,[label for label,fn in entries],presentation=presentation)

    def set_view(self,view):
        self.view=view
        if view=='editor':self.close_after_save=False
    def turn(self,delta):self.page+=delta
    def read_turn(self,delta):self.preview_page+=delta

    def handle(self,event):
        try:
            if event[0]==1:
                index=event[1]
                if type(index)is int and 0<=index<len(self.handlers):self.handlers[index]()
            elif event[0]==2:
                mode=self.text_mode;self.text_mode=None
                if event[1] is not None:
                    if mode=='edit':
                        text=text_checked(event[1]);caret=event.get(3,len(text))
                        if type(caret)is not int or not 0<=caret<=len(text):raise ValueError('Invalid editing position.')
                        dirty=self.doc['dirty'] or text!=self.doc['text']
                        self.doc.update(text=text,dirty=dirty,caret=caret);self.preview_page=0
                        self.checkpoint();self.notice=''
                    elif mode=='name' and not event.get(2):self.accept_name(event[1])
                else:
                    self.close_after_save=False
                    if mode=='name':self.view='editor'
                    if self.doc and self.doc['slot'] is None and not self.doc['text'] and not self.doc['dirty']:
                        self.close_document()
            elif event[0]==3:
                receipt=self.checkpoint();self.api.checkpointed(receipt);return
            else:return
        except (ValueError,PermissionError,OSError) as exc:
            self.close_after_save=False
            if self.doc is not None and isinstance(exc,(PermissionError,OSError)):self.doc['dirty']=True
            self.notice=(str(exc)[:200] if isinstance(exc,ValueError) else 'Storage or permission unavailable. Current text is retained; save was not confirmed.')
            if event[0]==3:return # Never acknowledge a checkpoint that did not complete.
            if self.doc is not None:self.view='editor'
        self.render()

def application(api):
    app=Notepad(api)
    while True:
        app.handle(api.event())
        time.sleep(.01)
