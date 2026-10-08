#!/usr/bin/python3
"""Untimed RG35XX H button baseline. SPDX-License-Identifier: AGPL-3.0-or-later."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import time

spec=importlib.util.spec_from_file_location('hardware',Path(__file__).with_name('controller-test.py'))
hw=importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
GAME='H700 Gamepad'
VOLUME='gpio-keys-volume'
# Expected names from the RG35XX H device-tree/joypad profile, not the failed
# diagnostic-3 discovery. Human confirmation of printed labels remains separate.
PROFILE=[('A',GAME,305),('B',GAME,304),('X',GAME,307),('Y',GAME,308),
         ('D-pad Up',GAME,544),('D-pad Right',GAME,547),('D-pad Down',GAME,545),('D-pad Left',GAME,546),
         ('L1',GAME,310),('R1',GAME,311),('L2',GAME,312),('R2',GAME,313),
         ('Left stick click',GAME,317),('Right stick click',GAME,318),('Select',GAME,314),('Menu',GAME,316),
         ('Volume +',VOLUME,115),('Volume -',VOLUME,114)]
EXCLUDED={315,116,408}


class Checklist:
    def __init__(self,devices):
        self.devices=devices
        self.buttons=[]; self.lookup={}; self.active={}; self.last='None yet'
        for label,name,code in PROFILE:
            matches=[i for i,d in enumerate(devices) if d.name==name and code in d.caps.get('1',[])]
            index=matches[0] if len(matches)==1 else None
            row=dict(label=label,device=index,code=code,cycles=0,presses=0,releases=0,
                     initial_held=bool(index is not None and devices[index].keys.get(code)),
                     available=index is not None,down=False,armed=False,needs_release=False)
            if index is not None:
                row['down']=row['initial_held']; row['needs_release']=row['initial_held']
                self.lookup[index,code]=row
            self.buttons.append(row)

    def available(self,row):
        if row['device'] is None: return False
        device=self.devices[row['device']]
        return device.connected and not getattr(device,'dropped',False)

    def resync(self):
        self.active.clear()
        for key,row in self.lookup.items():
            row['down']=bool(self.devices[key[0]].keys.get(key[1]))
            row['armed']=False; row['needs_release']=row['down']

    def disarm(self):
        self.active.clear()
        for row in self.buttons:
            row['armed']=False; row['needs_release']=row['down']

    def consume(self,events,capture=True):
        changed=False
        for event in events:
            device,kind,code,value=event
            row=self.lookup.get((device,code))
            if kind!=1 or code in EXCLUDED or row is None or value not in (0,1) or not self.available(row): continue
            key=(device,code)
            if value==1:
                if row['down']: continue
                row['down']=True
                self.active[key]=getattr(event,'timestamp',time.monotonic())
                self.last=row['label']+' pressed'
                if capture and not row['needs_release']:
                    row['armed']=True; row['presses']+=1
            else:
                was_down=row['down']; row['down']=False; self.active.pop(key,None)
                if capture and was_down and row['armed']:
                    row['releases']+=1; row['cycles']+=1; changed=True
                row['armed']=False; row['needs_release']=False
                self.last=row['label']+' released'
        return changed

    def neutral(self):
        return not any(row['down'] for row in self.buttons if self.available(row))

    def count(self):
        return sum(row['cycles']>0 and self.available(row) for row in self.buttons)


class Navigation:
    """Menu uses any responding included key, independent of learned mappings."""
    def __init__(self):
        self.mode='check'; self.selection=0; self.key=None; self.since=None
        self.held={}; self.blocked=set()

    def pause(self,model):
        self.mode='menu'; self.selection=0; self.key=self.since=None
        self.blocked={key for key,row in model.lookup.items() if row['down']}
        self.held.clear(); model.disarm()
        return 'pause'

    def feed(self,model,event,now):
        # Called before the checklist consumes each event: a queued long hold
        # must be recognized as navigation before its release earns test credit.
        i,t,c,v=event; key=(i,c); row=model.lookup.get(key)
        if t!=1 or row is None or c in EXCLUDED or v not in (0,1) or not model.available(row): return None
        stamp=getattr(event,'timestamp',now)
        if self.mode=='check':
            if v==1 and not row['down'] and not row['needs_release']:
                self.held[key]=stamp
            elif v==0:
                since=self.held.pop(key,None)
                if since is not None and stamp-since>=3:
                    action=self.pause(model)
                    self.blocked.discard(key)
                    return action
            return None
        if self.mode!='menu': return None
        # Release gates are per key. One stuck button cannot disable the menu.
        if key in self.blocked:
            if v==0: self.blocked.discard(key)
            return None
        if v==1 and not row['down']:
            if self.key is None: self.key=key; self.since=stamp
            elif self.key!=key:
                self.blocked.update((key,self.key)); self.key=self.since=None
        elif v==0 and self.key==key:
            duration=stamp-self.since; self.key=self.since=None
            if duration>=2: return self.choose(model)
            self.selection=(self.selection+1)%3
        return None

    def tick(self,model,now):
        if self.mode=='check' and any(now-since>=3 and model.available(model.lookup[key])
                                      for key,since in self.held.items()):
            return self.pause(model)
        return None

    def choose(self,model):
        self.key=self.since=None
        if self.selection==0:
            self.mode='check'; self.held.clear(); model.disarm(); return 'resume'
        self.mode='finished'
        return 'finish_match' if self.selection==1 else 'finish_uncertain'

    def interrupted(self,model):
        self.pause(model)


def process(model,nav,events,now):
    changed=False; actions=[]
    for event in events:
        previous=nav.mode
        action=nav.feed(model,event,now)
        changed |= model.consume([event],capture=previous=='check' and nav.mode=='check')
        if action: actions.append(action)
        if nav.mode=='finished': break
    action=nav.tick(model,now)
    if action: actions.append(action)
    return changed,actions


class EventLog:
    def __init__(self,file): self.file=file; self.phase='check'
    def write(self,text):
        row=json.loads(text); row['baseline_phase']=self.phase
        self.file.write(json.dumps(row)+'\n')


class Display:
    def __init__(self,sink):
        from PIL import Image,ImageDraw,ImageFont
        self.Image,self.Draw,self.sink=Image,ImageDraw,sink
        self.font={s:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',s) for s in (14,16,18,20,26)}

    def draw(self,model,nav,notice='',hold=0):
        im=self.Image.new('RGB',(640,480),'#101c2c'); d=self.Draw.Draw(im)
        def text(x,y,value,size=18,color='#f1f5fa'):
            d.text((x,y),value,font=self.font[size],fill=color)
        text(18,12,'RG35XX H  /  BUTTON CHECK',26)
        if nav.mode=='check':
            text(18,51,'Press and release every button, in any order.',20)
            text(18,81,'Check that the lit name matches what you press.',18,'#ffd166')
            for n,row in enumerate(model.buttons):
                x=16+(n%3)*208; y=117+(n//3)*46
                status='NOT AVAILABLE' if not model.available(row) else 'RELEASE FIRST' if row['needs_release'] else 'PRESSED - RELEASE' if row['down'] else 'DETECTED' if row['cycles'] else 'WAITING'
                color='#627187' if not model.available(row) else '#ffd166' if row['down'] else '#63e6b0' if row['cycles'] else '#8b9bb0'
                d.rounded_rectangle((x,y,x+192,y+40),radius=6,fill='#203047',outline=color,width=2)
                text(x+9,y+2,row['label'],16)
                text(x+9,y+21,status,14,color)
            text(18,400,f'{model.count()} / 18 detected   |   Last: {model.last}',16)
            text(18,428,'Hold ONE included button for 3s: pause / finish',16)
            if hold>0:
                d.rectangle((18,451,18+int(min(1,hold)*604),456),fill='#ffd166')
        else:
            text(18,54,'PAUSED - take your time',20,'#63e6b0')
            text(18,91,'There is no countdown. Take your time.',18)
            text(18,124,'Tap any included button to change the selection.',18)
            text(18,151,'Hold for 2 seconds, then release to choose.',18)
            choices=['Resume checking','Save + finish: tested labels matched','Save + finish: mismatch or not sure']
            for n,label in enumerate(choices):
                y=202+n*52
                d.rounded_rectangle((18,y,622,y+43),radius=8,fill='#3b4a35' if nav.selection==n else '#203047',
                                    outline='#ffd166' if nav.selection==n else '#203047',width=2)
                text(32,y+9,label,18)
            if nav.key is not None:
                prompt='Release to choose.' if time.monotonic()-nav.since>=2 else 'Keep holding to choose, or release to move.'
                text(18,373,prompt,18,'#ffd166')
            else: text(18,373,'Menu presses are not counted as button tests.',16)
            text(18,411,f'{model.count()} / 18 detected. You can save a partial check.',16)
        if notice: text(18,445,notice,14,'#ffd166')
        text(18,461,'No timer. Start, Power and Reset are excluded.',14,'#9cacbf')
        self.sink.show(im)


class Stopped(Exception): pass


def save(folders,model,inputs,nav,raw,result,reason,history):
    import html
    errors=[]
    buttons=[dict(row,available=model.available(row)) for row in model.buttons]
    data=dict(version='button-baseline-4',session=reason,
              excluded=['Start','Power','Reset'],profile_source='RG35XX H device-tree key declarations',
              physical_labels_confirmation=result,
              complete= model.count()==18 and result=='matched',
              recognized_count=model.count(),required_count=18,buttons=buttons,
              devices=[d.identity for d in inputs.devices],navigation=nav.mode,history=history,
              monotonic_seconds=time.monotonic(),
              scope='Digital button press/release baseline only. Sticks analog motion, outputs and reliability are not tested.')
    try:
        raw.flush(); os.fsync(raw.fileno())
    except OSError as exc:
        errors.append('raw event log: '+str(exc))
    rows=''.join('<tr><td>'+html.escape(r['label'])+'</td><td>'+str(r['code'])+'</td><td>'+str(r['cycles'])+
                 '</td><td>'+('present' if model.available(r) else 'unavailable')+'</td></tr>' for r in model.buttons)
    page='<!doctype html><meta charset="utf-8"><title>GuideOS button baseline</title><style>body{font:18px system-ui;max-width:900px;margin:32px auto;padding:20px}td,th{padding:12px;border-bottom:1px solid #ccc;text-align:left}table{border-collapse:collapse}</style><h1>RG35XX H button baseline</h1>'
    page+='<p>'+html.escape(reason)+'</p><p>Detected: '+str(model.count())+' / 18. Physical labels: '+html.escape(result)+'.</p>'
    page+='<p>Start, Power and Reset are excluded. Missing events are not a diagnosis of broken hardware.</p><table><tr><th>Expected button</th><th>Linux code</th><th>Press/release cycles</th><th>Device</th></tr>'+rows+'</table>'
    page+='<p><a href="button-baseline.json">Structured evidence</a> · <a href="button-events.jsonl">Raw events</a></p>'
    for folder in folders:
        try:
            for name,body in [('button-baseline.json',json.dumps(data,indent=2)),('results.html',page)]:
                temp=folder/(name+'.tmp')
                with temp.open('w',encoding='utf-8') as out:
                    out.write(body); out.flush(); os.fsync(out.fileno())
                temp.replace(folder/name)
            if folder!=folders[0]:
                # Append only new raw evidence. Retry after a partial write starts
                # at the mirrored length; the source is never modified here.
                target=folder/'button-events.jsonl'
                offset=target.stat().st_size if target.exists() else 0
                with Path(raw.name).open('rb') as source, target.open('ab') as out:
                    source.seek(offset)
                    import shutil
                    shutil.copyfileobj(source,out)
                    out.flush(); os.fsync(out.fileno())
            fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except OSError as exc:
            errors.append(str(folder)+': '+str(exc))
    return errors


def run(folders):
    inputs=fb=model=None; nav=Navigation(); history=[]; result='not yet confirmed'; reason='running'
    errors=[]; exit_status=2
    with (folders[0]/'button-events.jsonl').open('w',buffering=1) as raw:
        log=EventLog(raw)
        try:
            inputs=hw.Inputs(log); model=Checklist(inputs.devices)
            fb=hw.Framebuffer(); display=Display(fb)
            generation=inputs.generation; recovering=set(); pending=False; last_save=0
            errors=save(folders,model,inputs,nav,raw,result,reason,history)
            while True:
                log.phase=nav.mode
                events=inputs.poll(.05); now=time.monotonic(); dirty=False
                # Drain queued input before interpreting a still-held menu gesture.
                drained=False
                for _ in range(16):
                    more=inputs.poll(0)
                    if not more: drained=True; break
                    events.extend(more)
                dropping={i for i,d in enumerate(inputs.devices) if d.connected and d.dropped}
                if inputs.generation!=generation or recovering!=dropping:
                    generation=inputs.generation; model.resync(); nav.interrupted(model)
                    history.append(dict(time=now,event='input state changed; pending cycles discarded',
                                        recovering_devices=sorted(dropping)))
                    dirty=True; events=[]
                recovering=dropping
                # Quarantine only the device recovering lost events. Other
                # buttons must remain usable even if it never sends SYN_REPORT.
                events=[event for event in events if event[0] not in recovering]
                events.sort(key=lambda event:event.timestamp)
                changed,actions=process(model,nav,events,now if drained else float('-inf'))
                for action in actions:
                    history.append(dict(time=now,event=action)); dirty=True
                finish=next((a for a in actions if a.startswith('finish_')),None)
                if finish:
                    result='matched' if finish=='finish_match' else 'mismatch or unsure'
                    reason='finished by user'
                    errors=save(folders,model,inputs,nav,raw,result,reason,history)
                    if not errors:
                        exit_status=0; break
                    history.append(dict(time=now,event='finish save failed',errors=errors))
                    nav.pause(model); reason='save failed; waiting for user retry'
                    result='not yet confirmed'
                pending |= changed or dirty
                if pending and (dirty or now-last_save>=1):
                    errors=save(folders,model,inputs,nav,raw,result,reason,history)
                    last_save=now; pending=bool(errors)
                    if errors: print('SAVE ERRORS: '+repr(errors),flush=True)
                hold=0
                if nav.mode=='check' and nav.held:
                    hold=(now-min(nav.held.values()))/3
                display.draw(model,nav,notice='Save failed - use pause menu to retry before shutdown.' if errors else '',hold=hold)
        except Stopped:
            reason='interrupted; partial results saved'
        except Exception as exc:
            reason='application error: '+repr(exc)
            raise
        finally:
            try:
                if model:
                    errors=save(folders,model,inputs,nav,raw,result,reason,history)
                    if errors:
                        exit_status=2; print('FINAL SAVE ERRORS: '+repr(errors),flush=True)
            finally:
                try:
                    if fb: fb.close()
                finally:
                    if inputs: inputs.close()
    return exit_status


def main():
    p=argparse.ArgumentParser(); p.add_argument('--report',type=Path); p.add_argument('--mirror',type=Path); p.add_argument('--preview',type=Path)
    args=p.parse_args()
    if args.preview:
        class Sink:
            def show(self,image): self.image=image
        class Dev:
            connected=True; keys={}; identity={}
            def __init__(self,name): self.name=name; self.caps={'1':[c for _,n,c in PROFILE if n==name]}
        model=Checklist([Dev(GAME),Dev(VOLUME)])
        model.consume([(0,1,305,1),(0,1,305,0),(0,1,304,1)])
        sink=Sink(); display=Display(sink); nav=Navigation(); args.preview.mkdir(parents=True,exist_ok=True)
        display.draw(model,nav); sink.image.save(args.preview/'check.png')
        nav.mode='menu'; display.draw(model,nav); sink.image.save(args.preview/'menu.png')
        return
    if not args.report or not args.mirror: p.error('report and mirror required')
    for folder in (args.report,args.mirror): folder.mkdir(parents=True,exist_ok=True)
    def stop(*_): raise Stopped()
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    return run([args.report,args.mirror])


if __name__=='__main__': raise SystemExit(main())
