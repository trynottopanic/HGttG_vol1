import tempfile
import unittest

from guide_wikipedia_store import ArticleStore, ArticleStoreError


def example_article(pageid=12):
    return {
        "pageid": pageid,
        "title": "Earth",
        "source": "https://en.wikipedia.org/wiki/Earth",
        "text": "Earth is the third planet from the Sun.",
        "language": "en",
        "license": "CC BY-SA; see source page for attribution and version history",
    }


class ArticleStoreTests(unittest.TestCase):
    def test_article_is_saved_loaded_and_listed(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ArticleStore(folder)
            saved = store.save(example_article())
            self.assertIn("retrievedUtc", saved)
            self.assertEqual(store.load(12)["title"], "Earth")
            self.assertEqual([item["pageid"] for item in store.list()], [12])

    def test_update_replaces_existing_article(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ArticleStore(folder)
            store.save(example_article())
            changed = example_article()
            changed["text"] = "Updated text"
            store.save(changed)
            self.assertEqual(store.load(12)["text"], "Updated text")

    def test_invalid_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ArticleStore(folder)
            with self.assertRaises(ArticleStoreError):
                store.save(example_article("../escape"))


if __name__ == "__main__":
    unittest.main()
