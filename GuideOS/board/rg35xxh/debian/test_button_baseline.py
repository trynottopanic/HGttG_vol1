#!/usr/bin/python3
"""Behavioral checks for the untimed baseline, without physical input devices."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('button-baseline.py'))
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


class Device:
    connected=True; dropped=False
    def __init__(self,name,held=()):
        self.name=name; self.keys=dict.fromkeys(held,1); self.identity={'name':name}
        self.caps={'1':[c for _,n,c in b.PROFILE if n==name]}


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.devices=[Device(b.GAME),Device(b.VOLUME)]
        self.model=b.Checklist(self.devices); self.nav=b.Navigation()

    def event(self,code,value,stamp,device=0):
        return b.hw.TimedEvent((device,1,code,value),stamp)

    def batch(self,*events,now=None):
        return b.process(self.model,self.nav,events,events[-1].timestamp if now is None else now)

    def tap(self,code=305,at=10,device=0):
        return self.batch(self.event(code,1,at,device),self.event(code,0,at+.1,device))

    def hold(self,code=305,at=10,seconds=3.1,device=0):
        return self.batch(self.event(code,1,at,device),self.event(code,0,at+seconds,device))

    def test_all_buttons_any_order_and_exclusions(self):
        for _,name,code in reversed(b.PROFILE): self.tap(code,device=int(name==b.VOLUME))
        self.assertEqual(self.model.count(),18)
        for code in b.EXCLUDED: self.hold(code)
        self.assertEqual(self.nav.mode,'check')
        self.assertFalse(b.EXCLUDED.intersection(c for _,c in self.model.lookup))

    def test_initially_held_requires_new_cycle(self):
        self.devices[0].keys[305]=1; self.model=b.Checklist(self.devices)
        self.batch(self.event(305,1,10),self.event(305,0,11))
        self.assertEqual(self.model.count(),0)
        self.tap(); self.assertEqual(self.model.count(),1)

    def test_repeats_duplicate_presses_and_stray_release(self):
        events=[self.event(305,v,10+i*.1) for i,v in enumerate([0,1,1,2,0,0,1,0])]
        self.batch(*events)
        self.assertEqual(self.model.lookup[0,305]['cycles'],2)
        self.assertEqual(self.model.lookup[0,305]['presses'],2)

    def test_wrong_device_and_unknown_codes_cannot_pass(self):
        self.tap(305,device=1); self.tap(999)
        self.assertEqual(self.model.count(),0)

    def test_missing_button_never_passes(self):
        self.devices[0].caps['1'].remove(305); self.model=b.Checklist(self.devices)
        self.tap(); self.assertEqual(self.model.count(),0)
        self.assertFalse(self.model.available(self.model.buttons[0]))

    def test_queued_long_hold_opens_menu_without_credit(self):
        changed,actions=self.hold()
        self.assertFalse(changed); self.assertEqual(actions,['pause'])
        self.assertEqual(self.model.count(),0)
        self.assertEqual(self.nav.selection,0)

    def test_live_hold_waits_for_release_without_advancing_menu(self):
        self.batch(self.event(305,1,10),now=13.2)
        self.assertEqual(self.nav.mode,'menu')
        self.batch(self.event(305,0,15))
        self.assertEqual(self.nav.selection,0)
        self.assertEqual(self.model.count(),0)

    def test_menu_never_credits_and_finish_only_on_release(self):
        self.hold(); self.tap(at=20)
        self.assertEqual(self.nav.selection,1)
        self.batch(self.event(305,1,21),now=100)
        self.assertEqual(self.nav.mode,'menu')
        changed,actions=self.batch(self.event(305,0,101))
        self.assertEqual(actions,['finish_match']); self.assertFalse(changed)
        self.assertEqual(self.model.count(),0)

    def test_default_resume_does_not_credit_menu_hold(self):
        self.hold(); self.hold(at=20,seconds=2.1)
        self.assertEqual(self.nav.mode,'check'); self.assertEqual(self.model.count(),0)
        self.tap(at=30); self.assertEqual(self.model.count(),1)

    def test_stuck_key_does_not_block_other_key_navigation(self):
        self.devices[0].keys[305]=1; self.model=b.Checklist(self.devices)
        self.hold(114,device=1)
        self.tap(114,at=20,device=1)
        _,actions=self.hold(114,at=30,seconds=2.1,device=1)
        self.assertEqual(actions,['finish_match'])
        self.assertEqual(self.model.count(),0)

    def test_only_volume_device_can_still_finish_partial(self):
        self.devices[0].connected=False
        self.hold(115,device=1); self.tap(115,at=20,device=1); self.tap(115,at=21,device=1)
        _,actions=self.hold(115,at=22,seconds=2.1,device=1)
        self.assertEqual(actions,['finish_uncertain'])

    def test_chord_during_menu_requires_fresh_gesture(self):
        self.hold()
        self.batch(self.event(305,1,20),self.event(304,1,20.1),self.event(305,0,23),self.event(304,0,24))
        self.assertEqual(self.nav.mode,'menu'); self.assertEqual(self.nav.selection,0)
        self.tap(at=30); self.assertEqual(self.nav.selection,1)

    def test_interruption_preserves_completed_discards_pending(self):
        self.tap(304)
        self.batch(self.event(305,1,20)); self.devices[0].keys[305]=1
        self.model.resync(); self.nav.interrupted(self.model)
        self.batch(self.event(305,0,30))
        self.assertEqual(self.model.count(),1)
        self.assertEqual(self.model.lookup[0,305]['cycles'],0)
        self.assertEqual(self.nav.selection,0)

    def test_disconnected_device_cannot_navigate_or_count(self):
        self.devices[0].connected=False; self.hold()
        self.assertEqual(self.nav.mode,'check'); self.assertEqual(self.model.count(),0)

    def test_no_automatic_timeout_or_completion(self):
        for _,name,code in b.PROFILE: self.tap(code,device=int(name==b.VOLUME))
        b.process(self.model,self.nav,[],10**8)
        self.assertEqual(self.nav.mode,'check')

    def test_reports_require_both_evidence_and_human_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            folders=[Path(td)/'data',Path(td)/'boot']
            for folder in folders: folder.mkdir()
            inputs=type('Inputs',(),{'devices':self.devices})()
            with (folders[0]/'button-events.jsonl').open('w') as raw:
                raw.write('{"evidence":1}\n')
                self.assertEqual(b.save(folders,self.model,inputs,self.nav,raw,'matched','partial',[]),[])
                self.assertFalse(json.loads((folders[0]/'button-baseline.json').read_text())['complete'])
                for _,name,code in b.PROFILE: self.tap(code,device=int(name==b.VOLUME))
                b.save(folders,self.model,inputs,self.nav,raw,'not yet confirmed','running',[])
                self.assertFalse(json.loads((folders[0]/'button-baseline.json').read_text())['complete'])
                raw.write('{"evidence":2}\n')
                b.save(folders,self.model,inputs,self.nav,raw,'matched','finished by user',[])
                self.assertTrue(json.loads((folders[0]/'button-baseline.json').read_text())['complete'])
            self.assertEqual((folders[0]/'button-events.jsonl').read_bytes(),(folders[1]/'button-events.jsonl').read_bytes())

    def test_failed_mirror_does_not_discard_primary_report(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td); missing=folder/'missing'; inputs=type('Inputs',(),{'devices':self.devices})()
            with (folder/'button-events.jsonl').open('w') as raw:
                errors=b.save([folder,missing],self.model,inputs,self.nav,raw,'not yet confirmed','running',[])
            self.assertTrue(errors); self.assertTrue((folder/'button-baseline.json').exists())

    def test_session_can_finish_through_volume_while_gamepad_loses_events(self):
        # Exercise the actual run loop, including recovery and report saves.
        # A recovering device may never send SYN_REPORT, or disconnect first.
        for disconnect in (False,True):
            with self.subTest(disconnect=disconnect), tempfile.TemporaryDirectory() as td:
                folders=[Path(td)/'data',Path(td)/'boot']
                for folder in folders: folder.mkdir()
                game=Device(b.GAME); volume=Device(b.VOLUME)
                owner=self
                class Input:
                    devices=[game,volume]; generation=0; step=0; closed=False
                    def poll(self,delay):
                        if delay==0: return []
                        self.step+=1
                        if self.step==1:
                            game.dropped=True; self.generation+=1
                            return []
                        if self.step==2:
                            if disconnect:
                                game.connected=False; self.generation+=1
                            return []
                        if self.step==3:
                            return [owner.event(115,1,20,1),owner.event(115,0,20.1,1)]
                        if self.step==4:
                            return [owner.event(115,1,21,1),owner.event(115,0,23.1,1)]
                        raise AssertionError('Working volume key could not finish the paused session')
                    def close(self): self.closed=True
                class FB:
                    def close(self): pass
                class UI:
                    def draw(self,*args,**kwargs): pass
                inputs=Input()
                with patch.object(b.hw,'Inputs',return_value=inputs), patch.object(b.hw,'Framebuffer',return_value=FB()), patch.object(b,'Display',return_value=UI()):
                    self.assertEqual(b.run(folders),0)
                self.assertTrue(inputs.closed)
                report=json.loads((folders[0]/'button-baseline.json').read_text())
                self.assertEqual(report['session'],'finished by user')
                self.assertFalse(report['complete'])
                self.assertEqual(report['recognized_count'],0)


if __name__=='__main__': unittest.main()
