import tempfile
import unittest

from guide_wikipedia_app import WikipediaApplication
from guide_wikipedia_store import ArticleStore


ARTICLE = {
    "pageid": 12,
    "title": "Earth",
    "source": "https://en.wikipedia.org/wiki/Earth",
    "text": "Earth is the third planet from the Sun.",
    "language": "en",
    "license": "CC BY-SA; see source page for attribution and version history",
}


class FakeClient:
    def search(self, query):
        return [{"pageid": 12, "title": "Earth", "wordcount": 1000}]

    def article(self, title):
        return dict(ARTICLE)


class FailingClient:
    def search(self, query):
        raise RuntimeError("network unavailable")


class WikipediaApplicationTests(unittest.TestCase):
    def test_search_open_page_save_and_read_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            app = WikipediaApplication(FakeClient(), ArticleStore(folder), width=20, page_lines=4)
            app.accept()
            self.assertEqual(app.screen, "search")
            app.keyboard.text = "Earth"
            app.keyboard.row = 4
            app.keyboard.column = 4
            app.accept()
            self.assertEqual(app.view()["items"], ["Earth"])
            app.accept()
            self.assertEqual(app.screen, "article")
            self.assertEqual(app.view()["title"], "Earth")
            self.assertTrue(app.save_article())
            app.back()
            app.back()
            app.selected = 1
            app.accept()
            self.assertEqual(app.screen, "saved")
            app.accept()
            self.assertEqual(app.view()["title"], "Earth")
            app.back()
            self.assertEqual(app.screen, "saved")

    def test_network_error_is_visible_and_recoverable(self):
        with tempfile.TemporaryDirectory() as folder:
            app = WikipediaApplication(FailingClient(), ArticleStore(folder))
            app.accept()
            app.keyboard.text = "Earth"
            app.keyboard.row = 4
            app.keyboard.column = 4
            app.accept()
            self.assertEqual(app.screen, "error")
            self.assertEqual(app.message, "NETWORK UNAVAILABLE")
            app.back()
            self.assertEqual(app.screen, "home")

    def test_article_paging_stays_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            app = WikipediaApplication(FakeClient(), ArticleStore(folder), width=20, page_lines=4)
            app._show_article({**ARTICLE, "text": "word " * 200})
            app.move(vertical=999)
            self.assertEqual(app.document.page, app.document.page_count - 1)
            app.move(vertical=-999)
            self.assertEqual(app.document.page, 0)

    def test_back_erases_then_leaves_empty_search(self):
        with tempfile.TemporaryDirectory() as folder:
            app = WikipediaApplication(FakeClient(), ArticleStore(folder))
            app.accept()
            app.keyboard.text = "A"
            app.back()
            self.assertEqual(app.screen, "search")
            self.assertEqual(app.keyboard.text, "")
            app.back()
            self.assertEqual(app.screen, "home")


if __name__ == "__main__":
    unittest.main()
