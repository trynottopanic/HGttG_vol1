#!/usr/bin/env python3
"""Bounded, secret-free GuideOS diagnostics for an authorized Developer Link."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


PROTOCOL = "guide-diagnostics/1"
REPORT_DIRECTORY = Path("/data/guide-diagnostics")
TEXT_REPORT = REPORT_DIRECTORY / "latest.txt"
JSON_REPORT = REPORT_DIRECTORY / "latest.json"
MEDIA_STATUS = Path("/run/guideos-media-status.json")
MEDIA_OWNER = Path("/run/guideos-media-player.owner")
MEDIA_RUNTIME = Path("/usr/lib/guideos/media")
SHELL_LOG = Path("/guide-framebuffer-diagnostics.txt")
MEDIA_LOG = Path("/var/log/guide-media.log")
MAX_COMMAND_BYTES = 64 * 1024
MAX_LOG_BYTES = 48 * 1024

SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|psk|token|secret|authorization|private[_ -]?key)"
    r"\s*[:=]\s*([^\s,;]+)"
)
MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
MEDIA_PATH_PATTERN = re.compile(
    r"(?i)(?:/media/guide-card|/data/guide-media)(?:/[^\s'\"]+)+"
)


def redact(value: object) -> str:
    text = str(value).replace("\x00", "?")
    text = SECRET_PATTERN.sub(lambda match: match.group(1) + "=[REDACTED]", text)
    text = MAC_PATTERN.sub("[MAC REDACTED]", text)
    text = MEDIA_PATH_PATTERN.sub("[MEDIA PATH REDACTED]", text)
    return text


def read_text(path: Path, maximum: int = 8192, tail: bool = False) -> str:
    try:
        with path.open("rb") as source:
            if tail:
                source.seek(0, os.SEEK_END)
                length = source.tell()
                source.seek(max(0, length - maximum))
            data = source.read(maximum + 1)
    except OSError as error:
        return "UNAVAILABLE: " + redact(error)
    clipped = len(data) > maximum
    text = data[:maximum].decode("utf-8", errors="replace")
    if tail and clipped:
        text = text.split("\n", 1)[-1]
    return redact(text.rstrip()) + ("\n[OUTPUT CLIPPED]" if clipped else "")


def run_command(arguments: list[str], timeout: float = 6.0,
                maximum: int = MAX_COMMAND_BYTES) -> dict[str, object]:
    try:
        result = subprocess.run(
            arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
        output = result.stdout[:maximum].decode("utf-8", errors="replace")
        return {
            "return_code": result.returncode,
            "output": redact(output.rstrip()),
            "clipped": len(result.stdout) > maximum,
        }
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b""
        return {"return_code": None, "output": redact(output[:maximum]),
                "timed_out": True}
    except OSError as error:
        return {"return_code": None, "output": "UNAVAILABLE: " + redact(error)}


def first_existing(*paths: str) -> str | None:
    for path in paths:
        if Path(path).is_file() and os.access(path, os.X_OK):
            return path
    return None


def hash_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        return "UNAVAILABLE: " + redact(error)


def sysfs_values(directory: Path, names: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for name in names:
        path = directory / name
        if path.is_file():
            result[name] = read_text(path, 512)
    return result


def collect_system() -> dict[str, object]:
    uname = platform.uname()
    result: dict[str, object] = {
        "protocol": PROTOCOL,
        "generated_epoch": int(time.time()),
        "machine": uname.machine,
        "kernel_release": uname.release,
        "kernel_version": uname.version,
        "python": platform.python_version(),
        "pid": os.getpid(),
    }
    try:
        result["uptime_seconds"] = round(float(read_text(Path("/proc/uptime"), 128).split()[0]), 1)
    except (ValueError, IndexError):
        result["uptime_seconds"] = None
    result["load_average"] = read_text(Path("/proc/loadavg"), 256)
    memory = {}
    for line in read_text(Path("/proc/meminfo"), 8192).splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"MemTotal", "MemAvailable", "Buffers", "Cached", "SwapTotal",
                                 "SwapFree", "Dirty", "Writeback"}:
            memory[key] = value.strip()
    result["memory"] = memory
    result["init_sha256"] = hash_file(Path("/init"))
    return result


def collect_power() -> dict[str, object]:
    power = {}
    for name in sorted(glob.glob("/sys/class/power_supply/*")):
        directory = Path(name)
        power[directory.name] = sysfs_values(
            directory, ("type", "present", "online", "status", "health", "capacity",
                        "voltage_now", "current_now", "temp"))
    thermal = {}
    for name in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
        directory = Path(name)
        thermal[directory.name] = sysfs_values(directory, ("type", "temp", "mode"))
    return {"power_supplies": power, "thermal_zones": thermal}


def collect_storage() -> dict[str, object]:
    devices = {}
    for name in sorted(glob.glob("/sys/class/block/mmcblk*")):
        directory = Path(name)
        devices[directory.name] = sysfs_values(
            directory, ("size", "ro", "removable", "partition", "start"))
    space = {}
    for name, path in (("root", Path("/")), ("deck_media", Path("/data/guide-media")),
                       ("cartridge", Path("/media/guide-card"))):
        try:
            status = os.statvfs(path)
            space[name] = {
                "available_bytes": status.f_bavail * status.f_frsize,
                "total_bytes": status.f_blocks * status.f_frsize,
                "read_only": bool(status.f_flag & getattr(os, "ST_RDONLY", 1)),
            }
        except OSError as error:
            space[name] = {"error": redact(error)}
    mounts = []
    for line in read_text(Path("/proc/mounts"), 32768).splitlines():
        fields = line.split()
        if len(fields) >= 4:
            mounts.append({"source": fields[0], "target": fields[1],
                           "filesystem": fields[2], "options": fields[3]})
    return {"block_devices": devices, "space": space, "mounts": mounts}


def collect_display_input() -> dict[str, object]:
    framebuffer = sysfs_values(
        Path("/sys/class/graphics/fb0"),
        ("name", "virtual_size", "bits_per_pixel", "stride", "blank", "mode", "modes"))
    framebuffer["device_present"] = str(Path("/dev/fb0").exists()).lower()
    input_devices = []
    for block in read_text(Path("/proc/bus/input/devices"), 32768).split("\n\n"):
        record = {}
        for line in block.splitlines():
            if line.startswith("N: Name="):
                record["name"] = line.partition("=")[2].strip('"')
            elif line.startswith("H: Handlers="):
                record["handlers"] = line.partition("=")[2]
            elif line.startswith("B: EV=") or line.startswith("B: ABS=") or line.startswith("B: KEY="):
                key, _, value = line[3:].partition("=")
                record[key.lower()] = value
        if record:
            input_devices.append(record)
    return {"framebuffer": framebuffer, "input_devices": input_devices,
            "event_nodes": sorted(glob.glob("/dev/input/event*"))}


def collect_network_bluetooth() -> dict[str, object]:
    interfaces = {}
    for name in sorted(glob.glob("/sys/class/net/*")):
        directory = Path(name)
        interfaces[directory.name] = sysfs_values(
            directory, ("operstate", "carrier", "mtu", "speed", "duplex"))
    ip = first_existing("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip", "/bin/ip")
    addresses = run_command([ip, "-o", "-4", "addr", "show"], 3.0) if ip else {
        "return_code": None, "output": "ip command unavailable"}
    modules = []
    for line in read_text(Path("/proc/modules"), 32768).splitlines():
        name = line.split(" ", 1)[0]
        if re.search(r"(?i)(8821|wifi|wlan|bluetooth|btusb|hci|drm|sun|cedrus|video)", name):
            modules.append(line)
    bluetooth_status = first_existing("/opt/guide/bluetooth/guide-bluetooth-status")
    bluetooth = run_command([bluetooth_status], 5.0) if bluetooth_status else {
        "return_code": None, "output": "Bluetooth status helper unavailable"}
    allowed = []
    for line in str(bluetooth.get("output", "")).splitlines():
        if line.startswith(("READY=", "CONNECTED=")):
            allowed.append(line)
    bluetooth["output"] = "\n".join(allowed)
    return {"interfaces": interfaces, "ipv4": addresses,
            "relevant_modules": modules, "bluetooth": bluetooth,
            "rfkill": read_text(Path("/proc/net/rfkill"), 4096)}


def collect_audio_media() -> dict[str, object]:
    audio_route = first_existing("/opt/guide/bluetooth/guide-audio-route")
    audio = {
        "cards": read_text(Path("/proc/asound/cards"), 8192),
        "pcm": read_text(Path("/proc/asound/pcm"), 8192),
        "route": run_command([audio_route], 5.0) if audio_route else {
            "return_code": None, "output": "Audio route helper unavailable"},
    }
    try:
        media_status: Any = json.loads(read_text(MEDIA_STATUS, 16384))
    except (json.JSONDecodeError, TypeError):
        media_status = {"state": "no valid player status recorded"}
    loader = MEDIA_RUNTIME / "lib/ld-linux-aarch64.so.1"
    ffmpeg = MEDIA_RUNTIME / "bin/ffmpeg"
    runtime: dict[str, object] = {
        "loader_present": loader.is_file(), "ffmpeg_present": ffmpeg.is_file(),
    }
    if loader.is_file() and ffmpeg.is_file():
        prefix = [str(loader), "--library-path", str(MEDIA_RUNTIME / "lib"), str(ffmpeg),
                  "-hide_banner"]
        runtime["version"] = run_command(prefix + ["-version"], 6.0, 8192)
        runtime["hardware_acceleration"] = run_command(prefix + ["-hwaccels"], 6.0, 8192)
        decoders = run_command(prefix + ["-decoders"], 8.0)
        decoder_lines = [line for line in str(decoders.get("output", "")).splitlines()
                         if re.search(r"(?i)\b(h264|hevc|vp8|vp9|mpeg[124]?|aac|mp3|flac|opus|vorbis|subrip|ass)\b", line)]
        runtime["relevant_decoders"] = {"return_code": decoders.get("return_code"),
                                         "output": "\n".join(decoder_lines)}
    runtime["video_devices"] = sorted(
        glob.glob("/dev/video*") + glob.glob("/dev/media*") + glob.glob("/dev/dri/*"))
    return {"audio": audio, "player_status": media_status, "media_runtime": runtime}


def collect_processes() -> list[dict[str, object]]:
    result = []
    for name in glob.glob("/proc/[0-9]*/comm"):
        path = Path(name)
        command = read_text(path, 256)
        if not re.search(r"(?i)(guide|ffmpeg|python|dropbear|bluetooth|bluealsa|wpa)", command):
            continue
        status = read_text(path.parent / "status", 8192)
        values = {}
        for line in status.splitlines():
            key, _, value = line.partition(":")
            if key in {"State", "PPid", "Threads", "VmRSS", "VmSize"}:
                values[key] = value.strip()
        result.append({"pid": int(path.parent.name), "command": command, **values})
    return sorted(result, key=lambda value: int(value["pid"]))


def collect_media_supervision() -> dict[str, object]:
    """Report bounded lifecycle evidence without revealing a media source."""
    value = read_text(MEDIA_OWNER, 64).strip()
    owner = int(value) if value.isdigit() and 1 < int(value) < 4194304 else None
    active = owner is not None and Path(f"/proc/{owner}").is_dir()
    result: dict[str, object] = {
        "owner_pid": owner,
        "owner_active": active,
        "control_files": len(glob.glob("/run/guideos-media-control-*")),
    }
    if active and owner is not None:
        result["command"] = read_text(Path(f"/proc/{owner}/comm"), 64)
        try:
            result["process_group_isolated"] = os.getpgid(owner) == owner
            result["nice"] = os.getpriority(os.PRIO_PROCESS, owner)
        except OSError as error:
            result["process_error"] = redact(error)
    return result


def collect_logs() -> dict[str, object]:
    dmesg = first_existing("/bin/dmesg", "/usr/bin/dmesg", "/sbin/dmesg")
    kernel = run_command([dmesg], 6.0, 256 * 1024) if dmesg else {
        "return_code": None, "output": "dmesg unavailable"}
    if isinstance(kernel.get("output"), str):
        kernel["output"] = "\n".join(kernel["output"].splitlines()[-160:])
    return {
        "guide_shell_tail": read_text(SHELL_LOG, MAX_LOG_BYTES, tail=True),
        "media_tail": read_text(MEDIA_LOG, MAX_LOG_BYTES, tail=True),
        "kernel_tail": kernel,
    }


def collect_checks() -> dict[str, object]:
    required = (
        "/init", "/dev/fb0", "/proc/bus/input/devices", "/usr/bin/python3",
        "/usr/lib/guideos/media/bin/ffmpeg",
        "/usr/lib/guideos/node-link/guide_node_bridge.py",
        "/usr/sbin/guide-devlink-control",
    )
    checks = {path: Path(path).exists() for path in required}
    return {"required_paths": checks,
            "overall": "ready" if all(checks.values()) else "attention needed"}


def collect_report() -> dict[str, object]:
    return {
        "system": collect_system(),
        "checks": collect_checks(),
        "power_and_temperature": collect_power(),
        "storage": collect_storage(),
        "display_and_input": collect_display_input(),
        "network_and_bluetooth": collect_network_bluetooth(),
        "audio_and_media": collect_audio_media(),
        "media_supervision": collect_media_supervision(),
        "relevant_processes": collect_processes(),
        "recent_logs": collect_logs(),
    }


def text_report(report: dict[str, object]) -> str:
    lines = ["GUIDEOS DIAGNOSTIC REPORT", "PROTOCOL=" + PROTOCOL,
             "SECRETS_AND_PRIVATE_MEDIA_PATHS=REDACTED"]
    for section, value in report.items():
        lines.extend(("", "=== " + section.replace("_", " ").upper() + " ==="))
        if isinstance(value, (dict, list)):
            lines.append(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True))
        else:
            lines.append(redact(value))
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            destination.write(content)
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


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a bounded, secret-free GuideOS diagnostic report.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--save", action="store_true",
                        help="also save latest.txt and latest.json under Deck data")
    options = parser.parse_args(arguments)
    report = collect_report()
    encoded = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    readable = text_report(report)
    if options.save:
        atomic_write(JSON_REPORT, encoded)
        atomic_write(TEXT_REPORT, readable)
    sys.stdout.write(encoded if options.json else readable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
