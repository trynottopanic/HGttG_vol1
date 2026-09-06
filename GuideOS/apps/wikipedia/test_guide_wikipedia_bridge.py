import unittest

from guide_wikipedia_bridge import _readable_extract, format_article, format_search
from guide_wikipedia_client import WikipediaClientError


class WikipediaBridgeTests(unittest.TestCase):
    def test_search_emits_separate_selectable_results(self):
        def fake_search(query):
            self.assertEqual(query, "Earth")
            return [{"title": "Earth", "pageid": 1, "wordcount": 2}]

        result = format_search(" Earth ", fake_search)
        self.assertEqual(
            result,
            "GUIDE-WIKIPEDIA-SEARCH-1\nRESULT=2\tEarth\n",
        )

    def test_empty_results_emit_an_empty_result_set(self):
        self.assertEqual(format_search("Unknown", lambda query: []),
                         "GUIDE-WIKIPEDIA-SEARCH-1\n")

    def test_article_is_fetched_only_after_selection(self):
        def fake_article(title):
            self.assertEqual(title, "Earth")
            return {"title": "Earth", "source": "https://example.test/Earth", "text": "Blue planet.", "links": []}

        self.assertEqual(
            format_article("Earth", fake_article),
            "GUIDE-WIKIPEDIA-ARTICLE-2\nTITLE=Earth\nSOURCE=https://example.test/Earth\n\nBlue planet.",
        )

    def test_article_links_are_separate_safe_records(self):
        document = {"title": "Earth", "source": "https://example.test/Earth",
                    "text": "A world [1].", "links": ["Planet", "Solar\nSystem"]}
        result = format_article("Earth", lambda _title: document)
        self.assertIn("\nLINK=Planet\nLINK=Solar System\n\nA world [1].", result)

    def test_article_sections_are_readable_not_markup(self):
        self.assertEqual(
            _readable_extract("Lead.\n\n== History ==\n\n* First\n* Second"),
            "Lead.\n\nHISTORY\n\n- First\n- Second",
        )


if __name__ == "__main__":
    unittest.main()
