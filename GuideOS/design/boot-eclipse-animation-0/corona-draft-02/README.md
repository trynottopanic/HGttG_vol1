# Corona draft 02

Revises only the filament anatomy from draft 01: unequal spacing, widths,
brightness, reach and curvature; overlapping bundles and shorter wisps.
Anatomy is deterministic and persistent across frames, not random particles.
The broad flare directions, palette, pixel grid, timing and final O are retained.
The final O is checked pixel-for-pixel against draft 01.

[Animation](corona-draft-02.gif) · [Stages](corona-stages.png)

Run `render_corona.py` with NumPy and Pillow. It imports the previous draft's
shared palette and exporter, but writes only to this directory. The previous
animation is preserved. Visual draft only; no boot runtime or Seed changes.
