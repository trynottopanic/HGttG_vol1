import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'apps/notepad/cartridge/application'),str(ROOT/'package/guide-foundation/python'),str(ROOT/'package/guide-ipc/python')]
from notepad import Notepad,text_checked,name_checked,encode_checkpoint,decode_checkpoint
from guide_application_runtime import PrivateStore,Session

class API:
    def __init__(self,root):self.store=PrivateStore(root,524288);self.view=None;self.pending=None;self.ack=None;self.fail=None
    def acquire(self,cap):return cap
    def ready(self):pass
    def present(self,grant,title,body,actions,presentation=None):self.view=(title,body,actions);self.presentation=presentation
    def read(self,grant,key):return self.store.read(key)
    def write(self,grant,key,text):
        if self.fail==key:raise OSError('injected write failure')
        return self.store.write(key,text)
    def checkpointed(self,receipt):self.ack=receipt
    def text(self,grant,initial,limit,**metadata):self.pending=(initial,limit);self.text_metadata=metadata

class NotepadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.api=API(Path(self.temp.name));self.addCleanup(self.api.store.close)
        self.app=Notepad(self.api)
    def act(self,label):
        self.app.handle({0:1,1:self.api.view[2].index(label)})
    def edit(self,text):
        if self.app.text_mode!='edit':self.act('Edit text')
        self.app.handle({0:2,1:text})
    def save_new(self,name,text):
        self.act('New note');self.edit(text);self.act('Save internal draft');self.app.handle({0:2,1:name})
    def test_install_independent_draft_edit_checkpoint_relaunch(self):
        self.save_new('First','hello\nworld')
        self.assertEqual(self.api.presentation[3],'saved')
        self.app.handle({0:3});self.assertIsNotNone(self.api.ack)
        self.app=Notepad(self.api);self.assertEqual(self.app.view,'list')
        self.act('First');self.assertFalse(self.app.doc['dirty'])
        self.assertEqual(self.app.doc['text'],'hello\nworld')
    def test_cancel_text_preserves_previous_committed_edits(self):
        self.act('New note');self.edit('committed');self.act('Edit text');self.app.handle({0:2,1:None})
        self.assertEqual(self.app.doc['text'],'committed')
    def test_maximum_unicode_checkpoint_fits_host_limit(self):
        for text in ('😀'*5120,'\x00'*5120,'\n'*5120):
            self.app.new();self.app.text_mode='edit';self.app.handle({0:2,1:text})
            raw=self.api.read(2,'checkpoint');self.assertLessEqual(len(raw.encode()),24576)
            self.assertEqual(decode_checkpoint(raw)['text'],text)
    def test_normalization_limits_and_names(self):
        self.assertEqual(text_checked('\ufeffa\r\nb\rc'),'a\nb\nc')
        self.assertEqual(name_checked('e\u0301'),'é')
        for name in ('','CON','com1.txt','..','bad/leaf','bad.','x'*33,'a\x00b'):
            with self.assertRaises(ValueError):name_checked(name)
        with self.assertRaises(ValueError):text_checked('x'*5121)
    def test_replacement_requires_explicit_choice(self):
        self.save_new('First','old');self.act('Close note');self.act('New note');self.edit('new')
        self.act('Save internal draft');self.app.handle({0:2,1:'FIRST'})
        self.assertEqual(self.app.view,'replace');self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nold')
        self.act('Replace draft');self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nnew')
    def test_full_draft_store_preserves_existing_notes(self):
        for i in range(16):
            self.save_new('Note '+str(i),'😀'*5120);self.act('Close note')
        before=self.api.read(2,'draft-index')
        self.act('New note');self.edit('retain this');self.act('Save internal draft');self.app.handle({0:2,1:'Seventeenth'})
        self.assertEqual(len(self.app.index),16);self.assertEqual(self.api.read(2,'draft-index'),before)
        self.assertIn('16 draft slots',self.api.presentation[6]);self.assertEqual(self.app.doc['text'],'retain this')
        self.assertLess(sum(p.stat().st_size for p in Path(self.temp.name).iterdir()),524288)
    def test_failed_save_does_not_claim_success_or_lose_buffer(self):
        self.save_new('First','old');self.edit('new');self.api.fail='draft-0';self.act('Save internal draft')
        self.assertTrue(self.app.doc['dirty']);self.assertEqual(self.app.doc['text'],'new')
        self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nold');self.assertEqual(self.api.presentation[3],'unsaved')
    def test_failed_index_publication_leaves_recoverable_buffer(self):
        self.act('New note');self.edit('retain me');self.api.fail='draft-index'
        self.act('Save internal draft');self.app.handle({0:2,1:'First'})
        self.api.fail=None;self.app=Notepad(self.api);self.act('Restore recovery')
        self.assertEqual(self.app.doc['text'],'retain me');self.assertEqual(self.app.index,[])
    def test_corrupt_checkpoint_is_not_silently_replaced(self):
        self.api.write(2,'checkpoint','bad');self.app=Notepad(self.api)
        self.assertTrue(self.app.blocked);self.app.handle({0:3});self.assertIsNone(self.api.ack)
        self.assertEqual(self.api.read(2,'checkpoint'),'bad')
    def test_discard_needs_confirmation_and_preserves_saved_draft(self):
        self.save_new('First','old');self.edit('new');self.act('Close note');self.act('Discard changes')
        self.assertEqual(self.app.doc['text'],'new');self.act('Confirm discard')
        self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nold');self.assertIsNone(decode_checkpoint(self.api.read(2,'checkpoint')))
    def test_shutdown_keeps_queued_text_ahead_of_checkpoint(self):
        session=Session({},None,None);session.events=[{0:1,1:0},{0:2,1:'working text'}]
        session.shell(4,{})
        self.assertEqual(session.events,[{0:2,1:'working text'},{0:3,1:'checkpoint'}])

    def test_native_fields_and_caret_recovery(self):
        self.act('New note');self.assertEqual(self.api.text_metadata['label'],'Note text')
        self.assertTrue(self.api.text_metadata['multiline'])
        self.app.handle({0:2,1:'working text',3:4})
        self.app=Notepad(self.api);self.assertEqual(self.app.view,'recovery')
        self.act('Restore recovery');self.act('Edit text')
        self.assertEqual(self.api.text_metadata['caret'],4)
        self.app.handle({0:2,1:None});self.act('Save internal draft')
        self.assertFalse(self.api.text_metadata['multiline']);self.assertEqual(self.api.text_metadata['submit_label'],'Save')

    def test_clean_relaunch_reads_without_rewriting_private_data(self):
        self.save_new('First','saved text')
        before={p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()}
        self.app=Notepad(self.api);self.assertEqual(self.app.view,'list')
        self.assertEqual(self.api.presentation[4],['','saved text'])
        self.assertEqual({p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()},before)

    def test_changed_clean_checkpoint_still_requires_recovery(self):
        self.save_new('First','saved text');self.api.write(2,'draft-0','TEXT1\nchanged elsewhere')
        self.app=Notepad(self.api);self.assertEqual(self.app.view,'recovery')
        self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nchanged elsewhere')
        self.act('Restore recovery');self.assertEqual(self.app.doc['text'],'saved text')

    def test_cancel_empty_new_returns_notes(self):
        self.act('New note');self.app.handle({0:2,1:None})
        self.assertEqual(self.app.view,'list');self.assertIsNone(self.app.doc)
        self.assertIsNone(decode_checkpoint(self.api.read(2,'checkpoint')))

    def test_save_as_cancel_returns_document(self):
        self.save_new('First','saved text');self.act('Actions');self.act('Save As internal draft')
        self.app.handle({0:2,1:None});self.assertEqual(self.app.view,'editor')
        self.assertEqual(self.api.presentation[5],{0:0,1:1,2:2,3:3})

    def test_save_and_close_waits_for_success(self):
        self.act('New note');self.edit('retain');self.act('Close note');self.act('Keep as internal draft')
        self.assertTrue(self.app.close_after_save)
        self.app.handle({0:2,1:None});self.assertIsNotNone(self.app.doc);self.assertFalse(self.app.close_after_save)
        self.act('Close note');self.act('Keep as internal draft');self.app.handle({0:2,1:'First'})
        self.assertIsNone(self.app.doc);self.assertEqual(self.app.view,'list')
        self.assertEqual(self.api.read(2,'draft-0'),'TEXT1\nretain')

    def test_failed_checkpoint_preserves_document_and_does_not_claim_saved(self):
        self.save_new('First','old');self.edit('new');self.api.fail='checkpoint';self.act('Save internal draft')
        self.assertIsNotNone(self.app.doc);self.assertTrue(self.app.doc['dirty'])
        self.assertEqual(self.api.presentation[3],'unsaved')
        self.act('Close note');self.act('Discard changes');self.act('Confirm discard')
        self.assertEqual(self.app.doc['text'],'new')

    def test_back_from_replace_clears_pending_close(self):
        self.save_new('First','old');self.act('Close note');self.act('New note');self.edit('new')
        self.act('Close note');self.act('Keep as internal draft');self.app.handle({0:2,1:'First'})
        self.act('Return to note');self.assertFalse(self.app.close_after_save)
        self.act('Save internal draft');self.app.handle({0:2,1:'Second'})
        self.assertIsNotNone(self.app.doc);self.assertEqual(self.app.doc['name'],'Second')

if __name__=='__main__':unittest.main()
