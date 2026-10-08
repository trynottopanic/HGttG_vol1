import unittest

from guide_wikipedia_html import render_article, render_search, render_se_consent, render_se_result


class WikipediaHTMLTests(unittest.TestCase):
    def test_article_keeps_reading_structure_and_rewrites_internal_links(self):
        page = {"title": "Earth", "html": '<h2 id="History">History</h2><p>See <a href="./Planet">planet</a>.</p><table><tr><th>Age</th><td>Old</td></tr></table>'}
        rendered = render_article(page)
        self.assertIn('<h2 id="History">History</h2>', rendered)
        self.assertIn('href="/article?title=Planet"', rendered)
        self.assertIn("<table><tr><th>Age</th><td>Old</td></tr></table>", rendered)

    def test_active_content_and_arbitrary_attributes_are_removed(self):
        page = {"title": "Safe", "html": '<script>alert(1)</script><p onclick="bad()" style="position:fixed">Readable</p><a href="javascript:bad()">No</a>'}
        rendered = render_article(page)
        self.assertNotIn("alert", rendered)
        self.assertNotIn("onclick", rendered)
        self.assertNotIn("position:fixed", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("Readable", rendered)

    def test_only_wikimedia_https_images_survive(self):
        page = {"title": "Image", "html": '<img src="//upload.wikimedia.org/a.png" alt="Earth"><img src="https://example.test/tracker.png"><img src="data:image/png;base64,abc">'}
        rendered = render_article(page)
        self.assertIn('src="/image?url=https%3A%2F%2Fupload.wikimedia.org%2Fa.png"', rendered)
        self.assertNotIn("example.test", rendered)
        self.assertNotIn("data:image", rendered)

    def test_search_results_are_local_links(self):
        rendered = render_search("earth", [{"title": "Earth & Moon", "wordcount": 12}])
        self.assertIn("/article?title=Earth+%26+Moon", rendered)
        self.assertIn("Earth &amp; Moon", rendered)

    def test_article_exposes_controller_summary_action(self):
        rendered = render_article({"title": "Earth", "html": "<p>Home</p>"})
        self.assertIn('href="/guide/se"', rendered)
        self.assertIn("X: summarize", rendered)

    def test_summary_pages_escape_untrusted_text(self):
        self.assertNotIn("<script>", render_se_consent("<script>"))
        rendered = render_se_result("Earth", "Safe <script>", "low < confidence")
        self.assertIn("Safe &lt;script&gt;", rendered)
        self.assertIn("low &lt; confidence", rendered)


if __name__ == "__main__":
    unittest.main()
