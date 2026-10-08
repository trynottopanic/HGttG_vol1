import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import guide_nearby as nearby


class Commands(unittest.TestCase):
    def test_scan_preserves_literal_target_without_shell_or_scripts(self):
        for profile in ('ports','services'):
            args,limit=nearby.command_for(profile,'127.0.0.1')
            self.assertEqual(args[-1],'127.0.0.1')
            self.assertIn('-sT',args); self.assertIn('--unprivileged',args)
            self.assertNotIn('--script',args); self.assertNotIn('-A',args)
            self.assertLessEqual(limit,40)
        args,_=nearby.command_for('ports','::1'); self.assertIn('-6',args)

    def test_invalid_options_ranges_and_shell_fragments_are_rejected(self):
        for value in ('-oN/tmp/file','127.0.0.1;echo hi','192.168.1.0/24','192.168.1.1-255','example.com'):
            with self.assertRaises(ValueError): nearby.command_for('ports',value)
        for value in ('-x','foo..bar','a'*64+'.com','name;cmd'):
            with self.assertRaises(ValueError): nearby.command_for('dns',value)
        self.assertEqual(nearby.command_for('dns','example.com')[0][-1],'example.com')
        self.assertIn('-x',nearby.command_for('dns','127.0.0.1')[0])

    def test_nmap_closed_filtered_and_reported_services(self):
        raw=b'''<?xml version="1.0"?><!DOCTYPE nmaprun><nmaprun><host><ports>
        <extraports state="closed" count="48"/><port protocol="tcp" portid="80"><state state="open"/>
        <service name="http" product="example" version="1.0"/></port><port protocol="tcp" portid="22">
        <state state="filtered"/></port></ports></host><runstats><finished exit="success"/></runstats></nmaprun>'''
        result=nearby.nmap_result(raw)
        self.assertEqual(result['ports'][0]['reported'],'example 1.0')
        self.assertEqual(result['ports'][1]['state'],'filtered')
        self.assertEqual(result['summary'][0]['count'],48)
        self.assertIn('48 ports closed',result['lines'])
        with self.assertRaises(ValueError): nearby.nmap_result(b'<nmaprun><runstats><finished exit="error"/></runstats></nmaprun>')

    def test_cancel_terminates_real_child_and_returns_promptly(self):
        import sys
        started=threading.Event(); cancelled=threading.Event(); children=[]; errors=[]
        def spawn(*args,**kwargs):
            child=nearby.subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs)
            children.append(child); started.set(); return child
        def work():
            try: nearby.run_tool('ping','127.0.0.1',cancelled,spawn)
            except InterruptedError: errors.append('cancelled')
        worker=threading.Thread(target=work); worker.start(); self.assertTrue(started.wait(2))
        cancelled.set(); worker.join(2)
        self.assertFalse(worker.is_alive()); self.assertIsNotNone(children[0].poll()); self.assertEqual(errors,['cancelled'])


class FakeRadios:
    closed=[]
    def __init__(self): self.bt_session=None
    def wifi(self,rescan=False):
        return [dict(id='wifi:ap',kind='wifi',name='AP',signal=75,seen=time.monotonic(),unit='%')],'observed'
    def bluetooth_start(self,power=False): self.bt_session='owned'; return 'Bluetooth discovery'
    def bluetooth(self): return []
    def close(self): self.closed.append(self.bt_session)


class Lifecycle(unittest.TestCase):
    def setUp(self): FakeRadios.closed=[]; self.provider=nearby.Provider(radios=FakeRadios)
    def tearDown(self): self.provider.close()
    def wait(self,predicate):
        until=time.monotonic()+2
        while time.monotonic()<until:
            if predicate(): return
            time.sleep(.01)
        self.fail('Job did not reach the expected state')

    def test_survey_to_watch_cancels_owned_session_and_keeps_selection(self):
        self.provider.command(dict(action='survey',kind='bluetooth'))
        self.wait(lambda:self.provider.snapshot()['message']=='Bluetooth discovery')
        self.provider.command(dict(action='watch',kind='wifi',id='wifi:ap'))
        self.wait(lambda:not self.provider.thread.is_alive())
        self.provider.tick()
        self.wait(lambda:bool(self.provider.snapshot()['history']))
        self.assertIn('owned',FakeRadios.closed)
        self.provider.command(dict(action='cancel')); self.wait(lambda:not self.provider.thread.is_alive())
        self.assertFalse(self.provider.snapshot()['busy'])

    def test_leave_cancels_deferred_tool_before_execution(self):
        calls=[]; self.provider.tool=lambda *args:calls.append(args)
        self.provider.command(dict(action='survey',kind='wifi'))
        self.provider.command(dict(action='tool',profile='ports',target='127.0.0.1'))
        self.provider.command(dict(action='cancel')); self.wait(lambda:not self.provider.thread.is_alive())
        self.provider.tick(); self.assertEqual(calls,[])

    def test_lost_ui_heartbeat_cancels_observation(self):
        self.provider.command(dict(action='survey',kind='wifi'))
        self.provider.last_contact=time.monotonic()-6; self.provider.tick()
        self.wait(lambda:not self.provider.thread.is_alive()); self.assertFalse(self.provider.snapshot()['busy'])


if __name__=='__main__': unittest.main()
