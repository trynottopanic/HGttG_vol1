# Windows UI Performance Standard

Guide Windows applications must remain directly coupled to the user's current
input. They must never replay old pointer positions after the user has changed
direction or released the button.

## Required implementation

- Native drag input must pass through the shared `MovementGovernor`.
- Visual window-position commits must not exceed the active display's refresh
  rate. Higher-rate input is sampled, not replayed.
- Each committed position must be calculated from the live pointer position,
  never solely from an earlier queued position.
- A mouse-driven modal move must stop when the physical button is released,
  even if Windows has not yet delivered its queued release message.
- Expensive child surfaces must not repaint during movement. Repaint once after
  the move ends.

## Required diagnostic evidence

Every native Windows prototype must be able to report:

- source movement commands per second;
- committed visual positions per second and suppressed positions;
- active display refresh rate and oversubscription ratio;
- incoming command staleness and governed window-target distance behind the
  live pointer (median, 95th percentile, maximum), reported separately;
- UI heartbeat delay and process CPU use;
- time between physical button release and the end of modal movement.

## Acceptance limits

- committed movement rate: no more than 120% of display refresh rate;
- 95th-percentile governed window-target lag: no more than 24 physical pixels;
- post-release settling: no more than 100 milliseconds;
- no visible continued movement after input changes direction or stops.

A build that fails any limit is diagnostic-only and must not become the public
Node interface.
