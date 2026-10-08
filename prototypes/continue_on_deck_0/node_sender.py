#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Desktop Node sender for the CONTINUE-ON-DECK-0 protocol."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def parse_timecode(value: str) -> int:
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, MM:SS, or HH:MM:SS.")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as error:
        raise ValueError("The timecode contains something other than numbers.") from error
    if any(number < 0 for number in numbers) or any(number >= 60 for number in numbers[1:]):
        raise ValueError("Minutes and seconds after a colon must be below 60.")
    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60 + number
    return round(seconds * 1000)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_request(url: str, method: str = "GET", value: dict | None = None,
                 headers: dict | None = None) -> dict:
    body = None if value is None else json.dumps(value).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=body, headers=request_headers, method=method), timeout=15) as response:
        return json.load(response)


def upload_file(url: str, path: Path, token: str, progress=None) -> None:
    parsed = urlparse(url)
    connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(parsed.hostname, parsed.port, timeout=60)
    size = path.stat().st_size
    connection.putrequest("PUT", parsed.path)
    connection.putheader("Authorization", f"Bearer {token}")
    connection.putheader("Content-Type", "application/octet-stream")
    connection.putheader("Content-Length", str(size))
    connection.endheaders()
    sent = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            connection.send(chunk)
            sent += len(chunk)
            if progress:
                progress(sent, size)
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    if response.status != 200:
        message = json.loads(payload).get("error", "The Deck rejected the video.")
        raise RuntimeError(message)


def transfer(path: Path, position_ms: int, deck_url: str, pairing_code: str, progress=None) -> dict:
    path = path.resolve(strict=True)
    deck_url = deck_url.rstrip("/")
    deck = json_request(f"{deck_url}/v1/deck")
    size = path.stat().st_size
    if size > int(deck["free_bytes"]):
        raise ValueError(f"{deck['deck_name']} does not have enough free space.")
    if path.suffix.lower() not in deck["supported_extensions"]:
        raise ValueError(f"{deck['deck_name']} does not report support for {path.suffix or 'this file type'}.")
    metadata = {
        "display_name": path.name,
        "size_bytes": size,
        "sha256": sha256_file(path),
        "position_ms": position_ms,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    pending = json_request(f"{deck_url}/v1/handoffs", "POST", metadata,
                           {"X-Guide-Pairing-Code": pairing_code})
    handoff_id, token = pending["handoff_id"], pending["token"]
    upload_file(f"{deck_url}/v1/handoffs/{handoff_id}/media", path, token, progress)
    result = json_request(f"{deck_url}/v1/handoffs/{handoff_id}/commit", "POST", {},
                          {"Authorization": f"Bearer {token}"})
    result["deck_name"] = deck["deck_name"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--at", required=True, help="resume time: seconds, MM:SS, or HH:MM:SS")
    parser.add_argument("--deck", default="http://192.168.77.2:8766")
    parser.add_argument("--code", required=True, help="six-digit code displayed by the Deck")
    args = parser.parse_args()

    last_print = 0.0
    def show_progress(sent: int, total: int) -> None:
        nonlocal last_print
        now = time.monotonic()
        if now - last_print >= 0.5 or sent == total:
            print(f"Sent {sent:,} of {total:,} bytes ({sent / total:.0%})", flush=True)
            last_print = now

    result = transfer(args.video, parse_timecode(args.at), args.deck, args.code, show_progress)
    resume = result["resume"]
    print(f"Ready on the Deck at {resume['position_ms'] / 1000:.3f} seconds.")
    print("It is now safe to disconnect the cable.")


if __name__ == "__main__":
    main()
