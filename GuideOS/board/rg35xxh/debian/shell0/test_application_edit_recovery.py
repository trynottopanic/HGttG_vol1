import unittest
from concurrent.futures import Future
from guide_application_panel import ApplicationPanel
from guide_input import Keyboard,TextRequest,TextEntryManager,StickController

class ApplicationEditRecoveryTests(unittest.TestCase):
    def panel(self):
        p=ApplicationPanel.__new__(ApplicationPanel)
        p.closing=False;p.view=None;p.commands=[];p.close_text=None;p.cancel_confirmation=False
        p.owner='application:10001';p.text_entries=TextEntryManager();p.editor_initial='old'
        p.editor=Keyboard(p.text_entries,TextRequest(owner_id=p.owner,field_id='document',label='Text',initial='old',multiline=True,max_length=5120,max_bytes=20480))
        p.stick_input=StickController(p.editor)
        return p
    def test_home_snapshots_unsubmitted_editor(self):
        p=self.panel();p.editor.handle('insert',text=' new');p.key(316)
        self.assertEqual(p.close_text,{0:'old new',1:True});self.assertTrue(p.closing)
    def test_done_immediately_followed_by_home_keeps_submission(self):
        p=self.panel();p.editor.handle('insert',text=' new');p.editor.handle('submit');p.finish_editor();p.key(316)
        self.assertEqual(p.close_text,{0:'old new'})
    def test_cancel_changed_session_requires_confirmation(self):
        p=self.panel();p.editor.handle('insert',text=' new');p.key(304)
        self.assertTrue(p.cancel_confirmation);self.assertEqual(p.editor.session.text,'old new');self.assertEqual(p.commands,[])
        p.key(304);self.assertFalse(p.cancel_confirmation);p.key(304);p.key(305)
        self.assertIsNone(p.editor);self.assertEqual(p.commands,[(6,{})])
    def test_cancel_unchanged_session_is_immediate(self):
        p=self.panel();p.key(304);self.assertIsNone(p.editor);self.assertFalse(p.cancel_confirmation)

if __name__=='__main__':unittest.main()
