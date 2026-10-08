#!/usr/bin/env python3
"""Generate fixed v2 globe layers and a 640x480 reference preview."""

from __future__ import annotations

import heapq
import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
PREVIEW = HERE / "preview"
TW, TH = 1024, 512
CW, CH = 2048, 512
MW, MH = 80, 80
CAPTION_WIDTH, CAPTION_HEIGHT = 132, 18
ROUTE_STEP = 4
COAST_CELL = 8
CLOUD_CELL_X = 16
CLOUD_CELL_Y = 8


def periodic_delta(x: float, center: float, width: float) -> float:
    delta = abs(x - center)
    return min(delta, width - delta)


def ellipse(x: float, y: float, cx: float, cy: float,
            rx: float, ry: float, width: float) -> float:
    dx = periodic_delta(x, cx, width) / rx
    dy = (y - cy) / ry
    return 1.0 - dx * dx - dy * dy


def hash_noise(x: int, y: int, salt: int = 0) -> float:
    value = (x * 0x1F123BB5) ^ (y * 0x5F356495) ^ salt
    value ^= value >> 15
    value = (value * 0x2C1B3C6D) & 0xFFFFFFFF
    value ^= value >> 12
    return (value & 0xFFFF) / 65535.0


def terrain_info(x: int, y: int) -> tuple[tuple[int, int, int], bool, bool, float]:
    # Geography is authored on a stable coarse grid, then biome/elevation
    # detail is applied at full texture resolution. This prevents accidental
    # one-pixel coastline chatter while retaining detailed terrain interiors.
    coast_x = min(TW - 1, (x // COAST_CELL) * COAST_CELL + COAST_CELL // 2)
    coast_y = min(TH - 1, (y // COAST_CELL) * COAST_CELL + COAST_CELL // 2)
    nx, ny = float(coast_x), float(coast_y)
    latitude = abs((y / (TH - 1)) * 2.0 - 1.0)
    broad_noise = hash_noise(coast_x // 32, coast_y // 24, 17)
    north_edge = 74.0 + 20.0 * math.sin(coast_x * math.tau / TW) + 9.0 * math.sin(coast_x * 5.0 * math.tau / TW)
    south_edge = TH - 1 - (66.0 + 17.0 * math.sin((coast_x + 190) * math.tau / TW) + 8.0 * math.sin(coast_x * 4.0 * math.tau / TW))
    polar_land = coast_y < north_edge or coast_y > south_edge
    fields = (
        ellipse(nx, ny, 150, 210, 118, 74, TW),
        ellipse(nx, ny, 258, 240, 92, 58, TW),
        ellipse(nx, ny, 470, 312, 145, 82, TW),
        ellipse(nx, ny, 595, 285, 86, 58, TW),
        ellipse(nx, ny, 770, 185, 136, 78, TW),
        ellipse(nx, ny, 890, 225, 102, 65, TW),
    )
    continent = max(fields)
    land = polar_land or continent + (broad_noise - 0.5) * 0.06 > 0.08
    # Interior detail is intentionally much denser than the coastline mask.
    # Several discrete scales create a hand-authored, late-16-bit-map texture
    # without softening the stepped geography boundary.
    micro = hash_noise(x // 4, y // 4, 1771)
    local = hash_noise(x // 11, y // 9, 991)
    regional = hash_noise(x // 29, y // 23, 301)
    elevation = 0.24 * micro + 0.46 * local + 0.30 * regional
    depth = 0.45 + 0.22 * (1.0 - latitude) + 0.05 * math.sin(x * math.tau / TW)
    if not land:
        coast = max(continent, 1.0 - abs(coast_y - north_edge) / 18.0,
                    1.0 - abs(coast_y - south_edge) / 18.0)
        current = 0.5 + 0.5 * math.sin(x * 0.045 + y * 0.078 + regional * 2.8)
        fleck = (micro - 0.5) * 14.0
        if coast > 0.80:
            color = (38 + int(fleck * 0.25), 159 + int(fleck * 0.55), 205 + int(fleck * 0.70))
        else:
            color = (13 + int(current * 5),
                     int(88 + 45 * depth + 10 * current + fleck * 0.35),
                     int(144 + 66 * depth + 13 * current + fleck * 0.60))
        return color, False, False, elevation

    snow = coast_y < north_edge * 0.43 or coast_y > TH - (TH - south_edge) * 0.43
    if snow:
        return (225, 240, 238), True, False, elevation
    arid = 0.5 + 0.5 * math.sin((x * 0.019) + (y * 0.011) + regional * 1.7)
    ridge = abs(0.5 - local) * 2.0
    forest = hash_noise(x // 6, y // 6, 2221)
    if elevation > 0.72 or (elevation > 0.62 and ridge > 0.82):
        highlight = 20 if micro > 0.67 else (-14 if micro < 0.31 else 0)
        color = (126 + highlight, 129 + highlight, 116 + highlight)
    elif arid > 0.73 and latitude < 0.58:
        stripe = 13 if ((x // 5 + y // 3) % 7 == 0) else 0
        color = (188 + stripe + int(micro * 12), 150 + stripe + int(local * 15), 78 + int(micro * 14))
    elif latitude > 0.66:
        color = (82 + int(micro * 20), 128 + int(local * 24), 103 + int(micro * 16))
    elif elevation > 0.53 or forest > 0.67:
        canopy = 18 if forest > 0.82 else 0
        color = (38 + int(micro * 20), 91 + canopy + int(local * 28), 60 + int(micro * 19))
    else:
        color = (68 + int(micro * 26), 136 + int(local * 29), 72 + int(micro * 24))
    return color, True, elevation < 0.80, elevation


CLOUDS = (
    (110, 125, 115, 24, 208), (228, 145, 92, 20, 178),
    (405, 255, 150, 34, 225), (562, 234, 84, 19, 165),
    (720, 365, 142, 30, 212), (915, 110, 115, 26, 190),
    (1090, 320, 155, 36, 220), (1280, 180, 130, 27, 198),
    (1475, 390, 120, 23, 180), (1650, 245, 170, 35, 216),
    (1870, 105, 145, 29, 205), (2000, 330, 105, 25, 185),
)


def cloud_pixel(x: int, y: int) -> int:
    # Compose cloud coverage in roughly 5x5 on-screen pixel cells. The cloud
    # atlas is twice the visible horizontal span, so its source cells need to
    # be twice as wide as they are tall to remain approximately square after
    # projection onto the 320-pixel globe.
    cloud_x = min(CW - 1, (x // CLOUD_CELL_X) * CLOUD_CELL_X + CLOUD_CELL_X // 2)
    cloud_y = min(CH - 1, (y // CLOUD_CELL_Y) * CLOUD_CELL_Y + CLOUD_CELL_Y // 2)
    detail_x = min(CW - 1, (x // 4) * 4 + 2)
    detail_y = min(CH - 1, (y // 4) * 4 + 2)
    value = 0.0
    for cx, cy, rx, ry, alpha in CLOUDS:
        dx = periodic_delta(cloud_x, cx, CW) / rx
        dy = (cloud_y - cy) / ry
        d = dx * dx + dy * dy
        if d < 1.0:
            softness = (1.0 - d) ** 1.8
            billow = hash_noise(detail_x // 4, detail_y // 4, 4401)
            streak = 0.5 + 0.5 * math.sin(detail_x * 0.091 + detail_y * 0.047)
            interior = 0.70 + 0.21 * billow + 0.09 * streak
            value = max(value, alpha * softness * interior)
    # A restrained alpha palette gives internal definition without gradients
    # that read as modern high-resolution blur.
    return max(0, min(235, int(round(value / 10.0) * 10)))


# x, y, radius, light intensity, hierarchy: 1 minor, 2 standard, 3 major.
SETTLEMENTS = (
    (130, 205, 15, 255, 3), (220, 230, 11, 220, 2), (290, 240, 7, 178, 1),
    (440, 310, 15, 250, 3), (530, 300, 10, 215, 2), (610, 280, 8, 185, 2),
    (750, 190, 14, 248, 3), (835, 205, 9, 210, 2), (910, 225, 14, 245, 3),
)

# start, end, road class. Each continent gets a small connected hierarchy.
ROAD_EDGES = (
    (0, 1, 3), (1, 2, 1),
    (3, 4, 2), (4, 5, 1),
    (6, 7, 2), (7, 8, 3),
)


def nearest_route_cell(x: int, y: int) -> tuple[int, int]:
    gx, gy = x // ROUTE_STEP, y // ROUTE_STEP
    gw, gh = TW // ROUTE_STEP, TH // ROUTE_STEP
    for radius in range(15):
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if radius and abs(ox) != radius and abs(oy) != radius:
                    continue
                tx, ty = (gx + ox) % gw, gy + oy
                if 0 <= ty < gh and terrain_info(tx * ROUTE_STEP + 2, ty * ROUTE_STEP + 2)[2]:
                    return tx, ty
    raise RuntimeError(f"no passable route cell near settlement {(x, y)}")


def route(start: tuple[int, int], goal: tuple[int, int], existing: bytearray) -> list[tuple[int, int]]:
    gw, gh = TW // ROUTE_STEP, TH // ROUTE_STEP
    queue: list[tuple[float, float, tuple[int, int]]] = [(0.0, 0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    cost = {start: 0.0}
    while queue:
        _, current_cost, current = heapq.heappop(queue)
        if current == goal:
            break
        if current_cost != cost.get(current):
            continue
        cx, cy = current
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = (cx + dx) % gw, cy + dy
            if ny < 0 or ny >= gh:
                continue
            px, py = nx * ROUTE_STEP + 2, ny * ROUTE_STEP + 2
            _, _, passable, elevation = terrain_info(px, py)
            if not passable and (nx, ny) not in (start, goal):
                continue
            movement = 1.414 if dx and dy else 1.0
            terrain_cost = 1.0 + elevation * 3.0
            if existing[py * TW + px]:
                terrain_cost *= 0.42
            next_cost = current_cost + movement * terrain_cost
            node = (nx, ny)
            if next_cost >= cost.get(node, float("inf")):
                continue
            cost[node] = next_cost
            came_from[node] = current
            hx = min(abs(nx - goal[0]), gw - abs(nx - goal[0]))
            hy = abs(ny - goal[1])
            heapq.heappush(queue, (next_cost + math.hypot(hx, hy), next_cost, node))
    else:
        raise RuntimeError(f"no land route from {start} to {goal}")

    path = [goal]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return [(x * ROUTE_STEP + 2, y * ROUTE_STEP + 2) for x, y in path]


def paint_disk(layer: bytearray, cx: int, cy: int, radius: int, value: int,
               land_only: bool = True) -> None:
    for oy in range(-radius, radius + 1):
        y = cy + oy
        if y < 0 or y >= TH:
            continue
        for ox in range(-radius, radius + 1):
            if ox * ox + oy * oy > radius * radius:
                continue
            x = (cx + ox) % TW
            if land_only and not terrain_info(x, y)[1]:
                continue
            index = y * TW + x
            layer[index] = max(layer[index], value)


def generate_infrastructure() -> tuple[bytearray, bytearray]:
    roads = bytearray(TW * TH)
    lights = bytearray(TW * TH)
    degree = [0] * len(SETTLEMENTS)
    anchors = [nearest_route_cell(item[0], item[1]) for item in SETTLEMENTS]
    for start_index, end_index, road_class in sorted(ROAD_EDGES, key=lambda edge: -edge[2]):
        path = route(anchors[start_index], anchors[end_index], roads)
        degree[start_index] += 1
        degree[end_index] += 1
        radius = {1: 1, 2: 2, 3: 3}[road_class]
        encoded = {1: 85, 2: 170, 3: 255}[road_class]
        for x, y in path:
            paint_disk(roads, x, y, radius, encoded)
    if any(value < 1 for value in degree):
        raise RuntimeError("a qualifying settlement has no road entry or exit")

    for index, (x, y, radius, intensity, hierarchy) in enumerate(SETTLEMENTS):
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                distance = math.hypot(ox, oy)
                if distance > radius:
                    continue
                px, py = (x + ox) % TW, y + oy
                if py < 0 or py >= TH or not terrain_info(px, py)[1]:
                    continue
                density = hash_noise(px, py, 700 + index)
                falloff = max(0.0, 1.0 - distance / max(1, radius))
                if density < 0.47 - 0.18 * falloff:
                    continue
                value = int(intensity * (0.42 + 0.58 * falloff))
                lights[py * TW + px] = max(lights[py * TW + px], value)
        paint_disk(lights, x, y, max(1, hierarchy - 1), intensity)

    for y in range(TH):
        for x in range(TW):
            road_value = roads[y * TW + x]
            if not road_value:
                continue
            spacing = {85: 13, 170: 8, 255: 5}[road_value]
            if ((x * 3 + y * 5) % spacing) <= (1 if road_value < 255 else 2):
                lights[y * TW + x] = max(lights[y * TW + x], int(road_value * 0.64))
    return roads, lights


def generate_silhouette() -> bytearray:
    mask = bytearray(MW * MH)
    center = (MW - 1) / 2.0
    radius = MW / 2.0 - 1.0
    for row_group in range(0, MH, 2):
        sample_y = min(MH - 1, row_group + 1)
        dy = sample_y - center
        half_width = math.sqrt(max(0.0, radius * radius - dy * dy))
        # Quantize the radius in two-logical-pixel increments. Combined with
        # paired rows and 4x display scaling, this creates deliberate 8x8-ish
        # step rhythms rather than a high-resolution circle with tiny aliasing.
        half_width = math.floor(half_width / 2.0) * 2.0
        left = max(0, math.ceil(center - half_width))
        right = min(MW - 1, math.floor(center + half_width))
        for y in range(row_group, min(MH, row_group + 2)):
            for x in range(left, right + 1):
                mask[y * MW + x] = 255
    return mask


def rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def write_if_changed(path: Path, data: bytes | bytearray) -> None:
    """Avoid reopening unchanged staged assets that another process may map."""
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def write_assets():
    ASSETS.mkdir(exist_ok=True)
    terrain = [terrain_info(x, y)[0] for y in range(TH) for x in range(TW)]
    terrain_bytes = b"".join(struct.pack("<H", rgb565(*color)) for color in terrain)
    write_if_changed(ASSETS / "terrain-fixed-v2.rgb565", terrain_bytes)
    clouds = bytearray(cloud_pixel(x, y) for y in range(CH) for x in range(CW))
    roads, lights = generate_infrastructure()
    mask = generate_silhouette()
    caption_path = ASSETS / "caption-dont-panic-v3.r8"
    caption = caption_path.read_bytes()
    if len(caption) != CAPTION_WIDTH * CAPTION_HEIGHT:
        raise RuntimeError("run generate_caption_font.ps1 before generating the v2 preview")
    write_if_changed(ASSETS / "clouds-fixed-v2.r8", clouds)
    write_if_changed(ASSETS / "roads-fixed-v2.r8", roads)
    write_if_changed(ASSETS / "lights-fixed-v2.r8", lights)
    write_if_changed(ASSETS / "silhouette-standard-v3.r8", mask)
    return terrain, clouds, roads, lights, mask, caption


def sample(data, width: int, height: int, u: float, v: float) -> int:
    x = int((u % 1.0) * width) % width
    y = min(height - 1, max(0, int(v * height)))
    return data[y * width + x]


def preview_pixel(px: int, py: int, terrain, clouds, roads, lights, mask, caption) -> tuple[int, int, int]:
    caption_left, caption_top = 320 - CAPTION_WIDTH // 2, 432
    if (caption_left <= px < caption_left + CAPTION_WIDTH and
            caption_top <= py < caption_top + CAPTION_HEIGHT):
        alpha = caption[(py - caption_top) * CAPTION_WIDTH + px - caption_left] / 255.0 * 0.80
        if alpha:
            return (int(188 * alpha), int(222 * alpha), int(235 * alpha))
    left, top = 160, 80
    if px < left - 4 or px >= left + 324 or py < top or py >= top + 320:
        return (0, 0, 0)
    mask_scale = 320 // MW
    mx, my = (px - left) // mask_scale, (py - top) // mask_scale
    inside = 0 <= mx < MW and 0 <= my < MH and mask[my * MW + mx]
    shell_strength = 0.0
    if not inside and 0 <= my < MH:
        for distance, strength in ((1, 0.82),):
            for candidate in (mx - distance, mx + distance):
                if 0 <= candidate < MW and mask[my * MW + candidate]:
                    shell_strength = max(shell_strength, strength)
    if not inside and shell_strength == 0.0:
        return (0, 0, 0)
    sx = (px + 0.5 - 320.0) / 160.0
    sy = (240.0 - (py + 0.5)) / 160.0
    radius2 = min(0.9999, sx * sx + sy * sy)
    z = math.sqrt(1.0 - radius2)
    longitude = math.atan2(sx, z) / math.tau + 0.5
    latitude = math.asin(sy) / math.pi + 0.5
    u = longitude + 0.075
    tx = int((u % 1.0) * TW) % TW
    ty = min(TH - 1, max(0, int(latitude * TH)))
    r, g, b = terrain[ty * TW + tx]
    road = sample(roads, TW, TH, u, latitude) / 255.0
    light = sample(lights, TW, TH, u, latitude) / 255.0
    if road:
        r, g, b = r * (1.0 - 0.10 * road), g * (1.0 - 0.08 * road), b * (1.0 - 0.03 * road)
    day = max(0.0, min(1.0, (sx + 0.48) / 0.78))
    transition = day * day * (3.0 - 2.0 * day)
    illumination = 0.22 + 0.78 * transition
    cloud = sample(clouds, CW, CH, longitude * 0.5 - 0.10, latitude) / 255.0
    if not inside:
        shell = cloud * shell_strength
        return (int(242 * shell * (0.32 + 0.68 * transition)),
                int(249 * shell * (0.32 + 0.68 * transition)),
                int(255 * shell * (0.38 + 0.62 * transition)))
    r, g, b = r * illumination, g * illumination, b * illumination
    emission = max(light, road * 0.30) * (1.0 - transition) * (1.0 - cloud * 0.78)
    r += 255 * emission
    g += 206 * emission
    b += 112 * emission
    r = r * (1.0 - 0.72 * cloud) + 242 * cloud * (0.32 + 0.68 * transition)
    g = g * (1.0 - 0.72 * cloud) + 249 * cloud * (0.32 + 0.68 * transition)
    b = b * (1.0 - 0.65 * cloud) + 255 * cloud * (0.38 + 0.62 * transition)
    neighbor_outside = any(
        nx < 0 or nx >= MW or ny < 0 or ny >= MH or not mask[ny * MW + nx]
        for nx, ny in ((mx - 1, my), (mx + 1, my), (mx, my - 1), (mx, my + 1))
    )
    if neighbor_outside:
        r, g, b = (9, 44, 82) if transition < 0.5 else (20, 111, 171)
    return tuple(max(0, min(255, int(value))) for value in (r, g, b))


def write_bmp(path: Path, width: int, height: int, pixels) -> None:
    row_size = (width * 3 + 3) & ~3
    image_size = row_size * height
    header = struct.pack("<2sIHHI", b"BM", 54 + image_size, 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0,
                      image_size, 2835, 2835, 0, 0)
    with path.open("wb") as stream:
        stream.write(header + dib)
        padding = b"\0" * (row_size - width * 3)
        for y in range(height - 1, -1, -1):
            for x in range(width):
                r, g, b = pixels(x, y)
                stream.write(bytes((b, g, r)))
            stream.write(padding)


def main() -> None:
    terrain, clouds, roads, lights, mask, caption = write_assets()
    PREVIEW.mkdir(exist_ok=True)
    write_bmp(PREVIEW / "fixed-globe-preview-v2.bmp", 640, 480,
              lambda x, y: preview_pixel(x, y, terrain, clouds, roads, lights, mask, caption))
    print("GUIDE_FIXED_BOOT_ASSETS_V2_READY")
    for name in ("terrain-fixed-v2.rgb565", "clouds-fixed-v2.r8",
                 "roads-fixed-v2.r8", "lights-fixed-v2.r8",
                 "silhouette-standard-v3.r8", "caption-dont-panic-v3.r8"):
        print(ASSETS / name)
    print(PREVIEW / "fixed-globe-preview-v2.bmp")


if __name__ == "__main__":
    main()
