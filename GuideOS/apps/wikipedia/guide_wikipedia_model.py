"""Device-independent interaction and text layout for Guide Wikipedia."""

from dataclasses import dataclass
import re
import textwrap


KEYBOARD_ROWS = (
    "QWERTYUIOP",
    "ASDFGHJKL",
    "ZXCVBNM,./",
    "1234567890",
    ("CASE", "MORE", "SPACE", "ERASE", "SEARCH", "CANCEL"),
)


@dataclass
class SearchKeyboard:
    text: str = ""
    row: int = 0
    column: int = 0
    maximum: int = 200

    def _row_keys(self):
        row = KEYBOARD_ROWS[self.row]
        return tuple(row) if isinstance(row, str) else row

    @property
    def selected(self):
        return self._row_keys()[self.column]

    def move(self, horizontal=0, vertical=0):
        if vertical:
            self.row = (self.row + vertical) % len(KEYBOARD_ROWS)
            self.column = min(self.column, len(self._row_keys()) - 1)
        if horizontal:
            self.column = (self.column + horizontal) % len(self._row_keys())

    def activate(self):
        key = self.selected
        if key == "ERASE":
            self.text = self.text[:-1]
            return "edited"
        if key == "SEARCH":
            return "search" if self.text.strip() else "empty"
        if key == "CANCEL":
            return "cancel"
        if key in ("CASE", "MORE"):
            return key.lower()
        value = " " if key == "SPACE" else key
        if len(self.text) >= self.maximum:
            return "full"
        self.text += value
        return "edited"

    def erase(self):
        self.text = self.text[:-1]


class ArticleDocument:
    def __init__(self, title, text, width=48, page_lines=16):
        if width < 20 or page_lines < 4:
            raise ValueError("article layout is too small")
        self.title = title
        self.width = width
        self.page_lines = page_lines
        self.lines = self._layout(text)
        self.page = 0

    def _layout(self, text):
        lines = []
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        for paragraph in re.split(r"\n\s*\n", normalized):
            paragraph = " ".join(part.strip() for part in paragraph.splitlines()).strip()
            if not paragraph:
                continue
            heading = paragraph.startswith("==") and paragraph.endswith("==")
            if heading:
                paragraph = paragraph.strip("= ").upper()
            wrapped = textwrap.wrap(
                paragraph,
                width=self.width,
                break_long_words=False,
                break_on_hyphens=False,
                replace_whitespace=True,
            ) or [""]
            if heading and lines:
                lines.append("")
            lines.extend(wrapped)
            lines.append("")
        if lines and not lines[-1]:
            lines.pop()
        return lines or ["THIS ARTICLE HAS NO PLAIN TEXT."]

    @property
    def page_count(self):
        return max(1, (len(self.lines) + self.page_lines - 1) // self.page_lines)

    @property
    def visible_lines(self):
        start = self.page * self.page_lines
        return self.lines[start:start + self.page_lines]

    def move_page(self, change):
        self.page = min(max(self.page + change, 0), self.page_count - 1)

    @property
    def position_label(self):
        return f"{self.page + 1} OF {self.page_count}"
