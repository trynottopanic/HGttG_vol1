import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from guide_input import TextEntryManager
from guide_quick_find import QuickFind,search_names,FILES,APPS
from storage_files import Files

class ProviderSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);self.internal=base/'files';self.external=base/'card'
        self.external.mkdir();self.card='card-one'
        self.files=Files(self.external,self.internal,current=lambda:self.card)
        self.files.refresh(self.card,1);self.addCleanup(self.files.close)
        self.apps=[dict(name='Earth Atlas',code=10001,state='committed'),
                   dict(name='Earth removed',code=10002,state='uninstalled')]

    def client(self,path,op,args):
        if path==APPS:return dict(items=self.apps,next=None)
        result,fds=self.files.wire_dispatch(op,args)
        for fd in fds:os.close(fd)
        return result

    def test_unicode_nested_and_paginated_search_uses_provider_identities(self):
        nested=self.external/'GUIDE'/'MEDIA';nested.mkdir(parents=True)
        for i in range(40):(nested/f'item-{i:02}.txt').write_text('not searched')
        (nested/'ÉARTH.mp3').write_bytes(b'')
        result=search_names('e\u0301arth','external',threading.Event(),self.client)
        self.assertFalse(result['partial']);self.assertEqual(len(result['results']),1)
        match=result['results'][0]
        self.assertEqual(match['parts'],('GUIDE','MEDIA'))
        self.assertEqual(match['name'],'ÉARTH.mp3')
        self.assertEqual(self.client(FILES,3,{'entry':match['id']}),{'bytes':0})

    def test_owner_scope_does_not_follow_symlinks_or_search_file_contents(self):
        secret=Path(self.temp.name)/'Earth-private.txt';secret.write_text('secret')
        (self.internal/'outside').symlink_to(Path(self.temp.name),target_is_directory=True)
        (self.internal/'ordinary.txt').write_text('Earth only in contents')
        (self.external/'Earth-card.txt').write_text('')
        result=search_names('Earth','internal',threading.Event(),self.client)
        self.assertEqual(result['results'],[])

    def test_removed_app_is_excluded_and_apps_scope_never_reads_files(self):
        def client(path,op,args):
            self.assertEqual(path,APPS);return dict(items=self.apps,next=None)
        matches=search_names('EARTH','apps',threading.Event(),client)['results']
        self.assertEqual([r['code'] for r in matches],[10001])

    def test_result_budget_is_bounded_and_reported(self):
        for i in range(90):(self.internal/f'Earth-{i:02}.txt').write_text('')
        result=search_names('Earth','internal',threading.Event(),self.client)
        self.assertEqual(len(result['results']),64);self.assertTrue(result['partial'])

    def test_listing_revision_change_reports_incomplete_results(self):
        def client(path,op,args):
            if op==1:return dict(locations=[dict(id='internal',available=True,name='Internal')])
            offset=args['offset']
            return dict(items=[],revision='a'*64 if offset==0 else 'b'*64,next=32 if offset==0 else None)
        self.assertTrue(search_names('Earth','internal',threading.Event(),client)['partial'])

    def test_removed_card_does_not_claim_a_complete_empty_search(self):
        self.card=None;self.files.refresh(None,2)
        result=search_names('Earth','external',threading.Event(),self.client)
        self.assertEqual(result['results'],[]);self.assertTrue(result['partial'])

    def test_cancel_and_deadline_stop_without_traversal(self):
        cancel=threading.Event();cancel.set()
        self.assertEqual(search_names('Earth','all',cancel,lambda *_:self.fail('Cancelled search made an RPC'))['results'],[])
        times=iter((0,21,21,21))
        result=search_names('Earth','internal',threading.Event(),lambda *_:self.fail('Expired search made an RPC'),clock=lambda:next(times,21))
        self.assertTrue(result['partial'])

    def test_changed_file_cannot_open_and_removal_invalidates_external_identity(self):
        path=self.external/'Earth.txt';path.write_text('old')
        row=search_names('Earth','external',threading.Event(),self.client)['results'][0]
        path.write_text('new content')
        self.assertIn('errorCode',self.client(FILES,3,{'entry':row['id']}))
        self.card=None;self.files.refresh(None,2)
        self.assertIn('errorCode',self.client(FILES,3,{'entry':row['id']}))

class PanelTests(unittest.TestCase):
    def setUp(self):
        self.manager=TextEntryManager();self.panel=QuickFind(self.manager,lambda path,op,args:dict(items=[],next=None,locations=[]))
        self.addCleanup(self.manager.teardown);self.addCleanup(self.panel.close)

    def settle(self):
        deadline=time.monotonic()+2
        while self.panel.pending and time.monotonic()<deadline:self.panel.poll();time.sleep(.005)
        self.assertIsNone(self.panel.pending)

    def test_native_keyboard_submit_and_cancel_release_focus(self):
        self.panel.open();self.assertIsNotNone(self.manager.active)
        self.panel.editor.session.insert('Earth');self.panel.editor.session.submit();self.panel.finish_editor()
        self.settle();self.assertEqual(self.panel.query,'Earth');self.assertIsNone(self.manager.active)
        self.panel.edit();self.panel.key(304)
        self.assertIsNone(self.panel.editor);self.assertIsNone(self.manager.active)

    def test_leaving_search_discards_late_reply_and_clears_editor(self):
        started=threading.Event();release=threading.Event()
        def search(*args):
            started.set();release.wait(1);return dict(results=[dict(name='stale')],partial=False)
        with patch('guide_quick_find.search_names',search):
            self.panel.start('Earth');self.assertTrue(started.wait(1))
            self.panel.leave();release.set();self.settle()
        self.assertEqual(self.panel.results,[]);self.assertFalse(self.panel.busy)
        self.panel.edit();self.panel.leave();self.assertIsNone(self.manager.active)

    def test_changed_result_does_not_launch(self):
        self.panel.client=lambda *args:dict(errorCode='changed-source')
        self.panel.activate(dict(kind='file',id='opaque'));self.settle()
        self.assertIsNone(self.panel.opened);self.assertIn('changed',self.panel.notice)

    def test_new_search_replaces_pending_query_and_ignores_old_result(self):
        started=threading.Event();release=threading.Event();queries=[]
        def search(query,*args):
            queries.append(query)
            if query=='old':started.set();release.wait(1)
            return dict(results=[],partial=False)
        with patch('guide_quick_find.search_names',search):
            self.panel.start('old');self.assertTrue(started.wait(1))
            self.panel.start('skipped');self.panel.start('latest');release.set();self.settle()
        self.assertEqual(queries,['old','latest']);self.assertEqual(self.panel.query,'latest')

    def test_home_wheel_renders_find_target_and_search_results_use_same_targets(self):
        from types import SimpleNamespace
        from guide_v3_ui import HomeState,V3UI,DESTINATIONS
        ui=V3UI(world_runtime='missing',world_module='missing')
        home=HomeState(wheel_offset=DESTINATIONS.index('find'))
        layout=ui.render_home(SimpleNamespace(v3_home=home),now=0)
        self.assertTrue(any(r.value=='find' for r in layout.regions))
        self.panel.results=[dict(kind='app',id='app:10001',name='Earth Atlas',label='Application',code=10001)]
        result=ui.render(self.panel.model())
        self.assertTrue(any(r.value==self.panel.results[0] and r.action=='find-action' for r in result.regions))

    def test_shell_home_route_uses_keyboard_and_back_returns_to_search(self):
        import guide_shell
        with patch.multiple(guide_shell,AUDIO_ENABLED=False,STORAGE_ENABLED=False,OPERATIONS_ENABLED=False,WIFI_CONTROL_ENABLED=False):
            state=guide_shell.ShellState()
        self.addCleanup(state.quick_find.close);self.addCleanup(state.nodes_panel.worker.shutdown,wait=True)
        self.addCleanup(state.text_entries.teardown)
        state.open_v3_destination('find');self.assertEqual(state.page,'find');self.assertTrue(state.keyboard_active)
        state.key(304,1);self.assertFalse(state.keyboard_active);self.assertEqual(state.page,'find')
        state.enter_page('media');state.go_back();self.assertEqual(state.page,'find')
        from types import SimpleNamespace
        state.application_panel=SimpleNamespace(finished=False,failed=False)
        self.assertFalse(state.open_find_result(dict(kind='app',code=10001)))
        self.assertEqual(state.page,'find');self.assertIn('active application',state.quick_find.notice)
        state.key(304,1);self.assertEqual(state.page,'home')

if __name__=='__main__':unittest.main()
