"""Rendered Deck controls must invoke their semantic actions and return safely."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import guide_shell as shell
from guide_field_ui import field_model
from guide_files_panel import FilesPanel
from guide_media_panel import MediaPanel
from guide_operations_frontend import OperationsPages
from guide_transfers_panel import TransfersPanel
from guide_updates_panel import UpdatesPanel
from guide_v3_ui import V3UI, HomeState, SETTINGS

ROOT=Path(__file__).resolve().parents[4]


class DeckControlTests(unittest.TestCase):
    def setUp(self):
        self.ui=V3UI()
        self.transfer_calls=[]
        with patch.multiple(shell,AUDIO_ENABLED=False,WIFI_CONTROL_ENABLED=False,
                            STORAGE_ENABLED=False,OPERATIONS_ENABLED=False):
            self.state=shell.ShellState()
        self.addCleanup(self.state.text_entries.teardown)
        self.addCleanup(self.state.nodes_panel.worker.shutdown, wait=True)
        self.media=MediaPanel('/nonexistent')
        self.media.request=lambda request:dict(state='stopped',position=0,video=False)
        self.addCleanup(self.media.close)
        self.state.audio_panel=self.media
        self.files=FilesPanel(lambda op,args:{})
        def transfer(op,**args):
            self.transfer_calls.append((op,args))
            return dict(id='job',name=args.get('name',''),state='selecting',bytes=0,total=None)
        self.transfers=TransfersPanel(transfer)
        self.state.operations=OperationsPages(UpdatesPanel(lambda op,**args:{}),self.transfers,self.files)
        self.addCleanup(self.state.operations.close)
        self.state.schema_target_provider=lambda:self.layout().regions

    def model(self):
        s=self.state
        if s.page=='settings':return self.ui.settings_model(s)
        if s.page in s.operations.pages:return s.operations.model()
        return field_model(s)

    def layout(self):return self.ui.render(self.model())

    def details(self,name='A very long recording title — Part 02.flac',kind='file'):
        f=self.files;s=self.state
        f.location='external';f.path=['Guide','Media','Albums'];f.folder='folder-token'
        entry=dict(id='f'*32,name=name,kind=kind,size=1234)
        f.listing=dict(items=[entry],next=None)
        f.show_details(entry,now=0);f.details_progress=1
        s.page='files';s.operations.current='files'
        return entry

    def test_settings_explanations_fit_below_headings(self):
        s=self.state;s.page='settings'
        for index,(identity,heading,detail) in enumerate(SETTINGS):
            with self.subTest(setting=identity):
                s.settings_selection=index
                layout=self.layout()
                region=next(r for r in layout.regions if r.identity=='settings:'+identity)
                self.assertLessEqual(region.rect.bottom,480)
                self.assertEqual(region.action,'v3-setting')
                self.assertEqual(region.value,identity)
                self.assertLessEqual(len(self.ui.text.lines(detail,16,265)),2)
                self.assertGreater(layout.image.crop((region.rect.left+12,region.rect.top+34,
                                                      region.rect.right-12,region.rect.bottom-6)).convert('L').getextrema()[1],100)

    def test_all_settings_cards_open_and_return(self):
        s=self.state
        s.wifi_panel=SimpleNamespace(view='list',key=lambda code:'home',editor=None)
        s.storage_panel=SimpleNamespace(rows=lambda:[])
        routes=('audio','wifi','storage','power','updates','diagnostics','about')
        for index,((identity,_,_),destination) in enumerate(zip(SETTINGS,routes)):
            with self.subTest(setting=identity):
                s.page='settings';s.navigation_stack=[];s.settings_selection=index
                self.assertTrue(s.menu_input.activate('settings:'+identity))
                self.assertEqual(s.page,destination)
                self.assertTrue(s.key(shell.B,1))
                self.assertEqual(s.page,'settings')

    def test_missing_settings_provider_explains_unavailability(self):
        s=self.state;s.page='settings';s.audio_panel=None
        self.assertTrue(s.menu_input.activate('settings:audio'))
        self.assertEqual(s.page,'unavailable')
        self.assertIn('not installed',s.unavailable_message)
        self.assertTrue(s.menu_input.activate('back'))
        self.assertEqual(s.page,'settings')

    def test_home_destinations_have_existing_routes(self):
        s=self.state
        s.storage_panel=SimpleNamespace(rows=lambda:[])
        routes={'files':'files','applications':'installer','settings':'settings',
                'browser':'browser','storage':'storage','media':'media','nodes':'nodes'}
        with patch.object(shell,'BROWSER_ENABLED',True),patch.object(s,'open_installer'),patch.object(s.nodes_panel,'scan'):
            for destination,page in routes.items():
                with self.subTest(destination=destination):
                    s.page='home';s.navigation_stack=[]
                    self.assertTrue(s.open_v3_destination(destination))
                    self.assertEqual(s.page,page)

    def test_nodes_rendered_focus_dispatches_each_enabled_row(self):
        s=self.state;p=s.nodes_panel;s.page='nodes'
        with patch.object(p,'action') as action:
            for view,trusted in [('list',False),('pair',False),('session',False),('session',True)]:
                p.view=view;p.trust_known=True;p.trusted=trusted
                p.nodes=[('0','Desktop Node')];p.capabilities=['Media streaming']
                for index,row in enumerate(p.model().items):
                    if not row.enabled:continue
                    with self.subTest(view=view,identity=row.identity,trusted=trusted):
                        p.cursor=index
                        self.assertEqual(s.menu_input.focus_target().identity,row.identity)
                        self.assertTrue(s.key(shell.A,1))
                        action.assert_called_with(row.value)
                        self.assertEqual(s.page,'nodes')

    def test_nodes_dpad_then_a_and_disabled_focus_do_not_go_home(self):
        s=self.state;p=s.nodes_panel;s.page='nodes'
        p.view='session';p.trust_known=True;p.trusted=False;p.capabilities=['Media streaming']
        with patch.object(p,'action') as action:
            self.assertEqual(s.menu_input.focus_target().identity,'nodes:status')
            s.key(545,1)
            self.assertEqual(s.menu_input.focus_target().identity,'nodes:trust')
            s.key(shell.A,1);action.assert_called_once_with('trust')
            p.cursor=len(p.model().items)-1
            self.assertIsNone(s.menu_input.focus_target())
            s.key(shell.A,1)
            self.assertEqual(s.page,'nodes')
            self.assertTrue(s.key(shell.B,1));self.assertEqual(s.page,'home')

    def test_node_trust_refresh_preserves_worker_and_pending_request(self):
        p=self.state.nodes_panel;worker=p.worker;pending=object()
        p.pending=pending;p.pending_verb='status'
        with patch('guide_nodes_panel.Path.stat',side_effect=FileNotFoundError):
            p.refresh_trust();p.refresh_trust()
        self.assertIs(p.worker,worker);self.assertIs(p.pending,pending)
        self.assertEqual(p.pending_verb,'status')

    def test_media_categories_refresh_and_page_controls_dispatch(self):
        s=self.state;s.page='media';self.media.view='library'
        self.assertTrue(s.menu_input.activate('audio:music'))
        self.assertEqual(self.media.view,'music')
        self.assertEqual(list(self.media.tasks)[-1]['kind'],1)
        self.media.items=[dict(id='a',title='Long recording.flac',kind=1,generation=1)]
        self.media.more=True
        self.assertTrue(s.menu_input.activate('audio:next-media'))
        self.assertEqual(list(self.media.tasks)[-1]['after'],'a')
        self.assertTrue(s.menu_input.activate('audio:first-media'))
        self.assertIsNone(list(self.media.tasks)[-1]['after'])
        self.assertTrue(s.menu_input.activate('audio:refresh-media'))
        self.assertEqual(list(self.media.tasks)[-1]['action'],'list')
        self.assertTrue(s.key(shell.B,1))
        self.assertEqual(self.media.view,'library')
        self.assertTrue(s.menu_input.activate('audio:video'))
        self.assertEqual(list(self.media.tasks)[-1]['kind'],2)

    def test_power_cancel_and_confirm_only_change_requested_state(self):
        s=self.state;s.page='settings';s.open_v3_setting('power')
        self.assertFalse(s.shutdown_requested)
        self.assertTrue(s.menu_input.activate('power:cancel'))
        self.assertEqual(s.page,'settings')
        s.open_v3_setting('power')
        self.assertTrue(s.menu_input.activate('power:confirm'))
        self.assertTrue(s.shutdown_requested)

    def test_details_three_actions_are_reachable_by_controller(self):
        self.details()
        s=self.state
        self.assertEqual({r.identity for r in self.layout().regions},
                         {'back','play','copy','more-details'})
        self.assertEqual(s.menu_input.focus_target().identity,'play')
        s.key(547,1);self.assertEqual(s.menu_input.focus_target().identity,'copy')
        s.key(547,1);self.assertEqual(s.menu_input.focus_target().identity,'more-details')
        self.assertTrue(s.key(shell.A,1))
        self.assertEqual(self.files.view,'details-more')
        self.assertEqual(s.menu_input.focus_target().identity,'summary')
        self.assertTrue(s.key(shell.A,1))
        self.assertEqual(self.files.view,'details')
        self.assertEqual(s.operations.model().focus_id,'more-details')

    def test_on_screen_back_returns_to_selected_file(self):
        entry=self.details()
        self.assertTrue(self.state.menu_input.activate('back'))
        self.assertEqual(self.files.view,'folder')
        self.assertEqual(self.state.operations.model().focus_id,entry['id'])

    def test_copy_passes_opaque_source_to_transfer_service(self):
        entry=self.details()
        self.assertTrue(self.state.menu_input.activate('copy'))
        self.assertEqual(self.state.page,'transfers')
        self.transfers.future.result(timeout=2)
        self.assertEqual(self.transfer_calls[0],('offer',dict(source={'entry':entry['id']},name=entry['name'])))

    def test_play_uses_catalogue_request_and_returns_to_files(self):
        entry=self.details()
        self.assertTrue(self.state.menu_input.activate('play'))
        self.assertEqual(self.state.page,'media')
        self.assertEqual(self.media.desired,dict(kind=1,title=entry['name'],folder='Albums'))
        self.assertEqual(list(self.media.tasks)[-1]['action'],'list')
        self.assertTrue(self.state.key(shell.B,1))
        self.assertEqual(self.state.page,'files')
        self.assertEqual(self.state.operations.model().focus_id,entry['id'])

    def test_unsupported_play_and_folder_copy_are_disabled(self):
        for name,kind,disabled in [('readme.txt','file',{'play'}),('Albums','folder',{'play','copy'})]:
            with self.subTest(name=name):
                self.details(name,kind)
                targets={r.identity for r in self.layout().regions}
                self.assertFalse(targets & disabled)
                for identity in disabled:self.assertFalse(self.state.menu_input.activate(identity))
        self.details();self.files.media_available=False
        self.assertNotIn('play',{r.identity for r in self.layout().regions})
        self.assertIn('not installed',self.model().notice)

    def player(self,index=1):
        self.media.items=[dict(id=str(i),kind=1,title='Track '+str(i),generation=1) for i in range(3)]
        self.media.current=self.media.items[index]
        self.media.view='player';self.media.cursor=1;self.media.playback={'state':'playing'}
        self.state.page='media'

    def test_player_transport_and_playlist_boundaries(self):
        self.player(0)
        self.assertNotIn('audio:media-previous',{r.identity for r in self.layout().regions})
        self.assertTrue(self.state.menu_input.activate('audio:media-next'))
        self.assertEqual(self.media.current,self.media.items[1])
        self.assertTrue(self.state.menu_input.activate('audio:media-previous'))
        self.assertEqual(self.media.current,self.media.items[0])
        self.player(2)
        self.assertNotIn('audio:media-next',{r.identity for r in self.layout().regions})
        self.assertFalse(self.state.menu_input.activate('audio:media-next'))

    def test_player_back_matches_physical_b(self):
        self.player();self.media.view_stack=[('music',2)]
        self.assertTrue(self.state.menu_input.activate('back'))
        self.assertEqual((self.media.view,self.media.cursor),('music',2))
        self.assertEqual(self.state.page,'media')
        self.assertFalse(any(r['action']=='stop' for r in self.media.tasks))

    def test_a_controls_pause_and_resume_independently_of_focus(self):
        self.player();self.media.cursor=0
        self.assertTrue(self.state.key(shell.A,1))
        self.assertEqual(list(self.media.tasks)[-1]['action'],'pause')
        self.media.playback={'state':'paused'}
        self.assertTrue(self.state.key(shell.A,1))
        self.assertEqual(list(self.media.tasks)[-1]['action'],'resume')

    def test_home_keeps_installed_art_except_authorized_world_entry(self):
        path=ROOT/'build/release-0.4.2.03/candidate/release-source/shell0/guide_v3_ui.py'
        spec=importlib.util.spec_from_file_location('installed_deck_v3',path)
        installed=importlib.util.module_from_spec(spec);sys.modules[spec.name]=installed
        spec.loader.exec_module(installed)
        old=installed.V3UI()
        for frame in (0,225,450):
            for tray in (False,True):
                state=SimpleNamespace(v3_home=HomeState(tray_active=tray,planet_frame=frame))
                actual=self.ui.render_home(state,now=0);expected=old.render_home(state,now=0)
                # The only idle visual edit is the world's actionable caption.
                actual.image.paste(expected.image.crop((16,334,369,364)),(16,334))
                self.assertEqual(actual.image.tobytes(),expected.image.tobytes())
                self.assertEqual(tuple(r for r in actual.regions if r.identity!='v3-world'),expected.regions)
                self.assertEqual(next(r for r in actual.regions if r.identity=='v3-world').value,'planegotchi')

    def test_home_pending_update_keeps_normal_a(self):
        s=self.state;s.page='home';s.update_notice_id='candidate'
        self.assertEqual(self.ui.render_home(s,now=0).image.size,(640,480))
        self.assertTrue(s.key(shell.A,1))
        self.assertEqual(s.update_notice_id,'candidate')


if __name__=='__main__':unittest.main()
