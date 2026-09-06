"""Read-only detection for a future Node-hosted Android provider."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


def _first_existing(candidates: list[Path | None]) -> Path | None:
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def _command_path(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


class AndroidProviderDetector:
    """Find installed tools without installing, starting, or modifying Android."""

    def __init__(self) -> None:
        roots: list[Path] = []
        for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
            value = os.environ.get(variable)
            if value:
                roots.append(Path(value))
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            roots.append(Path(local_app_data) / "Android" / "Sdk")

        adb_candidates: list[Path | None] = [_command_path("adb")]
        emulator_candidates: list[Path | None] = [_command_path("emulator")]
        for root in roots:
            adb_candidates.extend([root / "platform-tools" / "adb.exe", root / "platform-tools" / "adb"])
            emulator_candidates.extend([root / "emulator" / "emulator.exe", root / "emulator" / "emulator"])

        self.adb = _first_existing(adb_candidates)
        self.emulator = _first_existing(emulator_candidates)
        self.scrcpy = _first_existing([_command_path("scrcpy")])

    def virtual_devices(self) -> list[str]:
        if not self.emulator:
            return []
        try:
            result = subprocess.run(
                [str(self.emulator), "-list-avds"],
                capture_output=True, text=True, timeout=5, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return [line.strip()[:128] for line in result.stdout.splitlines() if line.strip()]

    def status(self) -> dict[str, object]:
        avds = self.virtual_devices()
        tools_found = {
            "android_debug_bridge": self.adb is not None,
            "android_emulator": self.emulator is not None,
            "scrcpy": self.scrcpy is not None,
        }
        return {
            "available": False,
            "state": "detected-not-enabled" if self.adb and self.emulator else "not-installed",
            "reason": (
                "Android tools were found, but remote application sessions are not enabled yet"
                if self.adb and self.emulator
                else "Android SDK emulator tools are not installed on this Node"
            ),
            "tools_found": tools_found,
            "virtual_devices": avds,
        }
