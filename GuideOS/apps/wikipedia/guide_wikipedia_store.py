"""Small, atomic offline article store for Guide Wikipedia."""

import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

MAX_ARTICLES = 32
MAX_ARTICLE_BYTES = 2 * 1024 * 1024


class ArticleStoreError(RuntimeError):
    pass


class ArticleStore:
    def __init__(self, root):
        self.root = Path(root)

    def _safe_path(self, pageid):
        try:
            number = int(pageid)
        except (TypeError, ValueError) as error:
            raise ArticleStoreError("Article page id is invalid") from error
        if number <= 0:
            raise ArticleStoreError("Article page id is invalid")
        return self.root / f"{number}.json"

    def save(self, article):
        required = ("pageid", "title", "source", "text", "language", "license")
        if any(field not in article for field in required):
            raise ArticleStoreError("Article record is incomplete")
        destination = self._safe_path(article["pageid"])
        record = {field: article[field] for field in required}
        record["retrievedUtc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > MAX_ARTICLE_BYTES:
            raise ArticleStoreError("Article is too large to save")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ArticleStoreError("Article store is not a safe directory")
        os.chmod(self.root, 0o700)
        if destination.exists() and destination.is_symlink():
            raise ArticleStoreError("Article destination is not a regular file")
        existing = self.list()
        if not destination.exists() and len(existing) >= MAX_ARTICLES:
            raise ArticleStoreError("Saved article limit reached")
        descriptor, temporary = tempfile.mkstemp(prefix=".article-", suffix=".partial", dir=str(self.root))
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return record

    def load(self, pageid):
        path = self._safe_path(pageid)
        if path.is_symlink() or not path.is_file():
            raise ArticleStoreError("Saved article was not found")
        if path.stat().st_size > MAX_ARTICLE_BYTES:
            raise ArticleStoreError("Saved article is too large")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if int(record["pageid"]) != int(pageid):
                raise ArticleStoreError("Saved article identity does not match")
            return record
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ArticleStoreError("Saved article is unreadable") from error

    def list(self):
        if not self.root.is_dir():
            return []
        records = []
        for path in sorted(self.root.glob("[0-9]*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                records.append(self.load(path.stem))
            except ArticleStoreError:
                continue
        return records[:MAX_ARTICLES]
