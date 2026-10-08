#!/usr/bin/env python3
"""Generate the fixed prototype textures and a 640x480 BMP preview."""

from __future__ import annotations

import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
PREVIEW = HERE / "preview"
TW, TH = 1024, 512
CW, CH = 2048, 512


def periodic_delta(x: float, center: float, width: float) -> float:
    delta = abs(x - center)
    return min(delta, width - delta)


def ellipse(x: float, y: float, cx: float, cy: float, rx: float, ry: float, width: float) -> float:
    dx = periodic_delta(x, cx, width) / rx
    dy = (y - cy) / ry
    return 1.0 - dx * dx - dy * dy


def hash_noise(x: int, y: int, salt: int = 0) -> float:
    value = (x * 0x1F123BB5) ^ (y * 0x5F356495) ^ salt
    value ^= value >> 15
    value = (value * 0x2C1B3C6D) & 0xFFFFFFFF
    value ^= value >> 12
    return (value & 0xFFFF) / 65535.0


def terrain_pixel(x: int, y: int) -> tuple[int, int, int]:
    nx = float(x)
    ny = float(y)
    latitude = abs((y / (TH - 1)) * 2.0 - 1.0)
    broad_noise = hash_noise(x // 20, y // 16, 17)

    north_edge = 74.0 + 20.0 * math.sin(x * math.tau / TW) + 9.0 * math.sin(x * 5.0 * math.tau / TW)
    south_edge = TH - 1 - (66.0 + 17.0 * math.sin((x + 190) * math.tau / TW) + 8.0 * math.sin(x * 4.0 * math.tau / TW))
    polar_land = y < north_edge or y > south_edge

    fields = (
        ellipse(nx, ny, 150, 210, 118, 74, TW),
        ellipse(nx, ny, 258, 240, 92, 58, TW),
        ellipse(nx, ny, 470, 312, 145, 82, TW),
        ellipse(nx, ny, 595, 285, 86, 58, TW),
        ellipse(nx, ny, 770, 185, 136, 78, TW),
        ellipse(nx, ny, 890, 225, 102, 65, TW),
    )
    continent = max(fields)
    land = polar_land or continent + (broad_noise - 0.5) * 0.10 > 0.08

    depth = 0.45 + 0.22 * (1.0 - latitude) + 0.05 * math.sin(x * math.tau / TW)
    if not land:
        coast = max(continent, 1.0 - abs(y - north_edge) / 18.0, 1.0 - abs(y - south_edge) / 18.0)
        if coast > 0.80:
            return (38, 159, 205)
        return (15, int(94 + 42 * depth), int(151 + 62 * depth))

    snow = y < north_edge * 0.43 or y > TH - (TH - south_edge) * 0.43
    if snow:
        return (225, 240, 238)
    elevation = 0.58 * hash_noise(x // 9, y // 9, 991) + 0.42 * hash_noise(x // 27, y // 24, 301)
    arid = 0.5 + 0.5 * math.sin((x * 0.019) + (y * 0.011))
    if elevation > 0.75:
        return (122, 126, 112)
    if arid > 0.73 and latitude < 0.58:
        return (198, 166, 93)
    if latitude > 0.66:
        return (92, 139, 108)
    if elevation > 0.55:
        return (52, 115, 76)
    return (83, 151, 85)


CLOUDS = (
    (110, 125, 115, 24, 208), (228, 145, 92, 20, 178),
    (405, 255, 150, 34, 225), (562, 234, 84, 19, 165),
    (720, 365, 142, 30, 212), (915, 110, 115, 26, 190),
    (1090, 320, 155, 36, 220), (1280, 180, 130, 27, 198),
    (1475, 390, 120, 23, 180), (1650, 245, 170, 35, 216),
    (1870, 105, 145, 29, 205), (2000, 330, 105, 25, 185),
)


def cloud_pixel(x: int, y: int) -> int:
    value = 0.0
    for cx, cy, rx, ry, alpha in CLOUDS:
        dx = periodic_delta(x, cx, CW) / rx
        dy = (y - cy) / ry
        d = dx * dx + dy * dy
        if d < 1.0:
            softness = (1.0 - d) ** 1.8
            ripple = 0.84 + 0.16 * math.sin(x * 0.071 + y * 0.043)
            value = max(value, alpha * softness * ripple)
    return max(0, min(235, int(value)))


def rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def write_assets() -> tuple[list[tuple[int, int, int]], bytearray]:
    ASSETS.mkdir(exist_ok=True)
    terrain = [terrain_pixel(x, y) for y in range(TH) for x in range(TW)]
    with (ASSETS / "terrain-fixed.rgb565").open("wb") as stream:
        for color in terrain:
            stream.write(struct.pack("<H", rgb565(*color)))

    clouds = bytearray(cloud_pixel(x, y) for y in range(CH) for x in range(CW))
    (ASSETS / "clouds-fixed.r8").write_bytes(clouds)
    return terrain, clouds


def sample_terrain(data: list[tuple[int, int, int]], u: float, v: float) -> tuple[int, int, int]:
    x = int((u % 1.0) * TW) % TW
    y = min(TH - 1, max(0, int(v * TH)))
    return data[y * TW + x]


def sample_cloud(data: bytearray, u: float, v: float) -> int:
    x = int((u % 1.0) * CW) % CW
    y = min(CH - 1, max(0, int(v * CH)))
    return data[y * CW + x]


def preview_pixel(px: int, py: int, terrain, clouds) -> tuple[int, int, int]:
    sx = (px - 320.0) / 160.0
    sy = (240.0 - py) / 160.0
    radius2 = sx * sx + sy * sy
    if radius2 > 1.0:
        return (2, 5, 10)
    z = math.sqrt(max(0.0, 1.0 - radius2))
    longitude = math.atan2(sx, z) / math.tau + 0.5
    latitude = math.asin(sy) / math.pi + 0.5
    rotation = 0.075
    r, g, b = sample_terrain(terrain, longitude + rotation, latitude)
    # A fixed screen-right light. These broad bands are intentionally graphic.
    light_x = sx
    day = max(0.0, min(1.0, (light_x + 0.48) / 0.78))
    transition = day * day * (3.0 - 2.0 * day)
    illumination = 0.22 + 0.78 * transition
    cloud = sample_cloud(clouds, longitude * 0.5 - 0.10, latitude) / 255.0
    r = r * illumination * (1.0 - 0.30 * cloud) + 242 * cloud * (0.32 + 0.68 * transition)
    g = g * illumination * (1.0 - 0.30 * cloud) + 249 * cloud * (0.32 + 0.68 * transition)
    b = b * illumination * (1.0 - 0.18 * cloud) + 255 * cloud * (0.38 + 0.62 * transition)
    edge = min(1.0, max(0.0, z * 5.0))
    return tuple(max(0, min(255, int(c * edge))) for c in (r, g, b))


def write_bmp(path: Path, width: int, height: int, pixels) -> None:
    row_size = (width * 3 + 3) & ~3
    image_size = row_size * height
    header = struct.pack("<2sIHHI", b"BM", 54 + image_size, 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0, image_size, 2835, 2835, 0, 0)
    with path.open("wb") as stream:
        stream.write(header + dib)
        padding = b"\0" * (row_size - width * 3)
        for y in range(height - 1, -1, -1):
            for x in range(width):
                r, g, b = pixels(x, y)
                stream.write(bytes((b, g, r)))
            stream.write(padding)


def main() -> None:
    terrain, clouds = write_assets()
    PREVIEW.mkdir(exist_ok=True)
    write_bmp(PREVIEW / "fixed-globe-preview.bmp", 640, 480,
              lambda x, y: preview_pixel(x, y, terrain, clouds))
    print("GUIDE_FIXED_BOOT_ASSETS_READY")
    print(ASSETS / "terrain-fixed.rgb565")
    print(ASSETS / "clouds-fixed.r8")
    print(PREVIEW / "fixed-globe-preview.bmp")


if __name__ == "__main__":
    main()
