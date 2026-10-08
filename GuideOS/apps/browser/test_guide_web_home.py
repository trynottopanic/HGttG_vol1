import unittest

from guide_web_home import page


class GuideWebHomeTests(unittest.TestCase):
    def test_home_uses_dark_guide_schema_and_plain_language(self):
        rendered = page()
        self.assertIn("background:#071018", rendered)
        self.assertIn("GUIDE", rendered)
        self.assertIn("Enter an address", rendered)
        self.assertIn("Do not enter passwords yet", rendered)

    def test_home_links_are_https(self):
        rendered = page()
        self.assertNotIn('href="http://', rendered)
        self.assertIn("https://lite.duckduckgo.com/lite/", rendered)


if __name__ == "__main__":
    unittest.main()
