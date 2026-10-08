"""Browser adapter for the shared Guide editor, renderer and stick controls."""
from pathlib import Path
import sys
path=Path(__file__).resolve().parent.parent/'input'
if not (path/'guide_keyboard.py').is_file():path=Path('/usr/lib/guideos/input')
if not path.is_dir():path=Path(__file__).resolve().parents[3]/'package/guide-input'
sys.path.insert(0,str(path))
from guide_keyboard import Keyboard
from guide_keyboard_view import KeyboardRenderer
from guide_text_entry import TextEntryManager,TextRequest
from guide_stick_input import StickController


class NativeKeyboard:
    def __init__(self,target,initial=''):
        if target not in ('address','page'):raise ValueError('Unknown keyboard destination')
        self.target=target
        self.last_sequence = -1
        self.manager=TextEntryManager()
        self.keyboard=Keyboard(self.manager,TextRequest(owner_id='guide-browser',field_id=target,
            label='Web address' if target=='address' else 'Selected web field (masked)',
            initial=initial,purpose='url' if target=='address' else 'text',secret=target=='page',
            multiline=target=='page',max_length=4096,max_bytes=16384,
            submit_label='Go' if target=='address' else 'Insert'))
        self.renderer=KeyboardRenderer(application_label='Web browser')
        self.sticks=StickController(self.keyboard)

    @property
    def token(self):return self.keyboard.session.token

    def input(self,events):
        if not isinstance(events,list) or len(events)>32:raise ValueError('Too many keyboard events')
        actions={544:'up',545:'down',546:'left',547:'right',305:'activate',304:'cancel',
                 307:'space',308:'backspace',317:'case',318:'activate',310:'previous-layer',311:'next-layer'}
        changed=False
        for event in events:
            if not isinstance(event,dict):raise ValueError('Invalid keyboard event')
            if 'sticks' in event:
                value=event['sticks']
                if not isinstance(value,dict) or set(value)-{'left','right','generation','right_click'}:raise ValueError('Invalid sticks')
                for name in ('left','right'):
                    position=value.get(name)
                    if position is not None and (not isinstance(position,(tuple,list)) or len(position)!=2 or
                        any(type(part) not in (int,float) or not -1<=part<=1 for part in position)):raise ValueError('Invalid stick position')
                generation=value.get('generation',0)
                if type(generation) is not int or not 0<=generation<=2**53:raise ValueError('Invalid input generation')
                changed=self.sticks.update(left=value.get('left'),right=value.get('right'),generation=generation) or changed
            else:
                code,value=event.get('code'),event.get('value')
                if type(code) is not int or type(value) is not int or value not in (0,1,2):raise ValueError('Invalid button')
                if code in actions:
                    changed=self.keyboard.handle(actions[code],value) or changed
                    if value==1 and code in (318,317,310,311):self.sticks.reset()
        return changed

    def close(self):self.keyboard.close();self.manager.teardown()
