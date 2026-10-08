import sys,time,unittest
from pathlib import Path
from dataclasses import replace
from guide_field_ui import FieldUI
from guide_updates_panel import UpdatesPanel
from guide_transfers_panel import TransfersPanel
from guide_files_panel import FilesPanel
from guide_operations_frontend import OperationsPages
ROOT=Path(__file__).resolve().parents[2]
class PanelTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.status=dict(protocol='GUIDE-SIGNED-BUNDLE-1',active={'version':'0.3.9'},sequence=39,highest_sequence=39,
          transaction=dict(id='candidate',state='validated',sequence=40,review=dict(version='0.4.0',source='External or internal file',signer='sha256:'+'a'*64,bytes=1000,components=['shell0','browser'])))
        def client(op,**args):self.calls.append((op,args));return self.status
        self.updates=UpdatesPanel(client);self.updates.status=self.status
        self.transfer_calls=[]
        def transfers(op,**args):
            self.transfer_calls.append((op,args))
            if op=='offer':return dict(id='copy-job',name=args['name'],state='selecting',bytes=0,total=None)
            if op=='locations':return dict(locations=[])
            return dict(jobs=[])
        self.transfers=TransfersPanel(transfers)
        def files(op,args):
            if op==1:return dict(locations=[dict(id='external-root',name='External card',available=True,writable=True)])
            if op==2:return dict(folder=args['folder'],items=[dict(id='f'*32,name='Guide.txt',kind='file',size=12)],next=None)
            raise ValueError('unexpected file operation')
        self.files=FilesPanel(files)
        self.pages=OperationsPages(self.updates,self.transfers,self.files);self.addCleanup(self.pages.close)
    def test_exact_review_required_before_install(self):
        with self.assertRaises(ValueError):self.updates.act('install','candidate')
        self.updates.act('review','candidate')
        with self.assertRaises(ValueError):self.updates.act('install','different')
        self.updates.act('install','candidate');self.updates.future.result()
        self.assertEqual([c[0] for c in self.calls],['authorize','activate','status'])
    def test_downgrade_has_separate_explicit_action(self):
        self.status['transaction']['sequence']=39;self.updates.act('review','candidate')
        self.assertEqual(next(i for i in self.updates.model().items if i.identity=='install').action,'downgrade')
    def test_review_actions_are_visible_and_install_has_initial_focus(self):
        self.pages.open('updates');self.updates.act('review','candidate')
        model=self.pages.model()
        self.assertEqual([item.identity for item in model.items],['install','later'])
        self.assertEqual(model.focus_id,'install')
        self.assertIn('0.4.0',model.items[0].label)
    def test_review_rows_scroll_and_install_is_reachable(self):
        self.pages.open('updates');self.updates.act('review','candidate')
        ui=FieldUI(ROOT/'package/guide-ui')
        output=ROOT/'build/operations-ui-check';output.mkdir(parents=True,exist_ok=True)
        seen=set()
        for _ in range(len(self.pages.model().items)):
            model=self.pages.model();rendered=ui.render(model);seen.update(rendered.visible_ids)
            if model.focus_id=='install':
                self.assertIn('install',[r.identity for r in rendered.regions]);rendered.image.save(output/'update-review.png')
            self.pages.move(1)
        self.assertEqual(seen,{i.identity for i in self.pages.model().items})
    def test_file_copy_uses_opaque_identity_and_opens_transfers(self):
        self.pages.open('files');self.files.future.result();self.pages.poll()
        self.assertEqual(self.pages.model().items[0].identity,'external-root')
        self.pages.activate('external-root');self.files.future.result();self.pages.poll()
        self.pages.activate('f'*32)
        self.assertEqual(self.files.view,'details')
        self.pages.activate('copy')
        self.assertEqual(self.pages.current,'transfers')
        self.transfers.future.result()
        self.assertEqual(self.transfer_calls[0],('offer',{'source':{'entry':'f'*32},'name':'Guide.txt'}))
    def test_file_root_has_storage_and_disconnected_node_without_legacy_rows(self):
        self.pages.open('files');self.files.future.result();self.pages.poll()
        model=self.pages.model();labels=[item.label for item in model.items]
        self.assertIn('External card',labels)
        self.assertIn('Node media  ·  Not connected',labels)
        self.assertNotIn('Transfers',labels);self.assertNotIn('Refresh locations',labels)
        self.assertFalse(next(item for item in model.items if item.identity=='node-media').enabled)
    def test_missing_file_socket_never_exposes_errno(self):
        panel=FilesPanel(lambda _op,_args: (_ for _ in ()).throw(FileNotFoundError(2,'No such file or directory')))
        self.addCleanup(panel.close);panel.open()
        while not panel.poll():time.sleep(.001)
        model=panel.model()
        self.assertEqual([item.label for item in model.items],
                         ['Internal storage','External storage','Node media  ·  Not connected'])
        self.assertNotIn('Errno',model.notice)
    def test_folder_navigation_passes_opaque_identity_not_entry_row(self):
        calls=[];folder_id='a'*32
        def files(op,args):
            calls.append((op,args))
            if op==1:return dict(locations=[dict(id='external-root',name='External card',available=True,writable=False)])
            if args['folder']=='external-root':
                return dict(folder='external-root',items=[dict(id=folder_id,name='MEDIA',kind='folder',size=None)],next=None)
            if args['folder']==folder_id:return dict(folder=folder_id,items=[],next=None)
            raise ValueError('wrong folder identity')
        panel=FilesPanel(files);self.addCleanup(panel.close);panel.open();panel.future.result();panel.poll()
        panel.act('folder','external-root');panel.future.result();panel.poll()
        item=panel.model().items[0]
        self.assertEqual(item.value,folder_id)
        panel.act(item.action,item.value);panel.future.result();panel.poll()
        self.assertEqual(calls[-1],(2,{'folder':folder_id,'offset':0}))

    def test_select_details_supports_files_and_folders_with_slide_metadata(self):
        self.pages.open('files');self.files.future.result();self.pages.poll()
        self.pages.activate('external-root');self.files.future.result();self.pages.poll()
        entry=self.files.listing['items'][0]
        entry.update(modified=1_700_000_000,created=None,extension='txt')
        self.assertTrue(self.pages.details(entry['id']))
        model=self.pages.model()
        self.assertEqual(model.pattern,'file-details')
        self.assertEqual(model.transition,0.0)
        labels={fact.label:fact.value for fact in model.facts}
        self.assertEqual(labels['Extension'],'txt')
        self.assertEqual(labels['Created'],'Unavailable')
    def test_external_guide_media_audio_opens_native_player_action(self):
        panel=FilesPanel(lambda _op,_args: {})
        self.addCleanup(panel.close)
        panel.view='folder';panel.location='external';panel.path=['GUIDE','MEDIA','Albums']
        panel.listing={'items':[dict(id='a'*32,name='Answer.mp3',kind='file',size=12)],'next':None}
        item=panel.model().items[0]
        self.assertEqual(item.action,'play-media')
        self.assertEqual(item.value,dict(kind=1,title='Answer.mp3',folder='Albums'))
    def test_transfer_collision_ui_has_no_overwrite(self):
        self.transfers.view='details';self.transfers.selected=dict(id='job',name='Existing file.mp4',state='needs-attention',reason='name-collision',bytes=1234,total=1234,folder='internal')
        model=self.transfers.model();actions={i.action for i in model.items}
        self.assertTrue({'keep-both','skip','cancel'}<=actions);self.assertNotIn('replace',actions)
        ui=FieldUI(ROOT/'package/guide-ui');output=ROOT/'build/operations-ui-check';output.mkdir(parents=True,exist_ok=True)
        ui.render(replace(model,focus_id='keep')).image.save(output/'transfer-collision.png')
if __name__=='__main__':unittest.main()
