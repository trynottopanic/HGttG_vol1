#!/usr/bin/env python3
"""Conservative, dependency-free conversion from common wikitext to readable text."""

from __future__ import annotations

import html
import re


def _remove_balanced(text: str, opening="{{", closing="}}") -> str:
    output = []
    depth = 0
    index = 0
    while index < len(text):
        if text.startswith(opening, index):
            depth += 1
            index += len(opening)
        elif depth and text.startswith(closing, index):
            depth -= 1
            index += len(closing)
        elif not depth:
            output.append(text[index])
            index += 1
        else:
            index += 1
    return "".join(output)


def readable_text(source: str) -> str:
    """Render useful prose while refusing to execute templates or HTML."""
    text = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
    text = re.sub(r"<ref\b[^>]*>.*?</ref\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<ref\b[^>]*/\s*>", "", text, flags=re.I)
    text = re.sub(r"\{\|.*?\|\}", "\n[Table omitted in lightweight view]\n", text, flags=re.S)
    text = _remove_balanced(text)
    text = re.sub(r"\[\[(?:File|Image|Category):[^\]]+\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[(?:https?://\S+)\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://[^\]]+\]", "", text)
    text = re.sub(r"^(={2,6})\s*(.*?)\s*\1\s*$", lambda m: "\n" + m.group(2).upper() + "\n", text, flags=re.M)
    text = re.sub(r"^[*#]+\s*", "• ", text, flags=re.M)
    text = re.sub(r"^[;:]\s*", "  ", text, flags=re.M)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
