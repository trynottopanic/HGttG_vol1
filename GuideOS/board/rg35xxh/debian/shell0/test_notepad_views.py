import unittest
from concurrent.futures import Future
from PIL import ImageFont
from guide_application_panel import ApplicationPanel
from guide_application_views import ApplicationViews
from guide_deck_text import DeckText
from guide_input import TextEntryManager,Keyboard,TextRequest,StickController

class NotepadViewTests(unittest.TestCase):
    def panel(self):
        p=ApplicationPanel.__new__(ApplicationPanel)
        p.owner='application:10001';p.identity=None;p.pending=None;p.operation='snapshot'
        p.closing=p.finished=p.failed=False;p.editor=p.stick_input=None
        p.commands=[];p.notice='';p.cursor=0;p.text_entries=TextEntryManager()
        p.editor_initial='';p.editor_metadata=False;p.cancel_confirmation=False
        p.document_scroll=0;p.scroll_limit=0;p.document_identity=None
        p.view={0:'Notepad',1:'\n'.join('Line '+str(i) for i in range(30)),2:['Edit text','Save internal draft','Actions','Close note'],3:{0:'document',1:'First',2:'Internal draft',3:'saved',5:{0:0,1:1,2:2,3:3},6:''}}
        return p
    def renderer(self):
        fonts={s:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',s) for s in (14,16,18,20,24,28)}
        return ApplicationViews(DeckText(fonts))
    def snapshot(self,p,text):
        p.pending=Future();p.pending.set_result({0:1,1:p.view,2:text});p.poll()
    def test_document_pointer_buttons_and_controller_share_actions(self):
        p=self.panel();view=self.renderer();layout=view.render(p.model())
        footer=[r for r in layout.regions if r.action=='application-action']
        self.assertEqual([r.value for r in footer],[0,1,2,3])
        for code in (305,307,308,304):p.key(code)
        self.assertEqual(p.commands,[(2,{0:i}) for i in range(4)])
        self.assertFalse(p.closing)
    def test_document_scroll_is_bounded_and_full_text_survives(self):
        p=self.panel();renderer=self.renderer();before=p.view[1]
        renderer.render(p.model());p.scroll_limit=renderer.max_scroll
        self.assertEqual(p.scroll_limit,24)
        for _ in range(60):p.key(545)
        self.assertEqual(p.document_scroll,24)
        renderer.render(p.model());self.assertEqual(p.model().content,before)
        for _ in range(60):p.key(544)
        self.assertEqual(p.document_scroll,0);self.assertEqual(p.commands,[])
    def test_name_keyboard_purpose_caret_and_submit(self):
        p=self.panel();self.snapshot(p,{0:'Name',1:32,2:{0:'Note name',1:False,2:2,3:'Save'}})
        self.assertFalse(p.editor.session.request.multiline)
        self.assertEqual(p.editor.session.request.label,'Note name');self.assertEqual(p.editor.session.cursor,2)
        p.editor.handle('submit');p.finish_editor()
        self.assertEqual(p.commands,[(3,{0:'Name',2:2})])
    def test_dirty_cancel_keeps_name_constraints_and_caret(self):
        p=self.panel();self.snapshot(p,{0:'Name',1:32,2:{0:'Note name',1:False,2:2,3:'Save'}})
        p.editor.handle('insert',text='x');p.key(304)
        self.assertTrue(p.cancel_confirmation);self.assertFalse(p.editor.session.request.multiline)
        self.assertEqual(p.editor.session.cursor,3);self.assertEqual(p.editor.session.text,'Naxme')
        p.key(304);self.assertFalse(p.cancel_confirmation)
    def test_home_preserves_unsubmitted_text_with_caret(self):
        p=self.panel();self.snapshot(p,{0:'old',1:5120,2:{0:'Note text',1:True,2:1,3:'Done'}})
        p.editor.handle('insert',text=' new');p.key(316)
        self.assertEqual(p.close_text,{0:'o newld',1:True,2:5});self.assertTrue(p.closing)
        self.assertEqual(p.close_destination,'home')
    def test_shell_menu_routes_document_shortcuts_before_pointer_context(self):
        from types import SimpleNamespace
        from guide_menu_input import MenuInput
        from guide_input import PointerController
        p=self.panel();p.scroll_limit=24;menu=MenuInput.__new__(MenuInput)
        menu.pointer=PointerController();menu.state=SimpleNamespace(page='application',application_panel=p,_key=lambda code,value:p.key(code))
        for code in (305,307,308,545,304):self.assertTrue(menu.key(code))
        self.assertEqual(p.commands,[(2,{0:i}) for i in range(4)])
        self.assertEqual(p.document_scroll,1);self.assertIsNone(menu.pointer.context)
    def test_maximum_utf8_and_empty_document_render(self):
        p=self.panel();r=self.renderer()
        for body in ('','😀'*5120,'\n'*5120,'\x00'*5120):
            p.view[1]=body;layout=r.render(p.model());self.assertEqual(layout.image.size,(640,480))
            self.assertEqual(p.view[1],body)

if __name__=='__main__':unittest.main()
