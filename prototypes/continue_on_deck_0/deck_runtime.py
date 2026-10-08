#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal GuideOS runtime: receive a handoff, then continue playback."""

from __future__ import annotations

import argparse
import secrets
import subprocess
import threading
from pathlib import Path

from deck_receiver import DeckServer, HandoffStore


def player_command(manifest: dict, media_path: Path, player: str = "mpv") -> list[str]:
    position_seconds = int(manifest["position_ms"]) / 1000
    return [
        player,
        "--fullscreen",
        "--vo=drm",
        "--ao=alsa",
        "--hwdec=no",
        f"--start={position_seconds:.3f}",
        "--",
        str(media_path),
    ]


class Playback:
    def __init__(self, player: str):
        self.player = player
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def start(self, manifest: dict, media_path: Path) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process = subprocess.Popen(player_command(manifest, media_path, self.player))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="192.168.77.2")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--storage", type=Path, default=Path("/data/guide-media"))
    parser.add_argument("--deck-name", default="Anbernic Deck")
    parser.add_argument("--player", default="mpv")
    args = parser.parse_args()

    pairing_code = f"{secrets.randbelow(1_000_000):06d}"
    playback = Playback(args.player)
    store = HandoffStore(args.storage, args.deck_name, on_commit=playback.start)
    server = DeckServer((args.listen, args.port), store, pairing_code)
    print("\nGUIDE DECK\n", flush=True)
    print(f"Pairing code: {pairing_code}", flush=True)
    print("Connect the USB cable and enter this code on the Node.\n", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
