"""Bake the owner-approved irregular ivory corona into the existing sequence.

Offline only. Native boot player, GPU, handoff and deadlines are unchanged.
Historical draft 5 is retained; its corona is never called by this renderer.
"""
from pathlib import Path
import importlib.util
import hashlib
import json
import random
import sys
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


previous = load('boot_previous', HERE / 'render_boot_eclipse_draft_5.py')
approved = load('corona_approved', HERE / 'corona-draft-02' / 'render_corona.py')
original_space = previous.space

# Cache the unchanged nebula offline. Vectorization reproduces the old rounded
# per-cloud additions while avoiding 75 repetitions of a Python pixel loop.
rng = random.Random(previous.SEED)
clouds = [(rng.randrange(640), rng.randrange(480), rng.randrange(80, 170),
           rng.choice(((5, 20, 48), (8, 29, 66), (12, 22, 55)))) for _ in range(9)]
yy, xx = np.mgrid[:480, :640]
nebula = np.zeros((480, 640, 3), dtype=np.int32)
nebula[:] = (2, 4, 9)
for cx, cy, radius, tone in clouds:
    distance = np.hypot(xx - cx, yy - cy) / radius
    alpha = np.maximum(0, 1 - distance) ** 2
    for channel in range(3):
        nebula[:, :, channel] += np.rint(tone[channel] * alpha).astype(np.int32)
background = Image.fromarray(nebula.astype(np.uint8)).convert('RGBA')
stars = [(rng.randrange(5, 635), rng.randrange(5, 475),
          rng.choice((1, 1, 1, 2)), rng.random() * previous.math.tau) for _ in range(330)]


def space(seconds):
    layer = Image.new('RGBA', previous.SIZE)
    draw = ImageDraw.Draw(layer)
    for x, y, size, phase in stars:
        alpha = round(60 + 145 * (.5 + .5 * previous.math.sin(
            seconds * (.55 + size * .16) + phase)))
        draw.rectangle((x, y, x + size - 1, y + size - 1), fill=(174, 211, 255, alpha))
    return Image.alpha_composite(background, layer)


def corona(seconds):
    # The isolated study's emergence-to-O interval maps to 1.5–5.8 s;
    # thereafter the exact approved final O is held, without residual streamers.
    local = min(6.2, max(0, (seconds - 1.5) * 5.8 / 4.3))
    rgb = np.asarray(approved.render(local))
    alpha = np.where(np.any(rgb != 0, axis=2), 255, 0).astype(np.uint8)
    return Image.fromarray(np.dstack((rgb, alpha)))


def letter_gaps(s_x):
    """Minimum clear horizontal pixels between each glyph and the final rim."""
    outline = np.any(np.asarray(corona(7.4))[:, :, :3] != 0, axis=2)
    g = np.zeros(outline.shape, dtype=bool)
    s = g.copy()
    g[168:312, 78:222] = np.asarray(previous.glyph('G', (255, 255, 255), 255))[:, :, 3] > 0
    s[168:312, s_x:s_x + 144] = np.asarray(previous.glyph('S', (255, 255, 255), 255))[:, :, 3] > 0
    left, right = [], []
    for y in range(480):
        if not outline[y].any():
            continue
        if g[y].any():
            left.append(int(np.where(outline[y])[0][0] - np.where(g[y])[0][-1] - 1))
        if s[y].any():
            right.append(int(np.where(s[y])[0][0] - np.where(outline[y])[0][-1] - 1))
    return min(left), min(right)


def main(revision=1, s_x=418):
    # Protect all unmodified background behavior with an exact source comparison.
    assert np.array_equal(np.asarray(space(0)), np.asarray(original_space(0)))
    previous.space = space
    previous.corona = corona
    frames = previous.render(s_x=s_x)
    label = f'guideos-boot-eclipse-final-{revision}'
    gaps = letter_gaps(s_x)
    if revision >= 2:
        assert gaps == (12, 12), gaps
    target = HERE / 'GuideOS-Eclipse-Boot-Animation.gif'
    frames[0].save(target, save_all=True, append_images=frames[1:],
                   duration=100, loop=0, optimize=False, disposal=1)
    frames[-1].save(HERE / f'{label}-final.png')
    # A distinct immutable-name reference accompanies the current preview alias.
    target.with_name(f'{label}.gif').write_bytes(target.read_bytes())
    sheet = Image.new('RGB', (960, 514), (12, 14, 18))
    draw = ImageDraw.Draw(sheet)
    for number, seconds in enumerate((0.0, 2.4, 4.1, 5.0, 5.8, 7.4)):
        image = frames[round(seconds * 10)]
        x, y = number % 3 * 320, number // 3 * 257
        sheet.paste(image.resize((320, 240), Image.Resampling.NEAREST), (x, y))
        draw.text((x + 8, y + 242), f'{seconds:.1f}s', fill=(230, 230, 230))
    sheet.save(HERE / f'{label}-stages.png')
    with Image.open(target) as animation:
        durations = []
        for index in range(animation.n_frames):
            animation.seek(index)
            durations.append(animation.info['duration'])
        assert animation.n_frames == 75 and durations == [100] * 75
    assert np.array_equal(np.asarray(corona(5.8)), np.asarray(corona(7.4)))
    sys.path.insert(0, str(ROOT / 'apps' / 'boot_animation'))
    import build_prebaked_animation as bake
    destination = ROOT / 'apps' / 'boot_animation' / 'assets' / 'boot-eclipse-v1.rgb565a'
    bake.convert(target, destination)
    # Verify every stored frame against the RGB565 conversion of the GIF source.
    payload = destination.read_bytes()
    with Image.open(target) as animation:
        for index in range(75):
            animation.seek(index)
            start = 32 + index * 640 * 480 * 2
            assert payload[start:start + 640 * 480 * 2] == bake.rgb565(animation)
    receipt = {
        'approved_corona': 'corona-draft-02', 'frames': 75, 'fps': 10,
        'duration_ms': 7500, 'corona_start_s': 1.5, 'final_O_s': 5.8,
        'background_source_pixel_match': True, 'all_rgb565_frames_match': True,
        'final_corona_stable': True,
        's_x': s_x, 's_shift_right_px': s_x - 418,
        'minimum_horizontal_gaps_px': {'G_O': gaps[0], 'O_S': gaps[1]},
        'gif_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'asset_sha256': hashlib.sha256(payload).hexdigest(),
        'scope': 'working-source asset only; no release image, Seed or physical boot validation',
    }
    (HERE / f'{label}-verification.json').write_text(
        json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
