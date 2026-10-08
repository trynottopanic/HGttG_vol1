"""Actual font fallback/shaping checks for the optional Debian display profile."""
import os
import unittest
from PIL import Image
from guide_unicode import ImageCanvas, UnicodeText
from guide_text_entry import TextEntryManager, TextRequest


class UnicodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = UnicodeText()
        if not cls.text.available:
            if os.environ.get('GUIDE_REQUIRE_UNICODE') == '1':
                raise AssertionError('Required Unicode provider is missing')
            raise unittest.SkipTest('Optional Unicode profile is absent')

    def test_installed_fonts_cover_representative_scripts_without_missing_glyphs(self):
        for sample in ('Café Ελληνικά Кириллица', 'العربية שלום', 'हिन्दी বাংলা தமிழ்',
                       'ไทย ქართული Հայերեն', '中文 日本語 한국어', 'e\u0301 → € 🙂'):
            with self.subTest(sample=sample):
                self.assertEqual(self.text.unknown_glyphs(sample), 0)
                image = self.text.render(sample, 20)
                self.assertIsNotNone(image.getbbox())
                self.assertLess(image.width, 640)

    def test_bidirectional_caret_uses_shaped_layout_positions(self):
        text = 'שלום'
        self.assertGreater(self.text.cursor_x(text, 0), self.text.cursor_x(text, len(text)))
        self.assertLessEqual(self.text.cursor_x(text, 0), self.text.measure(text)[0])

    def test_literal_text_is_not_markup_and_wrapping_is_bounded(self):
        self.assertGreater(self.text.measure('<b>test</b>')[0], self.text.measure('test')[0])
        image = self.text.render('日本語と中文 ' * 12, width=180)
        self.assertLessEqual(image.width, 182)
        self.assertGreater(image.height, 20)

    def test_color_emoji_and_compositing_preserve_color(self):
        image = self.text.render('🙂', 30)
        colored = {rgb[:3] for rgb in image.getdata() if rgb[3] > 128 and max(rgb[:3]) - min(rgb[:3]) > 40}
        self.assertGreater(len(colored), 10)
        canvas = Image.new('RGB', (160, 80), 'white')
        self.text.draw(ImageCanvas(canvas), (4, 4), '🙂 中文', 24)
        self.assertEqual(canvas.getpixel((159, 79)), (255, 255, 255))

    def test_future_text_caller_round_trips_unicode_without_normalizing_it(self):
        value = 'Café e\u0301 العربية 中文 🙂'
        manager = TextEntryManager()
        session = manager.open(TextRequest('test.unicode', 'note', 'Note', initial=value))
        manager.dispatch('test.unicode', session.token, 'submit')
        result = manager.take_result('test.unicode', session.token)
        self.assertEqual(result.text, value)


if __name__ == '__main__':
    unittest.main()
