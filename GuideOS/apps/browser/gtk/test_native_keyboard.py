import unittest
from guide_browser_keyboard import NativeKeyboard


class NativeKeyboardTests(unittest.TestCase):
    def test_shared_editing_cancel_preserves_original_and_clears_draft(self):
        editor=NativeKeyboard('address','https://example.org')
        session=editor.keyboard.session
        editor.input([dict(code=307,value=1),dict(code=308,value=1)])
        self.assertEqual(session.text,'https://example.org')
        editor.input([dict(code=304,value=1)])
        result=editor.keyboard.take_result()
        self.assertEqual(result.state,'cancelled');self.assertIsNone(result.text)
        editor.close();self.assertEqual(session.text,'')

    def test_secret_page_draft_and_shared_case_layer_controls(self):
        editor=NativeKeyboard('page');self.addCleanup(editor.close)
        editor.input([dict(code=305,value=1),dict(code=305,value=2),dict(code=317,value=1),dict(code=305,value=1)])
        self.assertEqual(editor.keyboard.session.text,'qQ')
        self.assertEqual(editor.keyboard.session.display_text(),'••')
        editor.input([dict(code=310,value=1)])
        self.assertEqual(editor.keyboard.page,2)
        self.assertEqual(editor.renderer.render(editor.keyboard).size,(640,480))

    def test_sticks_use_shared_neutral_and_release_rules(self):
        editor=NativeKeyboard('page');self.addCleanup(editor.close)
        editor.input([dict(sticks=dict(left=[0,0],right=[0,0],generation=1))])
        editor.input([dict(sticks=dict(left=[0,0],right=[1,0],generation=1))])
        self.assertEqual(editor.keyboard.session.text,'')
        editor.input([dict(sticks=dict(left=[0,0],right=[0,0],generation=1))])
        self.assertEqual(editor.keyboard.session.text,'w')

    def test_bad_or_excessive_events_are_rejected(self):
        editor=NativeKeyboard('page');self.addCleanup(editor.close)
        for events in ([{}]*33,[dict(sticks=dict(left=[3,0]))],[dict(code='305',value=1)]):
            with self.assertRaises(ValueError):editor.input(events)

if __name__=='__main__':unittest.main()
