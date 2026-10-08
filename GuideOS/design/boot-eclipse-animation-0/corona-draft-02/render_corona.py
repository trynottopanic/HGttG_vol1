"""Revision 02: irregular, coherent filaments; preserve draft 01 timing and O."""
from pathlib import Path
import importlib.util
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'corona_baseline', HERE.parent / 'corona-draft-01' / 'render_corona.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_render = base.render

# Fixed spatial anatomy: randomness authors the strands once, never each frame.
# Unequal gaps, overlapping bundles, short wisps and long ribbons avoid the
# evenly spaced radial comb of draft 01 without introducing particle flicker.
rng = np.random.default_rng(20261002)
filaments = []
center = -np.pi
while center < np.pi:
    width = rng.uniform(0.012, 0.065)
    length = rng.uniform(0.48, 1.35)
    brightness = rng.uniform(0.42, 1.05)
    curve = rng.uniform(-0.16, 0.16)
    phase = rng.uniform(0, 2 * np.pi)
    taper = 1 - 0.62 * base.smooth(base.EDGE / 85)
    bending = curve * (base.EDGE / 65) ** 1.25
    bending += 0.018 * np.sin(base.EDGE / rng.uniform(17, 32) + phase)
    distance = np.arctan2(np.sin(base.ANGLE + bending - center),
                          np.cos(base.ANGLE + bending - center))
    profile = np.exp(-0.5 * (distance / (width * taper)) ** 2)
    filaments.append((profile, length, brightness))
    center += rng.uniform(0.065, 0.26)


def render(seconds):
    appear = float(base.smooth(seconds / 1.15))
    growth = float(base.smooth((seconds - 0.8) / 1.5))
    eruption = float(base.smooth((seconds - 2.3) / 1.1))
    settle = float(base.smooth((seconds - 3.8) / 2.0))
    active = 1 - settle
    flare = eruption * active
    bend = flare * 0.085 * np.sin(base.EDGE / 19 - seconds * 1.4)
    angle = base.ANGLE + bend
    lobes = (
        base.lobe(angle, -2.48, 0.23)
        + 0.78 * base.lobe(angle, -1.25, 0.17)
        + 0.88 * base.lobe(angle, -0.38, 0.28)
        + 0.65 * base.lobe(angle, 0.80, 0.23)
        + 0.93 * base.lobe(angle, 2.07, 0.27)
        + 0.40 * base.lobe(angle, 3.02, 0.22)
    )
    reach = 3 + active * growth * 10 + flare * (9 + 37 * lobes)
    diffuse = 0.32 * np.exp(-((base.EDGE / reach) ** 1.45) * 2.2)
    strands = np.zeros_like(base.EDGE)
    for profile, length, brightness in filaments:
        envelope = np.exp(-((base.EDGE / (reach * length)) ** 1.45) * 2.2)
        strands = np.maximum(strands, brightness * profile * envelope)
    halo = appear * active * (0.25 + 0.75 * growth) * np.maximum(diffuse, strands)

    # Exactly the original rim and final consolidation, independent of strands.
    ring_width = 1.4 + growth * 0.8 + settle * 2.8
    rim = appear * np.clip((ring_width + 0.8 - base.EDGE) / 0.8, 0, 1)
    rim *= 0.52 + 0.48 * float(base.smooth(seconds / 2.2))
    border = appear * settle * 0.38 * np.clip(6.5 - base.EDGE, 0, 1)
    intensity = np.maximum(np.maximum(halo, rim), border)
    indices = np.clip(np.floor(intensity * 15 + 0.35), 0, 15).astype(np.uint8)
    indices[base.RADIAL < base.RADIUS] = 0
    return base.Image.fromarray(base.PALETTE[indices]).resize(
        base.SIZE, base.Image.Resampling.NEAREST)


if __name__ == '__main__':
    assert np.array_equal(np.asarray(render(6.2)), np.asarray(original_render(6.2)))
    assert np.array_equal(np.asarray(render(3.6)), np.asarray(render(3.6)))
    base.HERE = HERE
    base.render = render
    base.main('corona-draft-02.gif')
    print(f'Fixed irregular filaments: {len(filaments)}; final O matches draft 01')
