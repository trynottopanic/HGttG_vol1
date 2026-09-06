import unittest

from guide_wikipedia_model import ArticleDocument, SearchKeyboard


class SearchKeyboardTests(unittest.TestCase):
    def test_controller_can_type_erase_and_submit(self):
        keyboard = SearchKeyboard()
        self.assertEqual(keyboard.selected, "Q")
        keyboard.activate()
        keyboard.move(horizontal=1)
        keyboard.activate()
        self.assertEqual(keyboard.text, "QW")
        keyboard.erase()
        self.assertEqual(keyboard.text, "Q")
        keyboard.row = 4
        keyboard.column = 4
        self.assertEqual(keyboard.activate(), "search")

    def test_blank_search_is_not_submitted(self):
        keyboard = SearchKeyboard(row=4, column=4)
        self.assertEqual(keyboard.activate(), "empty")

    def test_cursor_wraps(self):
        keyboard = SearchKeyboard()
        keyboard.move(horizontal=-1)
        self.assertEqual(keyboard.selected, "P")
        keyboard.move(vertical=-1)
        self.assertEqual(keyboard.row, 4)
        self.assertEqual(keyboard.column, 5)


class ArticleDocumentTests(unittest.TestCase):
    def test_text_is_wrapped_and_paginated(self):
        text = "First paragraph contains several words.\n\n== Section ==\n\nSecond paragraph."
        article = ArticleDocument("Test", text, width=20, page_lines=4)
        self.assertGreater(article.page_count, 1)
        self.assertTrue(all(len(line) <= 20 for line in article.lines))
        self.assertIn("SECTION", article.lines)
        article.move_page(1)
        self.assertEqual(article.position_label, f"2 OF {article.page_count}")
        article.move_page(999)
        self.assertEqual(article.page, article.page_count - 1)
        article.move_page(-999)
        self.assertEqual(article.page, 0)

    def test_empty_article_has_visible_explanation(self):
        article = ArticleDocument("Empty", "")
        self.assertIn("NO PLAIN TEXT", article.visible_lines[0])


if __name__ == "__main__":
    unittest.main()
