#!/usr/bin/env python3
"""Turn MediaWiki parse output into bounded, passive HTML for NetSurf."""

from html import escape
from html.parser import HTMLParser
import re
import urllib.parse

MAX_RENDERED_BYTES = 6 * 1024 * 1024
MAX_OPEN_TAGS = 256

_ALLOWED = {
    "a", "article", "b", "blockquote", "br", "caption", "code", "dd",
    "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre",
    "section", "small", "span", "strong", "sub", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
_VOID = {"br", "hr", "img"}
_SKIPPED = {
    "audio", "button", "canvas", "embed", "form", "iframe", "input",
    "link", "meta", "noscript", "object", "script", "select", "source",
    "style", "svg", "textarea", "track", "video",
}
_SKIPPED_CLASSES = {
    "mw-editsection", "mw-jump-link", "noprint", "navbox",
    "shortdescription",
}
_SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")


def _internal_href(raw):
    """Map a Wikipedia article target to the loopback gateway."""
    if not raw:
        return None
    if raw.startswith("#"):
        fragment = raw[1:]
        return "#" + urllib.parse.quote(fragment, safe="-_.:()") if fragment else None
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        return None
    if parsed.path.startswith("./"):
        target = parsed.path[2:]
    elif parsed.path.startswith("/wiki/"):
        target = parsed.path[6:]
    else:
        return None
    target = urllib.parse.unquote(target).replace("_", " ").strip()
    if not target or ":" in target.split("/", 1)[0] or len(target) > 300:
        return None
    href = "/article?" + urllib.parse.urlencode({"title": target})
    if parsed.fragment:
        href += "#" + urllib.parse.quote(parsed.fragment, safe="-_.:()")
    return href


def approved_image_url(raw):
    """Accept only HTTPS images from Wikimedia's upload host."""
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return None
    try:
        invalid_origin = (
            parsed.scheme != "https"
            or parsed.hostname != "upload.wikimedia.org"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        )
    except ValueError:
        return None
    if invalid_origin:
        return None
    return urllib.parse.urlunsplit(("https", "upload.wikimedia.org", parsed.path, parsed.query, ""))


def _image_src(raw):
    approved = approved_image_url(raw)
    if not approved:
        return None
    return "/image?" + urllib.parse.urlencode({"url": approved})


class _PassiveWikipediaHTML(HTMLParser):
    """An allow-list serializer; it never copies arbitrary attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []
        self.skip_depth = 0
        self.truncated = False
        self.rendered_bytes = 0

    def _append(self, value):
        if self.truncated:
            return
        size = len(value.encode("utf-8"))
        if self.rendered_bytes + size > MAX_RENDERED_BYTES:
            self.truncated = True
            return
        self.parts.append(value)
        self.rendered_bytes += size

    def handle_starttag(self, tag, attributes):
        tag = tag.lower()
        if self.skip_depth:
            if tag not in _VOID:
                self.skip_depth += 1
            return
        attrs = dict(attributes)
        classes = set(attrs.get("class", "").split())
        if tag in _SKIPPED or classes.intersection(_SKIPPED_CLASSES):
            if tag not in _VOID:
                self.skip_depth = 1
            return
        if tag not in _ALLOWED:
            return
        safe = []
        identifier = attrs.get("id", "")
        if identifier and _SAFE_ID.fullmatch(identifier):
            safe.append(("id", identifier))
        if tag == "a":
            href = _internal_href(attrs.get("href", ""))
            if href:
                safe.append(("href", href))
        elif tag == "img":
            src = _image_src(attrs.get("src", ""))
            if not src:
                return
            safe.extend((("src", src), ("loading", "lazy")))
            alt = attrs.get("alt", "")[:300]
            if alt:
                safe.append(("alt", alt))
        rendered = "".join(f' {name}="{escape(value, quote=True)}"' for name, value in safe)
        if tag not in _VOID:
            if len(self.open_tags) >= MAX_OPEN_TAGS:
                self.truncated = True
                return
        self._append(f"<{tag}{rendered}>")
        if tag not in _VOID:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attributes):
        tag = tag.lower()
        if tag in _SKIPPED:
            return
        self.handle_starttag(tag, attributes)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag not in _ALLOWED or tag in _VOID or tag not in self.open_tags:
            return
        while self.open_tags:
            opened = self.open_tags.pop()
            self._append(f"</{opened}>")
            if opened == tag:
                break

    def handle_data(self, data):
        if not self.skip_depth:
            self._append(escape(data))

    def result(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        if self.truncated:
            self.parts.append('<p class="guide-notice">Article shortened to protect Deck memory.</p>')
        return "".join(self.parts)


_CSS = """
html{font-family:sans-serif;background:#081118;color:#f3f7fa;font-size:17px;line-height:1.45}
body{margin:0 auto;padding:14px;max-width:46em}header{border-bottom:3px solid #2396b6;margin-bottom:12px}
h1{font-size:1.55em;margin:.25em 0;color:#fff}h2{border-bottom:1px solid #315968;font-size:1.3em}
h3{font-size:1.12em}a{color:#79d8f0;text-decoration:underline}a:focus,button:focus,input:focus{background:#f5b134;color:#111;outline:3px solid #fff}
img{display:block;max-width:100%;height:auto;margin:.5em auto}figure{margin:1em 0}figcaption{font-size:.85em}
table{border-collapse:collapse;max-width:100%;font-size:.88em}th,td{border:1px solid #426675;padding:.25em;vertical-align:top}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.guide-meta,.guide-notice{font-size:.82em;color:#a9c3cd}
.guide-search{display:block;width:96%;font-size:1em;padding:.45em;background:#101f29;color:#fff;border:2px solid #2396b6}
.guide-results li{margin:.55em 0}.guide-action{display:inline-block;padding:.45em .7em;border:2px solid #f5b134;color:#fff}
"""


def page_shell(title, body):
    title = str(title)[:300]
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{escape(title)}</title><style>{_CSS}</style></head><body>{body}</body></html>")


def render_article(page):
    parser = _PassiveWikipediaHTML()
    parser.feed(str(page["html"]))
    parser.close()
    title = str(page["title"])
    header = (f"<header><h1>{escape(title)}</h1>"
              '<p class="guide-meta">English Wikipedia · CC BY-SA · '
              f'<a href="/">New search</a> · '
              '<a class="guide-action" href="/guide/se">X: summarize</a></p></header>')
    return page_shell(title, header + "<article>" + parser.result() + "</article>")


def render_se_consent(title):
    body = (f'<header><h1>Summarize {escape(str(title))}</h1></header>'
            '<p>The article text will be sent only to your currently trusted Node '
            'and its Semiotic Engine.</p>'
            '<form action="/guide/se/start" method="post">'
            '<button class="guide-action" type="submit">A: allow and summarize</button></form>'
            '<p><a href="/article?' + urllib.parse.urlencode({"title": str(title)}) + '">Cancel</a></p>')
    return page_shell("Confirm summary", body)


def render_se_wait():
    return page_shell("Summarizing", '<meta http-equiv="refresh" content="2;url=/guide/se/result">'
                      '<header><h1>Semiotic Engine</h1></header><p>Reading this article…</p>'
                      '<p class="guide-notice">The most complex requests may take up to five minutes.</p>')


def render_se_result(title, summary, uncertainty="", error=""):
    if error:
        content = '<p class="guide-notice">' + escape(error) + '</p>'
    else:
        paragraphs = ''.join('<p>' + escape(part) + '</p>' for part in str(summary).split('\n') if part.strip())
        content = '<article>' + paragraphs + '</article>'
        if uncertainty:
            content += '<p class="guide-notice">Uncertainty: ' + escape(str(uncertainty)) + '</p>'
    back = '/article?' + urllib.parse.urlencode({"title": str(title)})
    return page_shell("Semiotic summary", '<header><h1>Semiotic summary</h1></header>' + content +
                      f'<p><a href="{escape(back, quote=True)}">Return to article</a></p>')


def render_search(query, results):
    items = []
    for item in results[:8]:
        title = str(item["title"])[:300]
        href = "/article?" + urllib.parse.urlencode({"title": title})
        words = max(0, int(item.get("wordcount", 0)))
        items.append(f'<li><a href="{escape(href, quote=True)}">{escape(title)}</a> '
                     f'<small>({words} words)</small></li>')
    listing = "".join(items)
    if not listing and query:
        listing = "<li>No matching articles were found.</li>"
    body = ('<header><h1>Guide Wikipedia</h1></header><form action="/search" method="get">'
            f'<input class="guide-search" name="q" maxlength="200" value="{escape(query, quote=True)}">'
            '<p><button type="submit">Search</button></p></form>'
            f'<ol class="guide-results">{listing}</ol>')
    return page_shell("Guide Wikipedia", body)


def render_home():
    return render_search("", [])
