#!/usr/bin/env python3
"""Line-oriented bridge between the framebuffer shell and Guide Nodes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from guide_node_client import NodeClient, NodeLinkError, discover_nodes, validate_node_description


CANDIDATES_FILE = Path("/run/guideos-node-candidates.json")
SESSION_FILE = Path("/run/guideos-node-session.json")
MEDIA_FILE = Path("/run/guideos-node-media.json")
DECK_ID_FILE = Path("/var/lib/guideos/node-link/deck-id")
TRUSTED_FILE = Path("/var/lib/guideos/node-link/trusted-nodes.json")
MAX_NODES = 8
MEDIA_RUNTIME = Path("/usr/lib/guideos/media")
MEDIA_LOADER = MEDIA_RUNTIME / "lib/ld-linux-aarch64.so.1"
MEDIA_FFMPEG = MEDIA_RUNTIME / "bin/ffmpeg"
MEDIA_AUDIO_CONTROL = MEDIA_RUNTIME / "bin/guide-audio-control"
MEDIA_CONTROL_DIRECTORY = Path("/run")


def _safe_text(value: object, limit: int = 64) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return "".join(character if 32 <= ord(character) < 127 else "?" for character in text)[:limit]


def _atomic_private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(value, destination, separators=(",", ":"))
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load(path: Path) -> object:
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def _deck_id() -> str:
    try:
        value = DECK_ID_FILE.read_text(encoding="ascii").strip()
        if re.fullmatch(r"[0-9a-f]{32}", value):
            return value
    except OSError:
        pass
    value = os.urandom(16).hex()
    DECK_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DECK_ID_FILE.with_suffix(".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as destination:
        destination.write(value + "\n")
        destination.flush()
        os.fsync(destination.fileno())
    os.replace(temporary, DECK_ID_FILE)
    return value


def _trusted_nodes() -> dict[str, dict[str, str]]:
    try:
        value = _load(TRUSTED_FILE)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {key: record for key, record in value.items()
            if re.fullmatch(r"[0-9a-f]{32}", key) and isinstance(record, dict) and
            isinstance(record.get("secret"), str)}


def discover(discovery=discover_nodes) -> int:
    nodes = discovery()[:MAX_NODES]
    _atomic_private_json(CANDIDATES_FILE, nodes)
    trusted = _trusted_nodes()
    reconnected = -1
    for index, node in enumerate(nodes):
        record = trusted.get(str(node["node_id"]))
        if not record:
            continue
        try:
            client = NodeClient(validate_node_description(node))
            result = client.reconnect(_deck_id(), record["secret"])
            _atomic_private_json(SESSION_FILE, {
                "description": node, "token": client.token,
                "expires_at": result.get("expires_at"), "trusted": True,
            })
            reconnected = index
            break
        except NodeLinkError:
            continue
    print("GUIDE-NODES-1")
    for index, node in enumerate(nodes):
        print(f"NODE={index}\t{_safe_text(node['name'])}")
    if reconnected >= 0:
        print(f"TRUSTED={reconnected}")
    return 0


def pair(index_text: str, code: str) -> int:
    if not re.fullmatch(r"[0-7]", index_text) or not re.fullmatch(r"[0-9]{6}", code):
        raise NodeLinkError("PAIRING DETAILS ARE INVALID")
    candidates = _load(CANDIDATES_FILE)
    if not isinstance(candidates, list) or int(index_text) >= len(candidates):
        raise NodeLinkError("SEARCH FOR THE NODE AGAIN")
    description = validate_node_description(candidates[int(index_text)])
    client = NodeClient(description)
    result = client.pair(code, client_id=_deck_id())
    session = {
        "description": description,
        "token": client.token,
        "expires_at": result.get("expires_at"),
    }
    _atomic_private_json(SESSION_FILE, session)
    android = client.android_status()
    print("GUIDE-NODE-PAIRED-1")
    print("NAME=" + _safe_text(description["name"]))
    print("ANDROID=" + _safe_text(android.get("state", "unknown")).upper())
    return 0


def trust() -> int:
    client = _session_client()
    result = client.trust()
    secret = result.get("secret")
    client_id = result.get("client_id")
    if (not isinstance(secret, str) or len(secret) < 32 or
            client_id != _deck_id()):
        raise NodeLinkError("NODE DID NOT COMPLETE TRUST")
    node_id = str(client.description["node_id"])
    trusted = _trusted_nodes()
    trusted[node_id] = {"name": str(client.description["name"])[:64], "secret": secret}
    _atomic_private_json(TRUSTED_FILE, trusted)
    print("GUIDE-NODE-TRUSTED-1")
    print("NAME=" + _safe_text(client.description["name"]))
    return 0


def untrust() -> int:
    client = _session_client()
    node_id = str(client.description["node_id"])
    client.revoke_trust()
    trusted = _trusted_nodes()
    trusted.pop(node_id, None)
    _atomic_private_json(TRUSTED_FILE, trusted)
    print("GUIDE-NODE-UNTRUSTED-1")
    return 0


def _session_client() -> NodeClient:
    session = _load(SESSION_FILE)
    if not isinstance(session, dict) or not isinstance(session.get("token"), str):
        raise NodeLinkError("NODE SESSION IS INVALID")
    client = NodeClient(validate_node_description(session.get("description")))
    client.token = session["token"]
    return client


def status() -> int:
    client = _session_client()
    node = client.status()
    capabilities = client.capabilities()
    print("GUIDE-NODE-STATUS-1")
    print("READY=" + ("YES" if node.get("ready") else "NO"))
    for capability in capabilities.get("capabilities", [])[:16]:
        if isinstance(capability, dict) and isinstance(capability.get("id"), str):
            print("CAPABILITY=" + _safe_text(capability["id"]) + "\t" +
                  ("READY" if capability.get("available") else "UNAVAILABLE"))
    return 0


def media() -> int:
    client = _session_client()
    library = client.media_library(0, 100)
    source_items = library.get("items", [])
    items = []
    if isinstance(source_items, list):
        for value in source_items[:100]:
            if not isinstance(value, dict):
                continue
            media_id = value.get("id")
            kind = value.get("kind")
            name = value.get("name")
            size = value.get("size")
            if (not isinstance(media_id, str) or not re.fullmatch(r"[0-9a-f]{32}", media_id)
                    or kind not in ("audio", "video") or not isinstance(name, str)
                    or not isinstance(size, int) or size < 0):
                continue
            source_subtitles = value.get("subtitles", [])
            subtitles = []
            if isinstance(source_subtitles, list):
                subtitles = [_safe_text(label, 32) for label in source_subtitles[:8]
                             if isinstance(label, str) and label.strip()]
            items.append({"id": media_id, "kind": kind, "name": name[:240], "size": size,
                          "subtitles": subtitles})
    _atomic_private_json(MEDIA_FILE, items)
    print("GUIDE-MEDIA-1")
    print("TOTAL=" + str(max(0, int(library.get("count", len(items))))))
    for index, item in enumerate(items):
        print(f"MEDIA={index}\t{item['kind']}\t{item['size']}\t{_safe_text(item['name'], 120)}")
        for track, label in enumerate(item["subtitles"]):
            print(f"SUBTITLE={index}\t{track}\t{label}")
    return 0


def _escaped_filter_path(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _player_arguments(ticket_url: str, kind: str, position: float = 0.0,
                      rate: int = 1, subtitle: int = -1,
                      one_frame: bool = False) -> list[str]:
    arguments = [
        str(MEDIA_LOADER), "--library-path", str(MEDIA_RUNTIME / "lib"),
        str(MEDIA_FFMPEG), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-stats", "-stats_period", "2", "-threads", "2",
        "-thread_queue_size", "8192", "-rw_timeout", "600000000",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
    ]
    if position > 0.01:
        arguments += ["-ss", f"{position:.3f}"]
    if not one_frame:
        arguments += ["-readrate", "2" if rate == 2 else "1",
                      "-readrate_initial_burst", "5"]
    arguments += ["-i", ticket_url]
    if kind == "audio":
        if rate == 2:
            arguments += ["-filter:a", "atempo=2.0"]
        return arguments + ["-vn", "-f", "alsa", "default"]
    video_filters = [
        "scale=640:480:force_original_aspect_ratio=decrease",
        "pad=640:480:(ow-iw)/2:(oh-ih)/2",
    ]
    if subtitle >= 0:
        video_filters.append(
            f"subtitles=filename='{_escaped_filter_path(ticket_url)}':si={subtitle}:"
            "fontsdir=/usr/share/guideos/fonts:"
            "force_style='FontName=DejaVu Sans,FontSize=18,Outline=1,Shadow=0,MarginV=16'")
    if rate == 2:
        video_filters.append("setpts=0.5*PTS")
    arguments += ["-map", "0:v:0", "-vf", ",".join(video_filters),
                  "-sws_flags", "fast_bilinear", "-filter_threads", "2",
                  "-pix_fmt", "bgra"]
    if one_frame:
        return arguments + ["-frames:v", "1", "-an", "-f", "fbdev", "/dev/fb0"]
    arguments += ["-f", "fbdev", "/dev/fb0", "-map", "0:a:0?"]
    if rate == 2:
        arguments += ["-filter:a", "atempo=2.0"]
    return arguments + ["-f", "alsa", "default"]


def _stop_player(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _run_player_controller(ticket_url: str, item: dict[str, object],
                           environment: dict[str, str]) -> int:
    """Supervise FFmpeg and accept only the fixed media-control vocabulary."""
    control = MEDIA_CONTROL_DIRECTORY / f"guideos-media-control-{os.getpid()}"
    control.touch(mode=0o600, exist_ok=True)
    position = 0.0
    rate = 1
    subtitle = -1
    paused = False
    offset = 0
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()

    def launch() -> subprocess.Popen[bytes]:
        nonlocal started
        reverse = rate == -2
        arguments = _player_arguments(ticket_url, str(item["kind"]), position,
                                      1 if reverse else rate, subtitle, reverse)
        started = time.monotonic()
        child = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, env=environment)
        if paused and not reverse:
            os.kill(child.pid, signal.SIGSTOP)
        return child

    def advance() -> None:
        nonlocal position, started
        if not paused and rate > 0:
            position += max(0.0, time.monotonic() - started) * rate
        started = time.monotonic()

    try:
        process = launch()
        while True:
            time.sleep(0.05)
            commands: list[str] = []
            try:
                with control.open("r", encoding="ascii", errors="ignore") as source:
                    source.seek(offset)
                    commands = [line.strip() for line in source if line.strip()]
                    offset = source.tell()
            except OSError:
                pass
            restart = False
            for command in commands:
                if command == "stop":
                    _stop_player(process)
                    return 0
                if command == "pause" and rate != -2 and process and process.poll() is None:
                    advance()
                    paused = not paused
                    os.kill(process.pid, signal.SIGSTOP if paused else signal.SIGCONT)
                elif command in ("seek:-10", "seek:10"):
                    advance()
                    position = max(0.0, position + int(command[5:]))
                    restart = True
                elif command in ("rate:-2", "rate:2"):
                    advance()
                    requested = int(command[5:])
                    rate = 1 if rate == requested else requested
                    paused = False
                    restart = True
                elif re.fullmatch(r"subtitle:-1|subtitle:[0-7]", command):
                    advance()
                    subtitle = int(command.split(":", 1)[1])
                    restart = True
            if restart:
                _stop_player(process)
                process = launch()
                continue
            if process.poll() is not None:
                if rate == -2 and position > 0.0:
                    position = max(0.0, position - 1.0)
                    time.sleep(0.45)
                    process = launch()
                    continue
                return process.returncode or 0
    finally:
        _stop_player(process)
        try:
            control.unlink()
        except FileNotFoundError:
            pass


def play(index_text: str) -> int:
    """Run the bounded media controller for one selected Node item."""
    if not re.fullmatch(r"(?:0|[1-9][0-9]?)", index_text):
        raise NodeLinkError("MEDIA SELECTION IS INVALID")
    items = _load(MEDIA_FILE)
    index = int(index_text)
    if not isinstance(items, list) or index >= len(items):
        raise NodeLinkError("REFRESH THE MEDIA LIBRARY")
    item = items[index]
    if not isinstance(item, dict) or item.get("kind") not in ("audio", "video"):
        raise NodeLinkError("MEDIA ENTRY IS INVALID")
    media_id = item.get("id")
    if not isinstance(media_id, str):
        raise NodeLinkError("MEDIA ENTRY IS INVALID")
    if (not MEDIA_LOADER.is_file() or not MEDIA_FFMPEG.is_file() or
            not MEDIA_AUDIO_CONTROL.is_file()):
        raise NodeLinkError("MEDIA PLAYER IS NOT INSTALLED")
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(MEDIA_RUNTIME / "lib")
    try:
        initialized = subprocess.run(
            [str(MEDIA_LOADER), "--library-path", str(MEDIA_RUNTIME / "lib"),
             str(MEDIA_AUDIO_CONTROL), "--initialize-speaker"],
            stdin=subprocess.DEVNULL, timeout=5, check=False, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NodeLinkError("DECK AUDIO COULD NOT BE INITIALIZED") from error
    if initialized.returncode != 0:
        raise NodeLinkError("DECK AUDIO COULD NOT BE INITIALIZED")
    ticket_url = _session_client().media_ticket(media_id)
    return _run_player_controller(ticket_url, item, environment)


def unpair() -> int:
    try:
        client = _session_client()
        client.unpair()
    finally:
        try:
            SESSION_FILE.unlink()
        except FileNotFoundError:
            pass
    print("GUIDE-NODE-UNPAIRED-1")
    return 0


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    try:
        if args == ["discover"]:
            return discover()
        if len(args) == 3 and args[0] == "pair":
            return pair(args[1], args[2])
        if args == ["status"]:
            return status()
        if args == ["media"]:
            return media()
        if len(args) == 2 and args[0] == "play":
            return play(args[1])
        if args == ["unpair"]:
            return unpair()
        if args == ["trust"]:
            return trust()
        if args == ["untrust"]:
            return untrust()
        raise NodeLinkError("USE DISCOVER, PAIR, TRUST, MEDIA, PLAY, STATUS, OR UNPAIR")
    except (NodeLinkError, OSError, ValueError, json.JSONDecodeError) as error:
        print("ERROR=" + _safe_text(error, 120).upper())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
