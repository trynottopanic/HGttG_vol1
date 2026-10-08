"""Video options rendered by the display-owning player, controlled by the shell."""
class VideoOptions:
    def __init__(self):
        self.view=None;self.cursor=0;self.inventory={};self.notice=''
    def reset(self):
        self.view=None;self.cursor=0;self.inventory={};self.notice=''
    def rows(self):
        if self.view=='options':
            return [('subtitle','Subtitle track'),('audio','Audio track')]
        tracks=self.inventory.get(self.view,[])
        return ([(None,'None')] if self.view=='subtitle' else [])+[(t['id'],t['label']) for t in tracks]
    def handle(self,key,engine,select):
        if key=='close':self.reset();engine.backend.command('raw','show-text','',0);return
        if key=='open':
            self.inventory=engine.tracks();self.view='options';self.cursor=0;self.notice=''
        elif not self.view:return
        elif key=='back':
            if self.view=='options':return self.handle('close',engine,select)
            self.cursor=0 if self.view=='subtitle' else 1;self.view='options';self.notice=''
        elif key in ('up','down'):
            rows=self.rows()
            if rows:self.cursor=(self.cursor+(-1 if key=='up' else 1))%len(rows)
        elif key=='choose':
            rows=self.rows()
            if not rows:self.notice='No audio tracks available.'
            elif self.view=='options':
                self.view=rows[self.cursor][0];self.inventory=engine.tracks();self.cursor=0
                for index,(identity,_) in enumerate(self.rows()):
                    if any(t['id']==identity and t['selected'] for t in self.inventory[self.view]):
                        self.cursor=index;break
            else:
                try:
                    select(self.view,rows[self.cursor][0]);self.inventory=engine.tracks()
                    self.notice='Track selected.'
                except (ValueError,RuntimeError):self.notice='Track unavailable. Choose another track.'
        else:raise ValueError('Unknown video option key')
        self.draw(engine)
    def draw(self,engine):
        if not self.view:return
        rows=self.rows();start=max(0,self.cursor-3)
        text=['Video options' if self.view=='options' else self.view.title()+' track','']
        for index,(_,label) in enumerate(rows[start:start+6],start):
            selected=(self.view=='subtitle' and index==0 and not any(t['selected'] for t in self.inventory['subtitle']))
            if self.view!='options':
                selected=selected or any(t['id']==rows[index][0] and t['selected'] for t in self.inventory.get(self.view,[]))
            label=label if len(label)<=36 else label[:35]+'…'
            text.append(('> ' if index==self.cursor else '  ')+label+(' [selected]' if selected else ''))
        if not rows:text.append('No audio tracks available.')
        text+=['',self.notice,'Up/Down: move   A: choose   B: back']
        # Raw text disables property expansion of untrusted track titles.
        engine.backend.command('raw','show-text','\n'.join(text),2147483647)
