#!/usr/bin/env python3
"""Memory-bounded reader for MediaWiki XML export 0.10 article dumps."""

from __future__ import annotations

import bz2
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


NAMESPACE = "http://www.mediawiki.org/xml/export-0.10/"
NS = "{" + NAMESPACE + "}"


class DumpFormatError(ValueError):
    pass


@dataclass(frozen=True)
class DumpArticle:
    title: str
    page_id: int
    revision_id: int
    timestamp: str
    text: str
    redirect: str | None
    model: str
    content_format: str


def _text(element, name, default=""):
    child = element.find(NS + name)
    return default if child is None or child.text is None else child.text


def iter_articles(path, namespace=0):
    """Yield one current revision at a time without retaining the full XML tree."""
    path = Path(path)
    source = bz2.open(path, "rb") if path.suffix == ".bz2" else path.open("rb")
    with source:
        context = ET.iterparse(source, events=("start", "end"))
        _, root = next(context)
        if root.tag != NS + "mediawiki":
            raise DumpFormatError("This is not a MediaWiki export-0.10 document")
        for event, element in context:
            if event != "end" or element.tag != NS + "page":
                continue
            try:
                page_namespace = int(_text(element, "ns", "-1"))
                if page_namespace == namespace:
                    revision = element.find(NS + "revision")
                    if revision is not None:
                        redirect = element.find(NS + "redirect")
                        yield DumpArticle(
                            title=_text(element, "title"),
                            page_id=int(_text(element, "id")),
                            revision_id=int(_text(revision, "id")),
                            timestamp=_text(revision, "timestamp"),
                            text=_text(revision, "text"),
                            redirect=redirect.get("title") if redirect is not None else None,
                            model=_text(revision, "model"),
                            content_format=_text(revision, "format"),
                        )
            except ValueError as error:
                raise DumpFormatError("A page contained an invalid numeric identifier") from error
            finally:
                element.clear()
                root.clear()
