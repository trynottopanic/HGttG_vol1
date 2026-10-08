#!/usr/bin/env python3
"""Loopback-only Wikipedia gateway for the GuideOS NetSurf view."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.parse
import urllib.error
import urllib.request

from guide_wikipedia_client import USER_AGENT, WikipediaClientError, parsed_article, readable_text, search
from guide_wikipedia_html import (approved_image_url, page_shell, render_article, render_home,
                                  render_search, render_se_consent, render_se_result, render_se_wait)

DEFAULT_PORT = 8765
MAX_URL_LENGTH = 2048
MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}
SE_INPUT = Path("/run/guideos-se-input.txt")
SE_SUMMARY = Path("/run/guideos-se-summary.txt")
SE_UNCERTAINTY = Path("/run/guideos-se-uncertainty.txt")


def fetch_image(url, opener=urllib.request.urlopen):
    approved = approved_image_url(url)
    if not approved:
        raise WikipediaClientError("That image is not from Wikimedia.")
    request = urllib.request.Request(
        approved,
        headers={"User-Agent": USER_AGENT, "Accept": "image/png,image/jpeg,image/gif,image/webp"},
        method="GET",
    )
    try:
        with opener(request, timeout=20) as response:
            if approved_image_url(response.geturl()) is None:
                raise WikipediaClientError("Wikimedia redirected that image elsewhere.")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type not in IMAGE_TYPES:
                raise WikipediaClientError("Wikipedia returned an unsupported image type.")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > MAX_IMAGE_BYTES:
                raise WikipediaClientError("That image is too large for this Deck.")
            body = response.read(MAX_IMAGE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
        raise WikipediaClientError("That Wikipedia image could not be loaded.") from error
    if len(body) > MAX_IMAGE_BYTES:
        raise WikipediaClientError("That image is too large for this Deck.")
    return content_type, body


def _error_page(message):
    from html import escape
    return page_shell("Wikipedia problem", '<h1>Wikipedia problem</h1><p>' + escape(message) + '</p><p><a href="/">Return to search</a></p>')


class WikipediaGateway(BaseHTTPRequestHandler):
    server_version = "GuideWikipedia/0.4"

    def log_message(self, pattern, *args):
        sys.stderr.write("wikipedia: " + pattern % args + "\n")

    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        self._send_bytes(status, body.encode("utf-8"), content_type)

    def _send_bytes(self, status, encoded, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if len(self.path) > MAX_URL_LENGTH:
            self._send(414, _error_page("That request was too long."))
            return
        request = urllib.parse.urlsplit(self.path)
        parameters = urllib.parse.parse_qs(request.query, keep_blank_values=True)
        try:
            if request.path == "/health":
                self._send(200, "ok\n", "text/plain; charset=utf-8")
            elif request.path == "/":
                self._send(200, render_home())
            elif request.path == "/search":
                query = parameters.get("q", [""])[0]
                self._send(200, render_search(query, search(query)))
            elif request.path == "/article":
                title = parameters.get("title", [""])[0]
                page = parsed_article(title)
                text, _links = readable_text(page)
                with self.server.guide_lock:
                    self.server.guide_article = {"title": page["title"], "text": text}
                self._send(200, render_article(page))
            elif request.path == "/guide/se":
                with self.server.guide_lock:
                    current = dict(self.server.guide_article or {})
                if not current:
                    self._send(409, _error_page("Open an article before asking for a summary."))
                else:
                    self._send(200, render_se_consent(current["title"]))
            elif request.path == "/guide/se/result":
                with self.server.guide_lock:
                    job = dict(self.server.guide_job)
                if job.get("state") == "running":
                    self._send(200, render_se_wait())
                else:
                    self._send(200, render_se_result(job.get("title", "article"),
                                                     job.get("summary", ""),
                                                     job.get("uncertainty", ""),
                                                     job.get("error", "")))
            elif request.path == "/image":
                content_type, body = fetch_image(parameters.get("url", [""])[0])
                self._send_bytes(200, body, content_type)
            else:
                self._send(404, _error_page("That page is not part of Guide Wikipedia."))
        except WikipediaClientError as error:
            if request.path == "/image":
                self._send(404, "image unavailable\n", "text/plain; charset=utf-8")
            else:
                self._send(502, _error_page(str(error)))
        except (KeyError, TypeError, ValueError):
            self._send(400, _error_page("That Wikipedia request was not understood."))

    def do_POST(self):
        if self.path != "/guide/se/start":
            self._send(404, _error_page("That action is not part of Guide Wikipedia."))
            return
        with self.server.guide_lock:
            article = dict(self.server.guide_article or {})
            running = self.server.guide_job.get("state") == "running"
            if article and not running:
                self.server.guide_job = {"state": "running", "title": article["title"]}
        if not article:
            self._send(409, _error_page("Open an article before asking for a summary."))
            return
        if not running:
            threading.Thread(target=self.server.run_se_job, args=(article,), daemon=True).start()
        self.send_response(303)
        self.send_header("Location", "/guide/se/result")
        self.send_header("Content-Length", "0")
        self.end_headers()


class GuideWikipediaServer(HTTPServer):
    def __init__(self, address):
        super().__init__(address, WikipediaGateway)
        self.guide_lock = threading.Lock()
        self.guide_article = None
        self.guide_job = {"state": "idle", "title": "article"}

    @staticmethod
    def _read_private(path, maximum):
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            return os.read(descriptor, maximum + 1).decode("utf-8")[:maximum]
        finally:
            os.close(descriptor)

    def run_se_job(self, article):
        error = summary = uncertainty = ""
        try:
            descriptor = os.open(SE_INPUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                                 getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(article["text"][:32_000])
            result = subprocess.run(["/usr/bin/guide-se-deck", "summarize", str(SE_INPUT)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, timeout=310, check=False)
            if result.returncode != 0:
                detail = next((line[6:] for line in result.stdout.splitlines()
                               if line.startswith("ERROR=")), "Semiotic Engine did not answer.")
                raise RuntimeError(detail)
            summary = self._read_private(SE_SUMMARY, 4000)
            try:
                uncertainty = self._read_private(SE_UNCERTAINTY, 500)
            except OSError:
                pass
        except (OSError, RuntimeError, subprocess.SubprocessError, UnicodeError) as problem:
            error = " ".join(str(problem).split())[:300]
        finally:
            try:
                SE_INPUT.unlink()
            except OSError:
                pass
        with self.guide_lock:
            self.guide_job = {"state": "done", "title": article["title"],
                              "summary": summary, "uncertainty": uncertainty, "error": error}


def main(argv=None):
    parser = argparse.ArgumentParser(description="GuideOS Wikipedia gateway for NetSurf")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args(argv)
    if not 1024 <= arguments.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    # One request at a time keeps work and memory bounded on a small Deck.
    server = GuideWikipediaServer(("127.0.0.1", arguments.port))
    print(f"Guide Wikipedia ready at http://127.0.0.1:{arguments.port}/", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
