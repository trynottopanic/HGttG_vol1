"""Frontend-independent state machine for the Guide Wikipedia reader."""

from dataclasses import dataclass, field

from guide_wikipedia_model import ArticleDocument, KEYBOARD_ROWS, SearchKeyboard


HOME_ITEMS = ("SEARCH WIKIPEDIA", "SAVED ARTICLES", "ABOUT")


@dataclass
class WikipediaApplication:
    client: object
    store: object
    width: int = 48
    page_lines: int = 16
    screen: str = "home"
    selected: int = 0
    keyboard: SearchKeyboard = field(default_factory=SearchKeyboard)
    results: list = field(default_factory=list)
    saved: list = field(default_factory=list)
    article_record: dict | None = None
    document: ArticleDocument | None = None
    message: str = ""
    article_parent: str = "results"

    def move(self, horizontal=0, vertical=0):
        if self.screen == "search":
            self.keyboard.move(horizontal, vertical)
        elif self.screen in ("home", "results", "saved"):
            items = self._items()
            if items and vertical:
                self.selected = (self.selected + vertical) % len(items)
        elif self.screen == "article":
            change = vertical or horizontal
            if change:
                self.document.move_page(change)

    def accept(self):
        if self.screen == "home":
            if self.selected == 0:
                self.screen = "search"
            elif self.selected == 1:
                self._open_saved()
            else:
                self.screen = "about"
            self.selected = 0
            return
        if self.screen == "search":
            result = self.keyboard.activate()
            if result == "search":
                self._search()
            elif result == "empty":
                self.message = "TYPE SOMETHING TO SEARCH"
            return
        if self.screen == "results" and self.results:
            self._open_online_article(self.results[self.selected]["title"])
            return
        if self.screen == "saved" and self.saved:
            self._show_article(self.saved[self.selected], "saved")

    def back(self):
        if self.screen == "search":
            if self.keyboard.text:
                self.keyboard.erase()
            else:
                self.screen = "home"
                self.selected = 0
            return
        if self.screen == "article":
            self.screen = self.article_parent
        elif self.screen in ("results", "saved", "about", "error"):
            self.screen = "home"
        self.selected = 0
        self.message = ""

    def save_article(self):
        if self.screen != "article" or not self.article_record:
            return False
        try:
            self.store.save(self.article_record)
        except Exception as error:
            self.message = self._safe_error(error, "ARTICLE COULD NOT BE SAVED")
            return False
        self.message = "SAVED FOR OFFLINE READING"
        return True

    def _items(self):
        if self.screen == "home":
            return HOME_ITEMS
        if self.screen == "results":
            return self.results
        if self.screen == "saved":
            return self.saved
        return ()

    def _search(self):
        self.message = "SEARCHING"
        try:
            self.results = self.client.search(self.keyboard.text)
        except Exception as error:
            self._fail(error, "WIKIPEDIA COULD NOT BE REACHED")
            return
        self.selected = 0
        self.screen = "results"
        self.message = "" if self.results else "NO ARTICLES FOUND"

    def _open_online_article(self, title):
        self.message = "LOADING ARTICLE"
        try:
            record = self.client.article(title)
        except Exception as error:
            self._fail(error, "ARTICLE COULD NOT BE LOADED")
            return
        self._show_article(record, "results")

    def _open_saved(self):
        try:
            self.saved = self.store.list()
        except Exception as error:
            self._fail(error, "SAVED ARTICLES COULD NOT BE READ")
            return
        self.screen = "saved"
        self.message = "" if self.saved else "NO SAVED ARTICLES"

    def _show_article(self, record, parent="results"):
        self.article_record = record
        self.article_parent = parent
        self.document = ArticleDocument(
            record["title"], record["text"], self.width, self.page_lines
        )
        self.screen = "article"
        self.selected = 0
        self.message = ""

    def _fail(self, error, fallback):
        self.screen = "error"
        self.message = self._safe_error(error, fallback)

    @staticmethod
    def _safe_error(error, fallback):
        text = str(error).strip()
        return text.upper()[:160] if text else fallback

    def view(self):
        """Return only data a small native framebuffer view needs to draw."""
        view = {"screen": self.screen, "selected": self.selected, "message": self.message}
        if self.screen == "home":
            view["items"] = list(HOME_ITEMS)
        elif self.screen == "search":
            view.update({
                "query": self.keyboard.text,
                "keyboard": [list(row) for row in KEYBOARD_ROWS],
                "key": self.keyboard.selected,
                "key_position": (self.keyboard.row, self.keyboard.column),
            })
        elif self.screen in ("results", "saved"):
            view["items"] = [item["title"] for item in self._items()]
        elif self.screen == "article":
            view.update({
                "title": self.article_record["title"],
                "lines": self.document.visible_lines,
                "position": self.document.position_label,
                "source": self.article_record["source"],
                "license": self.article_record["license"],
            })
        elif self.screen == "about":
            view["lines"] = [
                "A READING-FIRST WIKIPEDIA CLIENT.",
                "NO REMOTE WEB PAGES OR SCRIPTS.",
                "ARTICLES: CC BY-SA.",
            ]
        return view
