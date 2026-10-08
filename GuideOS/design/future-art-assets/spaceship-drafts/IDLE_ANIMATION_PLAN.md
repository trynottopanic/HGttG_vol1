# Experimental Spaceship Idle Animation Plan

## Shared production rules

- Status: approved experimental prototypes; not final runtime assets.
- Final working canvas: 32x32 pixels with a fixed ship anchor in every frame.
- Default loop: eight frames at eight frames per second, repeating once per
  second. Slower mechanisms may use the same frames over a two-second loop.
- Maximum whole-hull displacement: one pixel. Large ships should move less
  frequently than small ships.
- Animate no more than two primary mechanisms at once. Secondary light changes
  may accompany them without changing the silhouette.
- Use stepped, integer-pixel motion only. No interpolation, subpixel movement,
  blur, rotation filtering, or antialiasing.
- Preserve the ship's identifying silhouette in every frame.
- Exhaust and lamps use a small shared luminous palette, but every ship receives
  a distinct timing pattern.
- Frame 0 is always a clean neutral pose suitable for thumbnails and menus.
- Where a moving part crosses the hull, redraw the occlusion by hand rather than
  rotating or scaling the finished sprite.

## 1. Beetle salvage tug

**Character:** heavy, stable, mechanical.

- Hull settles downward by one pixel on frames 3-5, then returns.
- Front grappling claws close by one pixel during the lowest point and reopen.
- Exposed orange reactor brightens in three discrete levels, peaking just before
  the hull rises.
- Two cockpit windows remain steady so the animation reads as machinery rather
  than blinking eyes.

Recommended loop: eight frames over two seconds.

## 2. Needle high-speed courier

**Character:** restrained energy held under tension.

- Nose remains fixed while the tail rises one pixel, then returns, creating a
  slight pitch without shifting the whole sprite.
- Cooling-spine highlights travel backward through three short segments.
- Exhaust alternates between two lengths with one brief narrow frame.

Recommended loop: eight frames over one second.

## 3. Lantern survey craft

**Character:** attentive, curious, gently suspended.

- Entire hull rises one pixel for two frames and settles gradually.
- Brass sensor-ring highlights advance by one quarter turn over the loop; the
  ring geometry itself remains fixed at 32x32.
- One antenna lamp emits a two-frame blue pulse, followed later by a different
  antenna's single-frame response.

Recommended loop: eight frames over two seconds.

## 4. Mule modular cargo carrier

**Character:** burdened, durable, slightly uneven.

- Cockpit and cargo assembly remain fixed; the rear cargo block drops one pixel
  for two frames as if its mount flexes under weight.
- A cable beneath the blocks changes between two hand-drawn sag shapes.
- Offset engine flame expands asymmetrically during the recovery movement.

Recommended loop: eight frames over two seconds.

## 5. Manta atmospheric transport

**Character:** buoyant aerodynamic lift.

- Wing tips lower by one pixel, hold briefly, and return, without bending the
  central hull.
- Underside lift jets illuminate from the center outward, then fade outward to
  center.
- Cockpit and upper hull stay still to keep the movement graceful.

Recommended loop: eight frames over one second.

## 6. Kettle mining ship

**Character:** idling industrial equipment.

- Drill face advances through four rotational highlight states while retaining
  the same outer silhouette.
- One vent releases a two-frame, two-pixel puff which disappears completely
  before the loop ends.
- Engine lamps dim slightly while the drill highlight is brightest, implying a
  shared power load.

Recommended loop: eight frames over two seconds.

## 7. Heron reconnaissance ship

**Character:** balanced, precise observation.

- Central navigation drum advances through four light positions.
- Opposing sensor spars tilt by one pixel in alternating directions, then return
  to neutral together.
- Lower thrusters pulse once to correct the resulting drift; the hull itself
  does not bob.

Recommended loop: eight frames over two seconds.

## 8. Jackrabbit racing craft

**Character:** overpowered and impatient.

- Rear engine housings alternate vertically by one pixel, suggesting vibration.
- Pastel exhaust changes length every frame in a controlled four-state pattern.
- The cockpit remains anchored while one loose red bracket flickers between two
  positions.

Recommended loop: eight frames over one second.

## 9. Hearth passenger vessel

**Character:** inhabited, warm, calm.

- Hull moves down one pixel only once during the loop, then returns slowly.
- Communication dish changes between three angles across the upper silhouette.
- Two or three windows change brightness independently; most windows remain
  steady so the vessel feels occupied rather than electrically unstable.
- Lavender/cyan engine fan expands by one pixel at peak lift.

Recommended loop: eight frames over two seconds.

## Implementation sequence

1. Produce one manually simplified neutral 32x32 sprite for each prototype.
2. Review silhouettes together at native size and at 2x nearest-neighbor scale.
3. Reserve a consistent anchor point and bounding box for each ship.
4. Animate Beetle, Needle, and Lantern first as representatives of heavy, fast,
   and floating motion.
5. Test those loops on the 640x480 target framebuffer.
6. Adjust timing and luminous palette before animating the remaining six.
7. Store each final loop as a horizontal eight-frame RGBA atlas, 256x32 pixels,
   accompanied by a small manifest naming frame rate, anchor, and loop duration.
