"""Validated, low-rate Home view of the boot-generated world.

The boot renderer remains the authority for the boot visual. This module only
retains a verified generated snapshot and renders a small software view after
the renderer releases DRM/KMS to the shell.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

TERRAIN = ("terrain-fixed-v2.rgb565", 1024, 512, 2)
CLOUDS = ("clouds-fixed-v2.r8", 2048, 512, 1)
LIGHTS = ("lights-fixed-v2.r8", 1024, 512, 1)
ROADS = ("roads-fixed-v2.r8", 1024, 512, 1)
CAPTION = ("caption-world-words.r8", 600, 24, 1)
WORLD_FILES = (TERRAIN, CLOUDS, LIGHTS, ROADS, CAPTION)
MAX_METADATA_BYTES = 8192

class WorldUnavailable(ValueError):
    """The optional generated world is missing or does not meet its contract."""

def _regular_bytes(path: Path, expected: int) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise WorldUnavailable("world file unavailable") from exc
    if not path.is_file() or path.is_symlink() or info.st_size != expected:
        raise WorldUnavailable("world file contract mismatch")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise WorldUnavailable("world file unavailable") from exc

def validate_world(directory: Path) -> dict:
    """Return bounded metadata only after validating every retained payload."""
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise WorldUnavailable("world directory unavailable")
    metadata_path = directory / "world.json"
    try:
        info = metadata_path.lstat()
        if (not metadata_path.is_file() or metadata_path.is_symlink() or
                not 1 <= info.st_size < MAX_METADATA_BYTES):
            raise WorldUnavailable("world metadata contract mismatch")
        metadata_raw = metadata_path.read_bytes()
    except OSError as exc:
        raise WorldUnavailable("world metadata unavailable") from exc
    try:
        metadata = json.loads(metadata_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorldUnavailable("world metadata is invalid") from exc
    if (not isinstance(metadata, dict) or type(metadata.get("boot")) is not int or
            not 1 <= metadata["boot"] < 2 ** 63 or
            not isinstance(metadata.get("generator"), str) or
            not isinstance(metadata.get("seed_version"), str) or
            not isinstance(metadata.get("sha256"), dict)):
        raise WorldUnavailable("world metadata contract mismatch")
    for name, width, height, channels in WORLD_FILES:
        payload = _regular_bytes(directory / name, width * height * channels)
        digest = metadata["sha256"].get(name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise WorldUnavailable("world digest unavailable")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise WorldUnavailable("world digest mismatch")
    return metadata

def publish_current(source: Path, runtime: Path) -> dict:
    """Atomically publish a verified boot-generated world for Home."""
    source, runtime = Path(source), Path(runtime)
    metadata = validate_world(source)
    try:
        relative = source.resolve(strict=True).relative_to(runtime.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise WorldUnavailable("world source is outside runtime") from exc
    if len(relative.parts) != 2 or not relative.parts[0].startswith("world-") or relative.name != "assets":
        raise WorldUnavailable("world source layout mismatch")
    current = runtime / "home-world-current.json"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=runtime, delete=False,
                                         prefix=".home-world-") as handle:
            temporary = Path(handle.name)
            json.dump({"directory": relative.as_posix(), "boot": metadata["boot"],
                       "terrain_sha256": metadata["sha256"][TERRAIN[0]]}, handle,
                      separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, current)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return metadata

def load_current(runtime: Path) -> tuple[Path, dict]:
    """Load the atomically published snapshot and revalidate it for the shell."""
    runtime = Path(runtime)
    current = runtime / "home-world-current.json"
    try:
        info = current.lstat()
        if not current.is_file() or current.is_symlink() or not 1 <= info.st_size < 512:
            raise WorldUnavailable("world pointer contract mismatch")
        pointer = json.loads(current.read_bytes())
        target = pointer["directory"]
        if (not isinstance(target, str) or Path(target).is_absolute() or
                type(pointer.get("boot")) is not int or
                not isinstance(pointer.get("terrain_sha256"), str)):
            raise WorldUnavailable("world pointer contract mismatch")
        directory = (runtime / target).resolve(strict=True)
        relative = directory.relative_to(runtime.resolve(strict=True))
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorldUnavailable("world pointer unavailable") from exc
    if len(relative.parts) != 2 or not relative.parts[0].startswith("world-") or relative.name != "assets":
        raise WorldUnavailable("world pointer layout mismatch")
    metadata = validate_world(directory)
    if metadata["boot"] != pointer["boot"] or metadata["sha256"][TERRAIN[0]] != pointer["terrain_sha256"]:
        raise WorldUnavailable("world pointer does not match payload")
    return directory, metadata
class HomeWorldRenderer:
    """Small nearest-sample globe renderer; call at a bounded, low refresh rate."""
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.metadata = validate_world(self.directory)
        self.terrain = _regular_bytes(self.directory / TERRAIN[0], TERRAIN[1] * TERRAIN[2] * TERRAIN[3])
        self.clouds = _regular_bytes(self.directory / CLOUDS[0], CLOUDS[1] * CLOUDS[2] * CLOUDS[3])
        self.lights = _regular_bytes(self.directory / LIGHTS[0], LIGHTS[1] * LIGHTS[2] * LIGHTS[3])
        self.roads = _regular_bytes(self.directory / ROADS[0], ROADS[1] * ROADS[2] * ROADS[3])

    @staticmethod
    def _terrain_pixel(raw: bytes, x: int, y: int) -> tuple[int, int, int]:
        offset = (y * TERRAIN[1] + x) * 2
        value = raw[offset] | raw[offset + 1] << 8
        return ((value >> 11 & 31) * 255 // 31, (value >> 5 & 63) * 255 // 63, (value & 31) * 255 // 31)

    def render(self, size: tuple[int, int], rotation: float, cloud_phase: float):
        """Render the same generated seed without boot captions or diagnostics.

        ``rotation`` and ``cloud_phase`` are turns, not seconds. A Home owner
        should refresh no faster than 2 Hz and cache the returned image.
        """
        from PIL import Image
        width, height = size
        if not (64 <= width <= 320 and 64 <= height <= 240):
            raise ValueError("Home world size out of bounds")
        image = Image.new("RGB", size, "#05080d")
        pixels = image.load()
        radius = min(height - 8, width - 8) / 2
        center_x, center_y = width / 2, height / 2
        rotation, cloud_phase = float(rotation) % 1.0, float(cloud_phase) % 1.0
        for y in range(max(0, round(center_y - radius)), min(height, round(center_y + radius))):
            py = (y + .5 - center_y) / radius
            for x in range(max(0, round(center_x - radius)), min(width, round(center_x + radius))):
                px = (x + .5 - center_x) / radius
                rr = px * px + py * py
                if rr >= 1:
                    continue
                z = math.sqrt(1 - rr)
                lon = math.atan2(px, z) / math.tau + .5
                lat = .5 - math.asin(py) / math.pi
                tx = int(((lon + rotation) % 1.0) * (TERRAIN[1] - 1))
                ty = min(TERRAIN[2] - 1, int(lat * (TERRAIN[2] - 1)))
                r, g, b = self._terrain_pixel(self.terrain, tx, ty)
                index = ty * TERRAIN[1] + tx
                road, light = self.roads[index], self.lights[index]
                cloud_x = int(((lon * .5 - cloud_phase * .5) % 1.0) * (CLOUDS[1] - 1))
                cloud = self.clouds[ty * CLOUDS[1] + cloud_x] / 255
                transition = max(0.0, min(1.0, (px + .48) / .78))
                transition = transition * transition * (3 - 2 * transition)
                illumination = .22 + .78 * transition
                r, g, b = r * illumination * (1 - road / 255 * .08), g * illumination * (1 - road / 255 * .08), b * illumination * (1 - road / 255 * .08)
                emission = max(light / 255, road / 255 * .30) * (1 - transition) * (1 - cloud * .78)
                r += 255 * emission; g += 207 * emission; b += 112 * emission
                blend = cloud * (.72 + .20 * transition)
                r = r * (1 - blend) + 242 * blend
                g = g * (1 - blend) + 249 * blend
                b = b * (1 - blend) + 255 * blend
                pixels[x, y] = (round(min(255, r)), round(min(255, g)), round(min(255, b)))
        return image
