import bz2
import io
from pathlib import Path
import tempfile
import unittest

from guide_wikipedia_dump import dated_name, parse_checksums
from guide_wikipedia_dump_reader import iter_articles
from guide_wikitext_reader import readable_text


class DumpTests(unittest.TestCase):
    def test_checksum_manifest_and_dated_alias(self):
        checksums = parse_checksums(
            "e328a056321b276adb46a2c112a220ec855f0dc2  enwiki-20260901-pages-articles-multistream.xml.bz2\n"
        )
        self.assertEqual(
            dated_name("enwiki-latest-pages-articles-multistream.xml.bz2", checksums),
            "enwiki-20260901-pages-articles-multistream.xml.bz2",
        )

    def test_streams_main_namespace_article(self):
        xml = b'''<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/" version="0.10" xml:lang="en">
        <page><title>Earth</title><ns>0</ns><id>42</id><revision><id>7</id><timestamp>2026-01-01T00:00:00Z</timestamp><contributor><username>A</username></contributor><model>wikitext</model><format>text/x-wiki</format><text>Blue [[planet]].</text><sha1>x</sha1></revision></page>
        <page><title>Talk:Earth</title><ns>1</ns><id>43</id></page></mediawiki>'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tiny.xml.bz2"
            path.write_bytes(bz2.compress(xml))
            articles = list(iter_articles(path))
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Earth")
        self.assertEqual(articles[0].text, "Blue [[planet]].")

    def test_readable_wikitext(self):
        source = "'''Earth''' is a [[planet|world]].\n\n== Uses ==\n* Home<ref>citation</ref>\n{{Navbox}}"
        self.assertEqual(readable_text(source), "Earth is a world.\n\nUSES\n\n• Home")


if __name__ == "__main__":
    unittest.main()
