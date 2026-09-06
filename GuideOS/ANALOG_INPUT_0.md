# Analog Input 0

GuideOS treats the Deck's two analog sticks as ordinary Linux input axes. The
RG35XX H's `muOS-Keys` driver was observed to report a dummy zero-range axis
before each real pair. Its working axes are `ABS_Y`/`ABS_Z` for left X/Y and
`ABS_RY`/`ABS_RZ` for right X/Y. GuideOS detects this capability layout instead
of assuming that every controller uses the conventional axis numbering.

At startup, the shell asks each input device for its declared minimum, maximum,
flat area, fuzz, and resolution. It derives the center and activation threshold
from those device-provided values rather than assuming an 8-bit or 12-bit
range. The threshold is at least half of the distance from center to an edge
and at least twice the kernel-declared flat area. This intentionally favors
stable menu control over maximum sensitivity during early hardware testing.

A direction fires immediately when a stick crosses the threshold. If held, it
waits 450 milliseconds and then repeats every 170 milliseconds until the stick
returns to the central dead zone. This permits deliberate scrolling without
letting a held stick race uncontrollably through a menu.

Both vertical axes navigate Guide menus. Horizontal axes are recognized as left
and right actions and browse cartridges and on-screen keyboard rows in addition
to the vertical axes. The D-pad remains available for precise movement.
The Input Test displays and logs every key and absolute-axis event, including
neutral values that do not cause a menu action. This first physical test will
confirm the actual axis codes, ranges, orientation, centers, and drift on the
RG35XX H before analog values are exposed to games or general Guide packages.
