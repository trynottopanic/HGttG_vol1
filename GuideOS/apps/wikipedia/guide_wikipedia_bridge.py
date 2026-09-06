#!/usr/bin/env python3
"""Small line-oriented bridge between the framebuffer shell and Wikipedia."""

import sys
import unicodedata
import re

from guide_wikipedia_client import WikipediaClientError, article, search

MAX_TEXT_CHARACTERS = 6 * 1024 * 1024


def _plain(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    return normalized.encode("ascii", "replace").decode("ascii").replace("\r", " ")


def _readable_extract(value):
    """Give the framebuffer explicit paragraphs and headings, never raw XML."""
    text = _plain(value).replace("\r", "")
    text = re.sub(
        r"^\s*={2,6}\s*(.*?)\s*={2,6}\s*$",
        lambda match: "\n" + match.group(1).strip().upper() + "\n",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"^[*#]+\s*", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_search(query, search_function=search):
    results = search_function(query.strip())
    lines = ["GUIDE-WIKIPEDIA-SEARCH-1"]
    for result in results[:8]:
        title = _plain(result["title"]).replace("\n", " ").replace("\t", " ")[:300]
        lines.append(f"RESULT={int(result.get('wordcount', 0))}\t{title}")
    return "\n".join(lines) + "\n"


def format_article(title, article_function=article):
    document = article_function(title.strip())
    title = _plain(document["title"]).replace("\n", " ")[:300]
    source = _plain(document["source"]).replace("\n", " ")[:1000]
    text = _readable_extract(document.get("text", ""))[:MAX_TEXT_CHARACTERS]
    links = []
    for value in document.get("links", [])[:500]:
        link = _plain(value).replace("\n", " ").replace("\t", " ").strip()[:300]
        if link:
            links.append("LINK=" + link)
    metadata = "GUIDE-WIKIPEDIA-ARTICLE-2\nTITLE=" + title + "\nSOURCE=" + source
    if links:
        metadata += "\n" + "\n".join(links)
    return metadata + "\n\n" + text


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2 or arguments[0] not in ("search", "article"):
        print("ERROR=USE SEARCH OR ARTICLE WITH ONE TITLE")
        return 2
    try:
        if arguments[0] == "search":
            print(format_search(arguments[1]), end="")
        else:
            print(format_article(arguments[1]))
    except WikipediaClientError as error:
        print("ERROR=" + _plain(error).replace("\n", " ")[:300])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
