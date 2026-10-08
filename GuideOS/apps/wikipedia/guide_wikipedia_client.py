#!/usr/bin/env python3
"""Bounded MediaWiki API client for GuideOS Wikipedia views."""

import argparse
from html.parser import HTMLParser
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "GuideOS-Wikipedia/0.1 (https://github.com/trynottopanic/HGttG_vol1)"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 20
MAX_ARTICLE_LINKS = 500


class WikipediaClientError(RuntimeError):
    """A safe, user-presentable Wikipedia request failure."""


class _ReadableArticleParser(HTMLParser):
    """Extract readable blocks and numbered internal links from parsed HTML."""

    SKIPPED = {"script", "style", "table", "figure", "sup", "noscript"}
    SKIPPED_CLASSES = {"mw-editsection", "shortdescription"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    BLOCKS = {"p", "div", "section", "blockquote", "dl", "dt", "dd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.skip_depth = 0
        self.heading_depth = 0
        self.anchor_number = None

    @staticmethod
    def _target(attributes):
        href = dict(attributes).get("href", "")
        if href.startswith("./"):
            target = href[2:]
        elif href.startswith("/wiki/"):
            target = href[6:]
        else:
            return None
        target = urllib.parse.unquote(target.split("#", 1)[0].split("?", 1)[0])
        target = target.replace("_", " ").strip()
        return target if target else None

    def _break(self, count=2):
        self.parts.append("\n" * count)

    def handle_starttag(self, tag, attributes):
        tag = tag.lower()
        if self.skip_depth:
            if tag not in self.VOID:
                self.skip_depth += 1
            return
        classes = set(dict(attributes).get("class", "").split())
        if tag in self.SKIPPED or classes.intersection(self.SKIPPED_CLASSES):
            self.skip_depth = 1
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._break()
            self.parts.append("[ ")
            self.heading_depth += 1
        elif tag in self.BLOCKS:
            self._break()
        elif tag == "li":
            self._break(1)
            self.parts.append("- ")
        elif tag == "br":
            self._break(1)
        elif tag == "a" and len(self.links) < MAX_ARTICLE_LINKS:
            target = self._target(attributes)
            if target:
                self.links.append(target)
                self.anchor_number = len(self.links)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "a" and self.anchor_number is not None:
            self.parts.append(f" [{self.anchor_number}]")
            self.anchor_number = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.heading_depth = max(0, self.heading_depth - 1)
            self.parts.append(" ]")
            self._break()
        elif tag in self.BLOCKS or tag == "li":
            self._break(1 if tag == "li" else 2)

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data.upper() if self.heading_depth else data)

    def result(self):
        text = "".join(self.parts).replace("\r", "")
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip(), self.links


def _request(parameters, opener=urllib.request.urlopen):
    query = urllib.parse.urlencode(parameters)
    request = urllib.request.Request(
        API_URL + "?" + query,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            length = response.headers.get("Content-Length")
            try:
                if length is not None and int(length) > MAX_RESPONSE_BYTES:
                    raise WikipediaClientError("Wikipedia response was too large")
            except ValueError as error:
                raise WikipediaClientError("Wikipedia returned an invalid response size") from error
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise WikipediaClientError("Wikipedia could not be reached") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise WikipediaClientError("Wikipedia response was too large")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WikipediaClientError("Wikipedia returned unreadable data") from error


def search(query, opener=urllib.request.urlopen):
    query = query.strip()
    if not query or len(query) > 200:
        raise WikipediaClientError("Search must contain 1 to 200 characters")
    document = _request(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "list": "search",
            "srnamespace": "0",
            "srlimit": "8",
            "srprop": "size|wordcount|snippet",
            "srsearch": query,
        },
        opener,
    )
    try:
        results = document["query"]["search"]
        return [
            {
                "pageid": int(item["pageid"]),
                "title": str(item["title"]),
                "wordcount": int(item.get("wordcount", 0)),
            }
            for item in results[:8]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise WikipediaClientError("Wikipedia returned an unexpected search result") from error


def parsed_article(title, opener=urllib.request.urlopen):
    """Return one validated MediaWiki article with its rendered HTML intact.

    Callers must still treat ``html`` as hostile input.  The native text view
    feeds it to ``_ReadableArticleParser``; the NetSurf view feeds it to the
    strict allow-list sanitizer in ``guide_wikipedia_html``.
    """
    title = title.strip()
    if not title or len(title) > 300:
        raise WikipediaClientError("Article title must contain 1 to 300 characters")
    document = _request(
        {
            "action": "parse",
            "format": "json",
            "formatversion": "2",
            "page": title,
            "prop": "text|displaytitle",
            "redirects": "1",
            "disabletoc": "1",
        },
        opener,
    )
    try:
        page = document["parse"]
        resolved_title = str(page["title"])
        return {
            "pageid": int(page["pageid"]),
            "title": resolved_title,
            "source": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(resolved_title.replace(" ", "_")),
            "html": str(page["text"]),
            "language": "en",
            "license": "CC BY-SA; see source page for attribution and version history",
        }
    except WikipediaClientError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise WikipediaClientError("Wikipedia returned an unexpected article") from error


def article(title, opener=urllib.request.urlopen):
    """Return the existing bounded plain-text representation of an article."""
    page = parsed_article(title, opener)
    parser = _ReadableArticleParser()
    parser.feed(page["html"])
    parser.close()
    text, links = parser.result()
    result = dict(page)
    del result["html"]
    result["text"] = text
    result["links"] = links
    return result


def readable_text(page):
    """Extract bounded, human-readable text from a validated parsed page."""
    parser = _ReadableArticleParser()
    parser.feed(str(page["html"]))
    parser.close()
    text, links = parser.result()
    return text[:32_000], links


def main(argv=None):
    parser = argparse.ArgumentParser(description="GuideOS native Wikipedia data client")
    subparsers = parser.add_subparsers(dest="command", required=True)
    search_parser = subparsers.add_parser("search", help="find Wikipedia articles")
    search_parser.add_argument("query")
    article_parser = subparsers.add_parser("article", help="retrieve plain article text")
    article_parser.add_argument("title")
    arguments = parser.parse_args(argv)
    try:
        result = search(arguments.query) if arguments.command == "search" else article(arguments.title)
    except WikipediaClientError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
