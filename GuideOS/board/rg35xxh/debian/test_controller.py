import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('controller',Path(__file__).with_name('controller-test.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class InputTests(unittest.TestCase):
    def test_excluded_controls_never_map_or_advance(self):
        trial=m.ButtonTrial()
        for code in m.EXCLUDED:
            trial.event((0,code),1,1); trial.event((0,code),0,2)
        self.assertIsNone(trial.mapping)
        self.assertFalse(trial.complete)
        trial.event((0,304),1,3); trial.event((0,304),0,4)
        self.assertTrue(trial.complete)

    def test_driver_code_is_learned_not_assumed(self):
        trial=m.ButtonTrial()
        trial.event((1,114),1,1)
        self.assertEqual(trial.mapping,(1,114))
        self.assertFalse(trial.complete)
        trial.event((1,114),0,2)
        self.assertTrue(trial.complete)

    def test_release_without_press_is_not_completion(self):
        trial=m.ButtonTrial()
        trial.event((0,304),0,1)
        self.assertFalse(trial.complete)

    def test_duplicate_mapping_is_ambiguous(self):
        trial=m.ButtonTrial(used=[(0,304)])
        trial.event((0,304),1,1)
        self.assertTrue(trial.ambiguous)

    def test_two_buttons_are_ambiguous(self):
        trial=m.ButtonTrial()
        trial.event((0,304),1,1); trial.event((0,305),1,1.1)
        self.assertTrue(trial.ambiguous)

    def test_hold_requires_duration_release_and_second_tap(self):
        trial=m.ButtonTrial((0,304),exercise=True)
        trial.event((0,304),1,1); trial.event((0,304),0,1.2)
        self.assertEqual(trial.state,0)
        trial.event((0,304),1,2); trial.event((0,304),2,2.2)
        self.assertFalse(trial.complete)
        trial.event((0,304),0,3.1)
        self.assertEqual(trial.state,1)
        trial.event((0,304),1,3.4)
        self.assertFalse(trial.complete)
        trial.event((0,304),0,3.6)
        self.assertTrue(trial.complete)

    def test_lost_events_are_discarded_until_resync(self):
        class Dev:
            fd=11; connected=True; dropped=False
            keys={}; axes={}; sw={}; resynced=False
            def resync(self): self.resynced=True
        inputs=m.Inputs.__new__(m.Inputs)
        d=Dev(); inputs.devices=[d]; inputs.generation=0; inputs.log=io.StringIO()
        raw=b''.join(m.EVENT.pack(0,0,*ev) for ev in [(0,3,0),(1,304,1),(0,0,0)])
        with patch.object(m.select,'select',return_value=([11],[],[])), patch.object(m.os,'read',return_value=raw):
            events=inputs.poll()
        self.assertEqual(events,[])
        self.assertTrue(d.resynced)
        self.assertEqual(inputs.generation,1)
        self.assertEqual(d.keys,{})

    def test_event_device_disconnect_invalidates_trial(self):
        class Dev:
            fd=11; connected=True
        inputs=m.Inputs.__new__(m.Inputs)
        inputs.devices=[Dev()]; inputs.generation=0; inputs.log=io.StringIO()
        with patch.object(m.select,'select',return_value=([11],[],[])), patch.object(m.os,'read',return_value=b''):
            self.assertEqual(inputs.poll(),[])
        self.assertFalse(inputs.devices[0].connected)
        self.assertEqual(inputs.generation,1)

    def test_saved_summary_is_valid_and_mirrored(self):
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as tmp:
            folders=[Path(tmp)/'a',Path(tmp)/'b']
            for p in folders: p.mkdir()
            class Inputs: devices=[]
            inputs=Inputs()
            with (folders[0]/'controller-events.jsonl').open('w') as log:
                inputs.log=log
                test=m.Test(inputs,None,folders)
                with patch.object(m.os,'sync'):
                    test.record('discover','A','complete',mapping=[0,305])
                a=(folders[0]/'controller-summary.json').read_bytes()
                self.assertEqual(a,(folders[1]/'controller-summary.json').read_bytes())
                self.assertEqual(json.loads(a)['results'][0]['mapping'],[0,305])


class GuidedWorkflowTests(unittest.TestCase):
    def setup_session(self,schedule):
        from types import SimpleNamespace
        clock=[0.0]
        dev=SimpleNamespace(keys={},axes={0:dict(value=0,minimum=-1800,maximum=1800,center=0,flat=32)},identity={})
        class Inputs:
            devices=[dev]; generation=0
            def poll(self):
                clock[0]+=.05
                emitted=[]
                while schedule and schedule[0][0]<=clock[0]:
                    _,kind,code,value=schedule.pop(0)
                    if kind==m.EV_KEY: dev.keys[code]=value
                    if kind==m.EV_ABS: dev.axes[code]['value']=value
                    emitted.append((0,kind,code,value))
                return emitted
            def released(self): return not any(v for c,v in dev.keys.items() if c not in m.EXCLUDED)
            def down(self,mapping): return bool(dev.keys.get(mapping[1]))
        screen=SimpleNamespace(remaining=480,completed=set(),draw=lambda *a,**k:None)
        test=m.Test(Inputs(),screen,[]); test.started=0; test.save=lambda:None
        return test,clock

    def test_guided_discovery_then_exercise(self):
        test,clock=self.setup_session([(0.8,1,305,1),(1.0,1,305,0),(1.2,1,305,1),(1.4,1,305,0),
                                      (3.0,1,305,1),(4.2,1,305,0),(4.5,1,305,1),(4.7,1,305,0)])
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertTrue(test.button('A'))
            self.assertEqual(test.mapping['A'],[0,305])
            self.assertTrue(test.button('A',True))
        self.assertEqual([r['outcome'] for r in test.results],['complete','complete'])

    def test_axis_discovery_requires_return_to_center(self):
        test,clock=self.setup_session([(0.8,3,0,-1800),(1.5,3,0,0)])
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            result=test.discover_axis('LEFT STICK','right')
        self.assertEqual(result['sign'],-1)
        self.assertGreaterEqual(clock[0],1.5)

    def test_combination_requires_overlap_and_independent_release(self):
        test,clock=self.setup_session([(0.8,1,310,1),(0.9,1,305,1),(1.1,1,305,0),(1.3,1,310,0)])
        test.mapping={'L1':[0,310],'A':[0,305]}
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]): test.combination('L1','A','L1 + A')
        self.assertEqual(test.results[-1]['outcome'],'complete')

    def test_timeout_is_not_a_hardware_failure(self):
        test,clock=self.setup_session([])
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertFalse(test.button('A'))
        self.assertEqual(test.results[-1]['outcome'],'not observed')

    def test_stuck_control_is_not_reused_for_next_prompt(self):
        test,clock=self.setup_session([(0.05,1,305,1)])
        with patch.object(m.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertFalse(test.button('A'))
        self.assertNotIn('A',test.mapping)
        self.assertEqual(test.results[-1]['reason'],'Controls not released')


if __name__=='__main__': unittest.main()
