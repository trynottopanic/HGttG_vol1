#!/usr/bin/env python3
"""Loopback-only Guide start page for the first general NetSurf browser."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse

CSS = """
html{font-family:sans-serif;background:#071018;color:#f4f8fb;font-size:18px;line-height:1.45}
body{margin:0 auto;padding:20px;max-width:38em}header{border-bottom:3px solid #2396b6;margin-bottom:18px}
h1{font-size:1.65em;margin:.2em 0;color:#fff}.guide-mark{color:#f5b134}.guide-note{color:#a9c3cd}
.guide-card{background:#10202a;border-left:4px solid #2396b6;padding:12px 16px;margin:14px 0}
a{color:#7cddf4}a:focus{background:#f5b134;color:#071018;outline:3px solid #fff}
"""


def page():
    body = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Guide Web</title>
<style>{css}</style></head><body><header><h1><span class="guide-mark">GUIDE</span> WEB</h1>
<p class="guide-note">A small, general window into the public web.</p></header>
<div class="guide-card"><strong>Enter an address</strong><br>Select the address bar at the top.
The Deck keyboard opens automatically; type an HTTP or HTTPS address, then choose Enter.</div>
<div class="guide-card"><strong>Controls</strong><br>Stick or D-pad: pointer · A: select · B: leave browser<br>
L1/R1: page up/down · Y: back or stop where available</div>
<p><a href="https://lite.duckduckgo.com/lite/">Open lightweight web search</a></p>
<p><a href="https://en.wikipedia.org/">Open Wikipedia</a></p>
<p class="guide-note">Prototype limits: modern script-heavy sites may not work. Do not enter passwords yet.
GuideOS does not promise private browsing in this first version.</p></body></html>"""
    return body.format(css=CSS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _pattern, *_args):
        return

    def do_GET(self):
        if self.path not in ("/", "/health"):
            body = b"Not part of Guide Web."
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        elif self.path == "/health":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        else:
            body = page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
