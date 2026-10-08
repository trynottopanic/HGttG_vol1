# Isolated corona draft 01

Visual study only. The owner requested a faint corona behind the planet,
expansion before an outward flare, then contraction to a bold O for GOS.
White-ivory cores and restrained peach-orange edges replace the old red-orange
spikes and scattered bright pixels. Fine connected filaments supply detail.

The draft isolates this effect on black with a masked 180-pixel-diameter disk;
there is no planet texture, background, lettering or sound. Its local 7.5-second
timing is a preview, not an approved replacement for the complete boot sequence.

- 0–1.15 seconds: faint emergence.
- 0.8–2.3 seconds: halo expansion.
- 2.3–3.8 seconds: streamers flare outward.
- 3.8–5.8 seconds: contraction and consolidation.
- 5.8–7.5 seconds: stable bold O.

[Animation](corona-draft-01.gif) · [Stages](corona-stages.png)

Render with Python, NumPy and Pillow using `render_corona.py`. Output is
640x480, 20 fps, a 16-color palette and a 2x nearest-neighbor pixel grid.
No existing drafts or runtime assets are overwritten. No boot renderer, GPU
code, release image or Seed is changed. Visual approval and full-sequence timing
remain open before any integration.
