#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local Node video player with a Continue on Deck action."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from node_sender import transfer


def byte_range(value: str | None, size: int) -> tuple[int, int] | None:
    if not value or not value.startswith("bytes=") or "," in value:
        return None
    first, last = value[6:].split("-", 1)
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        length = int(last)
        start, end = max(0, size - length), size - 1
    if start < 0 or start > end or start >= size:
        raise ValueError("Invalid byte range")
    return start, end


PAGE = """<!doctype html><meta charset=utf-8><title>Third Way Node Player</title>
<style>body{background:#111;color:#eee;font:18px system-ui;max-width:1000px;margin:24px auto;padding:0 18px}video{width:100%;max-height:70vh;background:#000}button,input{font:inherit;padding:.65em;margin:.5em .25em .5em 0}button{background:#f5c400;border:0;color:#111;font-weight:700}#status{white-space:pre-wrap}</style>
<h1>Third Way Node</h1><p>Playing: <strong>__NAME__</strong></p>
<video id=v controls src="video"></video><div>
<label>Code shown by Deck <input id=code inputmode=numeric maxlength=6 size=8></label>
<button id=send>Continue on Deck</button></div><p id=status>Connect the Deck by USB, then enter its pairing code.</p>
<script>const v=document.querySelector('#v'),s=document.querySelector('#status'),b=document.querySelector('#send');
b.onclick=async()=>{v.pause();b.disabled=true;s.textContent='Checking and transferring… Keep the cable connected.';
try{let r=await fetch('handoff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({position_ms:Math.round(v.currentTime*1000),code:document.querySelector('#code').value})});let x=await r.json();if(!r.ok)throw Error(x.error||'Transfer failed');s.textContent=`Ready on ${x.deck_name} at ${(x.position_ms/1000).toFixed(3)} seconds. It is safe to disconnect.`}catch(e){s.textContent=e.message}finally{b.disabled=false}};</script>"""


class PlayerServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, video: Path, deck_url: str, owner_token: str):
        self.video = video
        self.deck_url = deck_url
        self.owner_token = owner_token
        super().__init__(address, PlayerHandler)


class PlayerHandler(BaseHTTPRequestHandler):
    server: PlayerServer

    def _allowed_path(self) -> str | None:
        prefix = f"/{self.server.owner_token}/"
        path = urlparse(self.path).path
        return path[len(prefix):] if path.startswith(prefix) else None

    def do_GET(self) -> None:
        path = self._allowed_path()
        if path == "":
            body = PAGE.replace("__NAME__", html.escape(self.server.video.name)).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif path == "video":
            self._video()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _video(self) -> None:
        size = self.server.video.stat().st_size
        try:
            selected = byte_range(self.headers.get("Range"), size)
        except (ValueError, TypeError):
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE); return
        start, end = selected or (0, size - 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT if selected else HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(self.server.video.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if selected:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with self.server.video.open("rb") as source:
            source.seek(start); remaining = end - start + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk: break
                self.wfile.write(chunk); remaining -= len(chunk)

    def do_POST(self) -> None:
        if self._allowed_path() != "handoff":
            self.send_error(HTTPStatus.NOT_FOUND); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("The handoff request is not a valid size.")
            request = json.loads(self.rfile.read(length))
            position_ms = int(request["position_ms"])
            pairing_code = str(request["code"])
            if position_ms < 0:
                raise ValueError("The playback position cannot be negative.")
            if len(pairing_code) != 6 or not pairing_code.isdigit():
                raise ValueError("Enter the six-digit code shown by the Deck.")
            result = transfer(self.server.video, position_ms,
                              self.server.deck_url, pairing_code)
            resume = result["resume"]
            self._json(HTTPStatus.OK, {"deck_name": result["deck_name"],
                                      "position_ms": resume["position_ms"]})
        except Exception as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="authorized local video file")
    parser.add_argument("--deck", default="http://192.168.77.2:8766")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    video = args.video.resolve(strict=True)
    token = secrets.token_urlsafe(24)
    server = PlayerServer(("127.0.0.1", args.port), video, args.deck, token)
    address = f"http://127.0.0.1:{server.server_port}/{token}/"
    print(address, flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(address)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
