"""Isolated, reproducible pixel-art corona study; not a boot runtime asset.

Owner direction: faint emergence, halo growth, outward flare, contraction to
a bold O. No disconnected particles, lettering, stars or planet texture.
The black disk retains the existing 90-pixel planet radius at 640x480.
"""
from pathlib import Path
import json

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SIZE = (640, 480)
WORK = (320, 240)
FPS = 20
DURATION = 7.5
RADIUS = 45
# Authored shadow-to-white ramp; peach belongs to the lower-temperature edges.
PALETTE = np.array([
    (0, 0, 0), (13, 10, 9), (27, 19, 15), (45, 30, 23),
    (67, 43, 31), (94, 60, 42), (124, 80, 55), (157, 106, 73),
    (187, 133, 94), (213, 160, 117), (232, 187, 144),
    (245, 211, 174), (251, 230, 204), (255, 243, 224),
    (255, 250, 240), (255, 253, 247),
], dtype=np.uint8)

Y, X = np.mgrid[:WORK[1], :WORK[0]]
DX, DY = X - 159.5, Y - 119.5
RADIAL = np.hypot(DX, DY)
EDGE = np.maximum(0, RADIAL - RADIUS)
ANGLE = np.arctan2(DY, DX)


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def lobe(angle, center, spread):
    distance = np.arctan2(np.sin(angle - center), np.cos(angle - center))
    return np.exp(-0.5 * (distance / spread) ** 2)


def render(seconds):
    appear = float(smooth(seconds / 1.15))
    growth = float(smooth((seconds - 0.8) / 1.5))
    eruption = float(smooth((seconds - 2.3) / 1.1))
    settle = float(smooth((seconds - 3.8) / 2.0))
    active = 1 - settle
    flare = eruption * active

    # Broad, asymmetric flowing streamers, not polygonal spikes. Their angular
    # roots remain fixed; slight bend travels outward continuously during flare.
    bend = flare * 0.085 * np.sin(EDGE / 19 - seconds * 1.4)
    angle = ANGLE + bend
    lobes = (
        1.00 * lobe(angle, -2.48, 0.23)
        + 0.78 * lobe(angle, -1.25, 0.17)
        + 0.88 * lobe(angle, -0.38, 0.28)
        + 0.65 * lobe(angle, 0.80, 0.23)
        + 0.93 * lobe(angle, 2.07, 0.27)
        + 0.40 * lobe(angle, 3.02, 0.22)
    )
    reach = 3 + active * growth * 10 + flare * (9 + 37 * lobes)
    # Thin connected filaments run from the limb toward each tapering tip.
    strands = (
        0.74
        + 0.17 * np.sin(angle * 43 + EDGE / 11 + flare * seconds * 0.6)
        + 0.09 * np.sin(angle * 79 - EDGE / 17)
    )
    envelope = np.exp(-((EDGE / np.maximum(reach, 1)) ** 1.45) * 2.2)
    halo = appear * active * (0.25 + 0.75 * growth) * envelope * strands
    # The limb consolidates into a clean, ten-pixel-wide O after contraction.
    ring_width = 1.4 + growth * 0.8 + settle * 2.8
    rim = appear * np.clip((ring_width + 0.8 - EDGE) / 0.8, 0, 1)
    rim *= 0.52 + 0.48 * float(smooth(seconds / 2.2))
    # Ivory-white core, limited warm edge; final outer border is just one pixel
    # at working resolution and is attached to the O rather than detached glow.
    border = appear * settle * 0.38 * np.clip(6.5 - EDGE, 0, 1)
    intensity = np.maximum(np.maximum(halo, rim), border)
    indices = np.clip(np.floor(intensity * 15 + 0.35), 0, 15).astype(np.uint8)
    indices[RADIAL < RADIUS] = 0
    image = Image.fromarray(PALETTE[indices])
    return image.resize(SIZE, Image.Resampling.NEAREST)


def main(animation_name='corona-draft-01.gif'):
    frames = [render(frame / FPS) for frame in range(round(FPS * DURATION))]
    # One shared palette avoids frame-to-frame color quantization flicker.
    palette = Image.new('P', (1, 1))
    palette.putpalette(PALETTE.flatten().tolist() + [0] * (768 - PALETTE.size))
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    target = HERE / animation_name
    encoded[0].save(target, save_all=True, append_images=encoded[1:],
                    duration=1000 // FPS, loop=0, optimize=False, disposal=1)
    times = (0.6, 1.8, 3.6, 4.8, 6.2)
    sheet = Image.new('RGB', (960, 514), (12, 14, 18))
    draw = ImageDraw.Draw(sheet)
    for number, seconds in enumerate(times):
        frame = render(seconds)
        frame.save(HERE / f'corona-{seconds:.1f}s.png')
        x, y = (number % 3) * 320, (number // 3) * 257
        sheet.paste(frame.resize(WORK, Image.Resampling.NEAREST), (x, y))
        draw.text((x + 8, y + 242), f'{seconds:.1f}s', fill=(230, 230, 230))
    sheet.save(HERE / 'corona-stages.png')
    with Image.open(target) as animation:
        total = 0
        for index in range(animation.n_frames):
            animation.seek(index)
            total += animation.info['duration']
            assert animation.size == SIZE
        assert total == 7500, total
    assert np.array_equal(np.asarray(render(6.0)), np.asarray(render(7.4)))
    assert np.all(np.asarray(render(3.6))[240, 320] == 0)
    receipt = {'size': list(SIZE), 'duration_ms': total, 'fps': FPS,
               'logical_frames': len(frames), 'palette_colors': len(PALETTE),
               'pixel_grid': '320x240 scaled 2x nearest-neighbor',
               'final_hold_stable': True,
               'scope': 'isolated visual draft only; no boot, GPU, image or Seed changes'}
    (HERE / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
