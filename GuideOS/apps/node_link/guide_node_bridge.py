#!/usr/bin/env python3
"""Line-oriented bridge between the framebuffer shell and Guide Nodes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import hashlib
import fcntl
import urllib.request
from contextlib import contextmanager

from guide_node_client import NodeClient, NodeLinkError, discover_nodes, validate_node_description


CANDIDATES_FILE = Path("/run/guideos-node-candidates.json")
SESSION_FILE = Path("/run/guideos-node-session.json")
MEDIA_FILE = Path("/run/guideos-node-media.json")
LOCAL_MEDIA_FILE = Path("/run/guideos-local-media.json")
MEDIA_RESUME_FILE = Path("/var/lib/guideos/media/resume.json")
MEDIA_STATUS_FILE = Path("/run/guideos-media-status.json")
MEDIA_OWNER_FILE = Path("/run/guideos-media-player.owner")
APPLICATIONS_FILE = Path("/run/guideos-node-applications.json")
APPLICATION_SESSION_FILE = Path("/run/guideos-node-application-session.json")
DECK_ID_FILE = Path("/var/lib/guideos/node-link/deck-id")
TRUSTED_FILE = Path("/var/lib/guideos/node-link/trusted-nodes.json")
MAX_NODES = 8
MEDIA_RUNTIME = Path("/usr/lib/guideos/media")
MEDIA_LOADER = MEDIA_RUNTIME / "lib/ld-linux-aarch64.so.1"
MEDIA_FFMPEG = MEDIA_RUNTIME / "bin/ffmpeg"
MEDIA_AUDIO_CONTROL = MEDIA_RUNTIME / "bin/guide-audio-control"
MEDIA_CONTROL_DIRECTORY = Path("/run")
BLUETOOTH_STATUS = Path("/opt/guide/bluetooth/guide-bluetooth-status")
BLUETOOTH_PLUGIN_DIRECTORY = MEDIA_RUNTIME / "alsa-lib"
BLUETOOTH_ALSA_CONFIG = Path("/opt/guide/bluetooth/alsa-media.conf")
PLAYER_REOPEN_DELAY_SECONDS = 0.25
BLUETOOTH_VIDEO_DELAY_SECONDS = 2.2
MAX_SUBTITLE_BYTES = 4 * 1024 * 1024
LOCAL_MEDIA_LIMIT = 100
LOCAL_SCAN_FILE_LIMIT = 10000
LOCAL_MEDIA_ROOTS = (
    (Path("/data/guide-media"), "This Deck"),
    (Path("/media/guide-card"), "Cartridge"),
)
AUDIO_EXTENSIONS = frozenset((".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"))
VIDEO_EXTENSIONS = frozenset((".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"))
SUBTITLE_EXTENSIONS = (".srt", ".ass", ".ssa", ".vtt")


def _is_media_command(arguments: list[str]) -> bool:
    return len(arguments) == 2 and arguments[0] in ("play", "local-play")


def _isolate_media_process() -> None:
    """Keep a media controller bounded to its launcher and process group."""
    parent = os.getppid()
    try:
        os.setpgid(0, 0)
    except OSError:
        pass
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        # Linux PR_SET_PDEATHSIG: if a non-init launcher disappears, its
        # controller cannot survive as an unmanaged display/audio owner.
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            return
        if parent != 1 and os.getppid() != parent:
            os.kill(os.getpid(), signal.SIGKILL)
    except (AttributeError, OSError, ImportError):
        pass


@contextmanager
def _player_ownership():
    """Allow exactly one supervised media controller to own Deck outputs."""
    flags = (os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) |
             getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(MEDIA_OWNER_FILE, flags, 0o600)
    acquired = False
    try:
        information = os.fstat(descriptor)
        if not stat.S_ISREG(information.st_mode) or information.st_nlink != 1:
            raise NodeLinkError("PLAYER OWNERSHIP RECORD IS UNSAFE")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise NodeLinkError("ANOTHER PLAYER IS ALREADY ACTIVE") from error
        acquired = True
        os.ftruncate(descriptor, 0)
        owner = f"{os.getpid()}\n".encode("ascii")
        if os.write(descriptor, owner) != len(owner):
            raise NodeLinkError("PLAYER OWNERSHIP RECORD COULD NOT BE WRITTEN")
        os.fsync(descriptor)
        yield
    finally:
        if acquired:
            try:
                os.ftruncate(descriptor, 0)
                os.fsync(descriptor)
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        else:
            os.close(descriptor)


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


def _local_media_kind(path: Path) -> str | None:
    extension = path.suffix.lower()
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    return None


def _sidecar_subtitles(path: Path) -> list[dict[str, str]]:
    tracks: list[dict[str, str]] = []
    try:
        entries = list(path.parent.iterdir())
    except OSError:
        return tracks
    stem = path.stem.casefold()
    for candidate in sorted(entries, key=lambda value: value.name.casefold()):
        if (len(tracks) >= 8 or candidate.is_symlink() or
                candidate.suffix.lower() not in SUBTITLE_EXTENSIONS or
                not candidate.is_file()):
            continue
        candidate_stem = candidate.stem.casefold()
        if candidate_stem != stem and not candidate_stem.startswith(stem + "."):
            continue
        label = candidate.stem[len(path.stem):].lstrip(" ._-") or candidate.suffix[1:]
        tracks.append({"label": _safe_text(label, 32) or "SUBTITLES",
                       "path": str(candidate.resolve())})
    return tracks


def _local_media_records() -> tuple[list[dict[str, object]], int, bool]:
    """Build a bounded inventory without following links off the selected media."""
    records: list[dict[str, object]] = []
    recognized = 0
    visited = 0
    limited = False
    for root, library in LOCAL_MEDIA_ROOTS:
        if not root.is_dir() or root.is_symlink():
            continue
        resolved_root = root.resolve()
        for current, directories, files in os.walk(resolved_root, followlinks=False):
            directories[:] = sorted(
                (name for name in directories
                 if not name.startswith(".") and name.casefold() not in {
                     "system volume information", "$recycle.bin"}),
                key=str.casefold,
            )
            for name in sorted(files, key=str.casefold):
                visited += 1
                if visited > LOCAL_SCAN_FILE_LIMIT:
                    limited = True
                    break
                path = Path(current) / name
                kind = _local_media_kind(path)
                if kind is None or path.is_symlink():
                    continue
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(resolved_root)
                    status = resolved.stat()
                except (OSError, ValueError):
                    continue
                if not resolved.is_file():
                    continue
                recognized += 1
                if len(records) >= LOCAL_MEDIA_LIMIT:
                    limited = True
                    continue
                relative = resolved.relative_to(resolved_root)
                identity = (str(resolved_root) + "\0" + relative.as_posix() + "\0" +
                            str(status.st_size) + "\0" + str(status.st_mtime_ns))
                subtitles = _sidecar_subtitles(resolved) if kind == "video" else []
                records.append({
                    "kind": kind,
                    "name": _safe_text(relative.name, 120),
                    "size": status.st_size,
                    "library": library,
                    "folder": _safe_text(relative.parent.as_posix()
                                         if relative.parent != Path(".") else "", 160),
                    "path": str(resolved),
                    "root": str(resolved_root),
                    "mtime_ns": status.st_mtime_ns,
                    "resume_key": hashlib.blake2s(identity.encode("utf-8"),
                                                   digest_size=16).hexdigest(),
                    "sidecars": subtitles,
                })
            if visited > LOCAL_SCAN_FILE_LIMIT:
                break
        if visited > LOCAL_SCAN_FILE_LIMIT:
            break
    records.sort(key=lambda item: (str(item["library"]).casefold(),
                                   str(item["folder"]).casefold(),
                                   str(item["name"]).casefold()))
    return records, recognized, limited


def local_media() -> int:
    records, total, limited = _local_media_records()
    _atomic_private_json(LOCAL_MEDIA_FILE, records)
    print("GUIDE-LOCAL-MEDIA-1")
    print(f"TOTAL={total}")
    if limited:
        print("LIMITED=YES")
    for index, item in enumerate(records):
        print(f"MEDIA={index}\t{item['kind']}\t{item['size']}\t{item['library']}\t"
              f"{item['folder']}\t{item['name']}")
        for track, subtitle in enumerate(item.get("sidecars", [])):
            if isinstance(subtitle, dict):
                print(f"SUBTITLE={index}\t{track}\t{_safe_text(subtitle.get('label'), 32)}")
    return 0


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
            library_name = value.get("library", "Media")
            folder = value.get("folder", "")
            size = value.get("size")
            if (not isinstance(media_id, str) or not re.fullmatch(r"[0-9a-f]{32}", media_id)
                    or kind not in ("audio", "video") or not isinstance(name, str)
                    or not isinstance(size, int) or size < 0
                    or not isinstance(library_name, str) or not isinstance(folder, str)):
                continue
            source_subtitles = value.get("subtitles", [])
            subtitles = []
            if isinstance(source_subtitles, list):
                subtitles = [_safe_text(label, 32) for label in source_subtitles[:8]
                             if isinstance(label, str) and label.strip()]
            items.append({"id": media_id, "kind": kind, "name": name[:240], "size": size,
                          "library": _safe_text(library_name, 48) or "Media",
                          "folder": _safe_text(folder.replace("\\", "/"), 160),
                          "subtitles": subtitles})
    _atomic_private_json(MEDIA_FILE, items)
    print("GUIDE-MEDIA-2")
    print("TOTAL=" + str(max(0, int(library.get("count", len(items))))))
    for index, item in enumerate(items):
        print(f"MEDIA={index}\t{item['kind']}\t{item['size']}\t{item['library']}\t"
              f"{item['folder']}\t{_safe_text(item['name'], 120)}")
        for track, label in enumerate(item["subtitles"]):
            print(f"SUBTITLE={index}\t{track}\t{label}")
    return 0


def applications() -> int:
    library = _session_client().applications()
    source = library.get("items", [])
    items = []
    if isinstance(source, list):
        for value in source[:32]:
            if not isinstance(value, dict):
                continue
            app_id, name = value.get("id"), value.get("name")
            if (isinstance(app_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", app_id)
                    and isinstance(name, str)):
                items.append({"id": app_id, "name": _safe_text(name, 80),
                              "available": bool(value.get("available")),
                              "streaming_ready": bool(value.get("streaming_ready"))})
    _atomic_private_json(APPLICATIONS_FILE, items)
    print("GUIDE-APPLICATIONS-1")
    for index, item in enumerate(items):
        state = "READY" if item["available"] else "UNAVAILABLE"
        print(f"APPLICATION={index}\t{state}\t{item['name']}")
    return 0


def application_request(index_text: str) -> int:
    if not re.fullmatch(r"(?:0|[1-2]?[0-9]|3[01])", index_text):
        raise NodeLinkError("APPLICATION SELECTION IS INVALID")
    items = _load(APPLICATIONS_FILE)
    index = int(index_text)
    if not isinstance(items, list) or index >= len(items) or not isinstance(items[index], dict):
        raise NodeLinkError("REFRESH THE APPLICATION LIST")
    result = _session_client().request_application(str(items[index].get("id", "")))
    session_id = result.get("id")
    if not isinstance(session_id, str) or not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise NodeLinkError("NODE DID NOT CREATE THE APPLICATION SESSION")
    _atomic_private_json(APPLICATION_SESSION_FILE, {"id": session_id})
    print("GUIDE-APPLICATION-SESSION-1")
    print("STATE=" + _safe_text(result.get("state", "unknown")).upper())
    print("APPLICATION=" + _safe_text(result.get("application", ""), 80))
    return 0


def application_status() -> int:
    saved = _load(APPLICATION_SESSION_FILE)
    session_id = saved.get("id") if isinstance(saved, dict) else None
    if not isinstance(session_id, str):
        raise NodeLinkError("NO APPLICATION SESSION")
    result = _session_client().application_session(session_id)
    print("GUIDE-APPLICATION-SESSION-1")
    print("STATE=" + _safe_text(result.get("state", "unknown")).upper())
    if isinstance(result.get("stream_path"), str):
        print("STREAM=READY")
    if result.get("reason"):
        print("REASON=" + _safe_text(result["reason"], 100).upper())
    return 0


def application_close() -> int:
    saved = _load(APPLICATION_SESSION_FILE)
    session_id = saved.get("id") if isinstance(saved, dict) else None
    if not isinstance(session_id, str):
        raise NodeLinkError("NO APPLICATION SESSION")
    _session_client().close_application(session_id)
    try:
        APPLICATION_SESSION_FILE.unlink()
    except FileNotFoundError:
        pass
    print("GUIDE-APPLICATION-CLOSED-1")
    return 0


def application_play() -> int:
    saved = _load(APPLICATION_SESSION_FILE)
    session_id = saved.get("id") if isinstance(saved, dict) else None
    if not isinstance(session_id, str):
        raise NodeLinkError("NO APPLICATION SESSION")
    if not MEDIA_LOADER.is_file() or not MEDIA_FFMPEG.is_file():
        raise NodeLinkError("STREAM PLAYER IS NOT INSTALLED")
    client = _session_client()
    url, authorization = client.application_stream(session_id)
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(MEDIA_RUNTIME / "lib")
    arguments = [
        str(MEDIA_LOADER), "--library-path", str(MEDIA_RUNTIME / "lib"),
        str(MEDIA_FFMPEG), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-fflags", "nobuffer", "-flags", "low_delay", "-probesize", "65536",
        "-analyzeduration", "250000", "-headers", authorization, "-i", url,
        "-vf", "scale=640:480:force_original_aspect_ratio=decrease,"
               "pad=640:480:(ow-iw)/2:(oh-ih)/2",
        "-an", "-pix_fmt", "bgra", "-f", "fbdev", "/dev/fb0",
    ]
    return subprocess.run(arguments, stdin=subprocess.DEVNULL,
                          env=environment, check=False).returncode


def _escaped_filter_path(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _audio_output(environment: dict[str, str]) -> tuple[str, bool]:
    """Choose a connected A2DP device, with the Deck speaker as fallback."""
    if BLUETOOTH_STATUS.is_file():
        try:
            result = subprocess.run(
                [str(BLUETOOTH_STATUS)], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=4, check=False,
            )
            values = dict(line.split("=", 1) for line in result.stdout.splitlines()
                          if "=" in line)
            target = values.get("ALSA", "")
            if (result.returncode == 0 and values.get("CONNECTED") == "YES" and
                    re.fullmatch(r"bluealsa:DEV=[0-9A-Fa-f:]{17},PROFILE=a2dp", target)):
                if (BLUETOOTH_PLUGIN_DIRECTORY.is_dir() and
                        BLUETOOTH_ALSA_CONFIG.is_file()):
                    environment["ALSA_PLUGIN_DIR"] = str(BLUETOOTH_PLUGIN_DIRECTORY)
                    environment["ALSA_CONFIG_PATH"] = str(BLUETOOTH_ALSA_CONFIG)
                    return target, True
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    return "default", False


def _player_arguments(source: str, kind: str, audio_output: str = "default",
                      position: float = 0.0,
                      rate: int = 1, subtitle: int = -1,
                      one_frame: bool = False, network: bool = True,
                      subtitle_path: str | None = None) -> list[str]:
    arguments = [
        str(MEDIA_LOADER), "--library-path", str(MEDIA_RUNTIME / "lib"),
        str(MEDIA_FFMPEG), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-stats", "-stats_period", "2", "-threads", "4",
        "-thread_queue_size", "1024" if network else "256",
    ]
    if network:
        arguments += ["-rw_timeout", "600000000", "-reconnect", "1",
                      "-reconnect_streamed", "1", "-reconnect_delay_max", "2"]
    if position > 0.01:
        arguments += ["-ss", f"{position:.3f}"]
    if not one_frame:
        # The framebuffer has no presentation clock of its own. Feed it at the
        # media clock from the first frame; an initial unpaced burst makes video
        # run ahead while ALSA is still filling its buffer.
        arguments += ["-readrate", "2" if rate == 2 else "1"]
    arguments += ["-i", source]
    if kind == "audio":
        if rate == 2:
            arguments += ["-filter:a", "atempo=2.0"]
        return arguments + ["-vn", "-f", "alsa", audio_output]
    video_filters = [
        "scale=640:480:force_original_aspect_ratio=decrease",
        "pad=640:480:(ow-iw)/2:(oh-ih)/2",
    ]
    if subtitle >= 0:
        subtitle_source = subtitle_path or source
        stream_selector = "" if subtitle_path else f":si={subtitle}"
        video_filters.append(
            f"subtitles=filename='{_escaped_filter_path(subtitle_source)}'{stream_selector}:"
            "fontsdir=/usr/share/guideos/fonts:"
            "force_style='FontName=DejaVu Sans,FontSize=18,Outline=1,Shadow=0,MarginV=16'")
    if audio_output != "default":
        # Consumer Bluetooth earbuds buffer audio internally. BlueALSA cannot
        # observe that delay, so hold the first video frame while the earbud's
        # buffer fills. This stays inside the supervised player process.
        video_filters.append(
            f"tpad=start_mode=clone:start_duration={BLUETOOTH_VIDEO_DELAY_SECONDS:.3f}")
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
    return arguments + ["-f", "alsa", audio_output]


def _stop_player(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    # FFmpeg's graceful shutdown can drain queued PCM after the UI has already
    # returned. Closing it immediately discards speaker/BlueALSA buffers and is
    # safe because GuideOS never asks this process to write a media file.
    process.kill()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        # A process stuck in an uninterruptible kernel wait must never hold the
        # Guide interface or shutdown path hostage.
        return


def _read_control_commands(control: Path, offset: int) -> tuple[list[str], int]:
    """Consume each appended media command exactly once."""
    try:
        with control.open("r", encoding="ascii", errors="ignore") as source:
            source.seek(offset)
            chunk = source.read()
            next_offset = source.tell()
    except OSError:
        return [], offset
    return [line.strip() for line in chunk.splitlines() if line.strip()], next_offset


def _write_player_control_state(state_path: Path, state: str) -> None:
    """Publish a tiny acknowledgement after output ownership has changed."""
    if state not in ("starting", "playing", "paused", "stopped"):
        return
    flags = (os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
             getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(state_path, flags, 0o600)
    try:
        os.write(descriptor, (state + "\n").encode("ascii"))
    finally:
        os.close(descriptor)


def _resume_positions() -> dict[str, float]:
    try:
        value = _load(MEDIA_RESUME_FILE)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, position in value.items():
        if (isinstance(key, str) and re.fullmatch(r"[0-9a-f]{32}", key) and
                isinstance(position, (int, float)) and 0.0 <= float(position) <= 604800.0):
            result[key] = float(position)
    return result


def _store_resume_position(key: str | None, position: float | None) -> None:
    if not key or not re.fullmatch(r"[0-9a-f]{32}", key):
        return
    positions = _resume_positions()
    if position is None or position < 3.0:
        positions.pop(key, None)
    else:
        positions[key] = round(min(position, 604800.0), 1)
    _atomic_private_json(MEDIA_RESUME_FILE, positions)


def _write_media_status(state: str, item: dict[str, object], network: bool,
                        position: float, rate: int, subtitle: int,
                        audio_output: str, return_code: int | None = None) -> None:
    """Leave a secret-free diagnostic breadcrumb for the active/recent player."""
    value: dict[str, object] = {
        "protocol": "guide-media-status/1",
        "state": state,
        "source": "node" if network else "local",
        "kind": str(item.get("kind", "unknown"))[:8],
        "name": _safe_text(item.get("name", "unnamed"), 120),
        "position_seconds": round(max(0.0, position), 1),
        "rate": rate,
        "subtitle": subtitle,
        "audio_output": "bluetooth" if audio_output != "default" else "speaker",
        "bluetooth_video_delay_seconds": (
            BLUETOOTH_VIDEO_DELAY_SECONDS
            if str(item.get("kind")) == "video" and audio_output != "default" else 0.0),
        "updated_monotonic_seconds": round(time.monotonic(), 1),
    }
    if return_code is not None:
        value["return_code"] = return_code
    try:
        _atomic_private_json(MEDIA_STATUS_FILE, value)
    except OSError:
        pass


def _cache_node_subtitle(ticket: str, node_base: str, track: int) -> str:
    """Download one Node-issued subtitle ticket into a bounded private file."""
    expected_prefix = node_base.rstrip("/") + "/guide/v1/play/"
    if not ticket.startswith(expected_prefix):
        raise NodeLinkError("NODE RETURNED AN INVALID SUBTITLE ADDRESS")
    try:
        with urllib.request.urlopen(ticket, timeout=30) as response:
            payload = response.read(MAX_SUBTITLE_BYTES + 1)
    except (OSError, ValueError) as error:
        raise NodeLinkError("NODE SUBTITLE DID NOT ANSWER") from error
    if not payload or len(payload) > MAX_SUBTITLE_BYTES or b"\x00" in payload:
        raise NodeLinkError("NODE SUBTITLE IS INVALID")
    descriptor, path = tempfile.mkstemp(
        prefix=f"guide-subtitle-{os.getpid()}-{track}-", suffix=".srt",
        dir=str(MEDIA_CONTROL_DIRECTORY))
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _played_interval(elapsed: float, startup_delay_remaining: float) -> tuple[float, float]:
    """Exclude only the unconsumed Bluetooth startup hold from resume time."""
    elapsed = max(0.0, elapsed)
    delay = max(0.0, startup_delay_remaining)
    return max(0.0, elapsed - delay), max(0.0, delay - elapsed)


def _run_player_controller(source: str, item: dict[str, object],
                           environment: dict[str, str], network: bool = True) -> int:
    """Supervise FFmpeg and accept only the fixed media-control vocabulary."""
    # Ownership has already been acquired, so no older control file can belong
    # to a live Guide player. Remove leftovers before creating this session.
    for stale_control in MEDIA_CONTROL_DIRECTORY.glob("guideos-media-control-*"):
        try:
            stale_control.unlink()
        except OSError:
            pass
    control = MEDIA_CONTROL_DIRECTORY / f"guideos-media-control-{os.getpid()}"
    control_state = control.with_name(control.name + ".state")
    control.touch(mode=0o600, exist_ok=True)
    _write_player_control_state(control_state, "starting")
    resume_key = item.get("resume_key")
    if not isinstance(resume_key, str):
        resume_key = None
    position = _resume_positions().get(resume_key, 0.0) if resume_key else 0.0
    rate = 1
    subtitle = -1
    paused = False
    offset = 0
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    startup_delay_remaining = 0.0
    audio_output, _ = _audio_output(environment)
    bluetooth_fallback_used = False
    subtitle_sources: dict[int, str] = {}
    last_resume_save = started
    stop_requested = False
    previous_handlers: dict[int, object] = {}

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        nonlocal stop_requested
        stop_requested = True

    for watched_signal in (signal.SIGTERM, signal.SIGHUP):
        previous_handlers[watched_signal] = signal.signal(watched_signal, request_stop)
    _write_media_status("starting", item, network, position, rate, subtitle,
                        audio_output)

    def launch() -> subprocess.Popen[bytes]:
        nonlocal started, startup_delay_remaining
        reverse = rate == -2
        subtitle_path = subtitle_sources.get(subtitle) if network else None
        sidecars = item.get("sidecars")
        if (not network and subtitle >= 0 and isinstance(sidecars, list) and
                subtitle < len(sidecars) and isinstance(sidecars[subtitle], dict)):
            value = sidecars[subtitle].get("path")
            if isinstance(value, str):
                subtitle_path = value
        arguments = _player_arguments(source, str(item["kind"]), audio_output, position,
                                      1 if reverse else rate, subtitle, reverse,
                                      network, subtitle_path)
        started = time.monotonic()
        startup_delay_remaining = (BLUETOOTH_VIDEO_DELAY_SECONDS
                                   if str(item["kind"]) == "video" and
                                   audio_output != "default" and not reverse else 0.0)
        child = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, env=environment)
        _write_player_control_state(control_state, "playing")
        _write_media_status("playing", item, network, position, rate, subtitle,
                            audio_output)
        return child

    def reopen_player() -> subprocess.Popen[bytes] | None:
        """Close an output completely before reopening it at the new position."""
        nonlocal process
        had_player = process is not None and process.poll() is None
        _stop_player(process)
        process = None
        if paused:
            _write_player_control_state(control_state, "paused")
            print("GUIDE MEDIA CONTROL: held at requested position", file=sys.stderr,
                  flush=True)
            return None
        if had_player:
            time.sleep(PLAYER_REOPEN_DELAY_SECONDS)
        print(f"GUIDE MEDIA CONTROL: reopen position={position:.2f} rate={rate} "
              f"subtitle={subtitle}", file=sys.stderr, flush=True)
        return launch()

    def advance() -> None:
        nonlocal position, started, startup_delay_remaining
        if not paused and rate > 0:
            now = time.monotonic()
            elapsed = max(0.0, now - started)
            played, startup_delay_remaining = _played_interval(
                elapsed, startup_delay_remaining)
            position += played * rate
            started = now
        else:
            started = time.monotonic()

    try:
        process = launch()
        while True:
            time.sleep(0.05)
            if stop_requested:
                advance()
                _store_resume_position(resume_key, position)
                _write_media_status("stopped", item, network, position, rate,
                                    subtitle, audio_output, 0)
                _write_player_control_state(control_state, "stopped")
                return 0
            commands, offset = _read_control_commands(control, offset)
            restart = False
            for command in commands:
                print(f"GUIDE MEDIA CONTROL: received {command}", file=sys.stderr,
                      flush=True)
                if command == "stop":
                    advance()
                    _store_resume_position(resume_key, position)
                    _write_media_status("stopped", item, network, position, rate,
                                        subtitle, audio_output, 0)
                    _stop_player(process)
                    _write_player_control_state(control_state, "stopped")
                    return 0
                if command == "pause" and rate != -2:
                    if paused:
                        paused = False
                        print(f"GUIDE MEDIA CONTROL: resume position={position:.2f}",
                              file=sys.stderr, flush=True)
                        # A subtitle/rate/seek command in the same input batch
                        # already requires one reopen. Do not briefly launch an
                        # obsolete pipeline and immediately kill it again.
                        process = None if restart else launch()
                    elif process and process.poll() is None:
                        advance()
                        _store_resume_position(resume_key, position)
                        paused = True
                        _stop_player(process)
                        process = None
                        _write_player_control_state(control_state, "paused")
                        print(f"GUIDE MEDIA CONTROL: paused position={position:.2f}",
                              file=sys.stderr, flush=True)
                        _write_media_status("paused", item, network, position, rate,
                                            subtitle, audio_output)
                elif command in ("seek:-10", "seek:10"):
                    advance()
                    position = max(0.0, position + int(command[5:]))
                    _store_resume_position(resume_key, position)
                    _write_media_status("seeking", item, network, position, rate,
                                        subtitle, audio_output)
                    restart = True
                elif command in ("rate:-2", "rate:2"):
                    advance()
                    requested = int(command[5:])
                    rate = 1 if rate == requested else requested
                    paused = False
                    restart = True
                elif re.fullmatch(r"subtitle:-1|subtitle:[0-7]", command):
                    advance()
                    requested_subtitle = int(command.split(":", 1)[1])
                    if network and requested_subtitle >= 0:
                        media_id = item.get("id")
                        try:
                            if not isinstance(media_id, str):
                                raise NodeLinkError("MEDIA ENTRY IS INVALID")
                            client = _session_client()
                            ticket = client.media_subtitle_ticket(
                                media_id, requested_subtitle)
                            old_subtitle = subtitle_sources.pop(
                                requested_subtitle, None)
                            if old_subtitle:
                                try:
                                    os.unlink(old_subtitle)
                                except OSError:
                                    pass
                            subtitle_sources[requested_subtitle] = (
                                _cache_node_subtitle(ticket, client.base,
                                                     requested_subtitle))
                        except (NodeLinkError, OSError) as error:
                            print(f"GUIDE MEDIA CONTROL: subtitle unavailable: {error}",
                                  file=sys.stderr, flush=True)
                            continue
                    subtitle = requested_subtitle
                    restart = True
            if restart:
                process = reopen_player()
                continue
            if (resume_key and process is not None and process.poll() is None and
                    time.monotonic() - last_resume_save >= 10.0):
                advance()
                _store_resume_position(resume_key, position)
                last_resume_save = time.monotonic()
            if process is not None and process.poll() is not None:
                if rate == -2 and position > 0.0:
                    position = max(0.0, position - 1.0)
                    time.sleep(0.45)
                    process = launch()
                    continue
                if audio_output != "default" and not bluetooth_fallback_used:
                    # A connected earbud can vanish at any instant. Retry the
                    # same item once on the already prepared internal speaker.
                    advance()
                    audio_output = "default"
                    bluetooth_fallback_used = True
                    process = launch()
                    continue
                result = process.returncode or 0
                if result == 0:
                    _store_resume_position(resume_key, None)
                    _write_media_status("complete", item, network, position, rate,
                                        subtitle, audio_output, result)
                else:
                    advance()
                    _store_resume_position(resume_key, position)
                    _write_media_status("error", item, network, position, rate,
                                        subtitle, audio_output, result)
                return result
    finally:
        _stop_player(process)
        for subtitle_path in subtitle_sources.values():
            try:
                os.unlink(subtitle_path)
            except OSError:
                pass
        for watched_signal, previous_handler in previous_handlers.items():
            signal.signal(watched_signal, previous_handler)
        try:
            control.unlink()
        except FileNotFoundError:
            pass
        try:
            control_state.unlink()
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
    # Keep the fallback prepared even when Bluetooth is currently connected;
    # an earbud may disappear between route selection and decoder startup.
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
    with _player_ownership():
        return _run_player_controller(ticket_url, item, environment)


def _local_media_record(index_text: str) -> dict[str, object]:
    if not re.fullmatch(r"(?:0|[1-9][0-9]?)", index_text):
        raise NodeLinkError("LOCAL MEDIA SELECTION IS INVALID")
    items = _load(LOCAL_MEDIA_FILE)
    index = int(index_text)
    if not isinstance(items, list) or index >= len(items):
        raise NodeLinkError("REFRESH THE LOCAL MEDIA LIBRARY")
    item = items[index]
    if not isinstance(item, dict) or item.get("kind") not in ("audio", "video"):
        raise NodeLinkError("LOCAL MEDIA ENTRY IS INVALID")
    path_value, root_value = item.get("path"), item.get("root")
    if not isinstance(path_value, str) or not isinstance(root_value, str):
        raise NodeLinkError("LOCAL MEDIA ENTRY IS INVALID")
    path, root = Path(path_value), Path(root_value)
    try:
        if path.is_symlink() or root.is_symlink():
            raise NodeLinkError("LOCAL MEDIA LINK IS NOT ALLOWED")
        resolved, resolved_root = path.resolve(strict=True), root.resolve(strict=True)
        resolved.relative_to(resolved_root)
        status = resolved.stat()
    except (OSError, ValueError) as error:
        raise NodeLinkError("LOCAL MEDIA IS NO LONGER AVAILABLE") from error
    if (not resolved.is_file() or status.st_size != item.get("size") or
            status.st_mtime_ns != item.get("mtime_ns")):
        raise NodeLinkError("LOCAL MEDIA CHANGED; REFRESH THE LIBRARY")
    item["path"] = str(resolved)
    checked_sidecars = []
    sidecars = item.get("sidecars")
    if isinstance(sidecars, list):
        for sidecar in sidecars[:8]:
            if not isinstance(sidecar, dict) or not isinstance(sidecar.get("path"), str):
                continue
            candidate = Path(sidecar["path"])
            try:
                if candidate.is_symlink():
                    continue
                checked = candidate.resolve(strict=True)
                checked.relative_to(resolved_root)
            except (OSError, ValueError):
                continue
            if checked.is_file():
                checked_sidecars.append({"label": _safe_text(sidecar.get("label"), 32),
                                         "path": str(checked)})
    item["sidecars"] = checked_sidecars
    return item


def local_play(index_text: str) -> int:
    item = _local_media_record(index_text)
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
    with _player_ownership():
        return _run_player_controller(str(item["path"]), item, environment, network=False)


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
        if _is_media_command(args):
            _isolate_media_process()
        if args == ["discover"]:
            return discover()
        if len(args) == 3 and args[0] == "pair":
            return pair(args[1], args[2])
        if args == ["status"]:
            return status()
        if args == ["media"]:
            return media()
        if args == ["local-media"]:
            return local_media()
        if args == ["applications"]:
            return applications()
        if len(args) == 2 and args[0] == "application-request":
            return application_request(args[1])
        if args == ["application-status"]:
            return application_status()
        if args == ["application-close"]:
            return application_close()
        if args == ["application-play"]:
            return application_play()
        if len(args) == 2 and args[0] == "play":
            return play(args[1])
        if len(args) == 2 and args[0] == "local-play":
            return local_play(args[1])
        if args == ["unpair"]:
            return unpair()
        if args == ["trust"]:
            return trust()
        if args == ["untrust"]:
            return untrust()
        raise NodeLinkError("UNKNOWN DECK-NODE REQUEST")
    except (NodeLinkError, OSError, ValueError, json.JSONDecodeError) as error:
        print("ERROR=" + _safe_text(error, 120).upper())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
