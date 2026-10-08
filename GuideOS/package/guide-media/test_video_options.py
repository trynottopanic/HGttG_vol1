"""Track selection across the shell service, session manager and decoder adapter."""
import hashlib, os, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'guide-audio'),str(HERE.parent/'guide-ipc/python'),str(HERE.parent/'guide-ipc/generated')]
from media_player_service import Service
from media_session import Session, PAUSED, PLAYING
from mpv_video_adapter import MpvVideoAdapter

class Decoder:
    def __init__(self):
        self.calls=[];self.selected={'aid':1,'sid':'no'}
        self.inventory=[dict(type='audio',id=1,lang='eng'),dict(type='audio',id=7,title='Commentary'),
                        dict(type='sub',id=3,lang='eng'),dict(type='sub',id=8,title='${media-title}\nInjected')]
    def _drain(self):pass
    def _property(self,name,default=None):
        if name=='track-list':
            return [dict(t,selected=self.selected['aid' if t['type']=='audio' else 'sid']==t['id']) for t in self.inventory]
        return self.selected.get(name,default)
    def command(self,*args):
        self.calls.append(args)
        if args[0]=='set_property':self.selected[args[1]]=args[2]
        if args[0]=='get_property':return self.selected[args[1]]

class VideoOptionsTests(unittest.TestCase):
    def test_navigation_choose_and_back_preserve_playing_and_paused_states(self):
        session=self.service.manager.sessions[self.service.sid]
        for state in (PLAYING,PAUSED):
            with self.subTest(state=state):
                session.state=state;self.adapter.requested_play=state==PLAYING
                self.adapter.position_ms=12345;self.decoder.calls.clear()
                self.key('open');self.assertEqual(self.service.video_options.cursor,0)
                self.key('down');self.assertEqual(self.service.video_options.cursor,1)
                self.key('up');self.assertEqual(self.service.video_options.cursor,0)
                self.key('choose');self.assertEqual(self.service.video_options.view,'subtitle')
                self.key('down');self.key('choose');self.key('back');self.key('back')
                self.assertTrue(self.service.active());self.assertEqual(session.state,state)
                self.assertEqual(self.adapter.requested_play,state==PLAYING)
                self.assertEqual(self.adapter.position_ms,12345)
                self.assertIsNone(self.service.video_options.view)
                self.assertFalse(any(c[0] in ('seek','quit') or c[:2]==('set_property','pause') for c in self.decoder.calls))
    def setUp(self):
        self.decoder=Decoder();self.adapter=MpvVideoAdapter(self.decoder)
        self.service=Service();self.service.kind=2;self.service.sid=b'S'*16
        self.service.owner=SimpleNamespace(instance_id=hashlib.sha256(('shell:'+str(os.getpid())).encode()).hexdigest()[:32],generation=1)
        self.service.manager.sessions[self.service.sid]=Session(self.service.sid,self.service.owner.instance_id,1,b'M'*16,1,1,self.adapter,object(),state=PAUSED)
    def key(self,key):return self.service.command(os.getpid(),dict(action='video-options',key=key))
    def test_two_options_subtitle_selection_none_and_audio_switch(self):
        result=self.key('open');self.assertEqual(result['options_view'],'options')
        self.assertIn('Subtitle track',self.decoder.calls[-1][2]);self.assertIn('Audio track',self.decoder.calls[-1][2])
        self.key('choose');self.assertIn('None [selected]',self.decoder.calls[-1][2])
        self.key('down');self.key('choose');self.assertEqual(self.decoder.selected['sid'],3)
        self.assertEqual(self.service.manager.sessions[self.service.sid].revision,2)
        self.key('up');self.key('choose');self.assertEqual(self.decoder.selected['sid'],'no')
        self.key('back');self.key('down');self.key('choose');self.key('down');self.key('choose')
        self.assertEqual(self.decoder.selected['aid'],7)
        self.assertEqual(self.service.status()['state'],'paused')
        self.key('back');self.key('back');self.assertIsNone(self.service.status()['options_view'])
        self.assertFalse(any(call[0]=='seek' for call in self.decoder.calls))
    def test_no_tracks_and_unavailable_selection_preserve_session(self):
        self.decoder.inventory=[];self.key('open');self.key('choose')
        self.assertEqual(self.service.video_options.rows(),[(None,'None')])
        self.key('back');self.key('down');self.key('choose');self.key('choose')
        self.assertIn('No audio tracks available',self.decoder.calls[-1][2])
        self.assertTrue(self.service.active())
        self.decoder.inventory=[dict(type='audio',id=1)]
        self.key('close');self.key('open');self.key('down');self.key('choose')
        self.decoder.inventory=[];self.key('choose')
        self.assertIn('unavailable',self.decoder.calls[-1][2])
        self.assertTrue(self.service.active())
    def test_inventory_ids_are_private_and_stale_ids_rejected(self):
        inventory=self.adapter.tracks();identity=inventory['audio'][1]['id']
        self.assertEqual(len(identity),16);self.assertEqual(identity,self.adapter.tracks()['audio'][1]['id'])
        self.decoder.inventory=[t for t in self.decoder.inventory if t['id']!=7]
        with self.assertRaises(ValueError):self.adapter.select_audio(identity)
        self.assertEqual(self.decoder.selected['aid'],1)
    def test_track_titles_are_literal_and_owner_is_checked(self):
        self.key('open');self.key('choose')
        command=self.decoder.calls[-1]
        self.assertEqual(command[:2],('raw','show-text'))
        self.assertIn('${media-title}Injected',command[2])
        with self.assertRaises(PermissionError):self.service.command(os.getpid()+1,dict(action='video-options',key='choose'))
    def test_unconfirmed_selection_does_not_update_session_revision(self):
        self.key('open');self.key('down');self.key('choose');self.key('down')
        original=self.decoder.command
        def failed(*args):
            if args[:2]==('get_property','aid'):return 1
            return original(*args)
        with patch.object(self.decoder,'command',failed):self.key('choose')
        self.assertEqual(self.service.manager.sessions[self.service.sid].revision,1)
        self.assertIn('unavailable',self.decoder.calls[-1][2])

if __name__=='__main__':unittest.main()
