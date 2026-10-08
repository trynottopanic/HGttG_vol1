# Guided controller discovery and exercise

Status: implemented for diagnostic 3; see `DEBIAN_DIAGNOSTIC_3.md` for the
implementation, validation, and physical-test status.

## Purpose and limits

Associate physical controls with their actual Linux input events, then exercise
their observable behavior. Do not assume that BTN_SOUTH means the physical A
button. Device names, advertised capabilities, observed events, and the user's
physical-control prompt are separate evidence.

Never request Start, Power, or Reset. Exclude them from completion requirements,
retries, navigation shortcuts, and combinations. Do not synthesize their events.
Start events, if incidental, cannot advance a prompt. Do not grab the power-key
device or disable hardware recovery behavior. Software cannot prevent a physical
reset or guarantee that holding Power will not shut down the hardware.

This is a quick functional screen, not an exhaustive reliability, latency, or
electrical test. Aim for about three minutes for the required controls; optional
outputs/accessories and retries take additional time.

## Screen and interaction

Use the whole 640x480 display. Show a recognizable front/back controller outline
with the current physical control highlighted and labeled. Use a rear view for
shoulder buttons and a side inset for volume. Show one large instruction, a live
response indicator, and progress such as `7 of 18 controls`.

Example:

    DISCOVER — LEFT SHOULDER L1
    Press L1 once, then release it.
    [highlighted controller outline]
    Waiting for press → Press detected → Released ✓

Use words/icons as well as colors: waiting (amber), detected/complete (green),
needs another try (amber), and excluded (gray). Keep raw Linux codes in the
saved report and optional details view, not the main prompt. Show a large live
stick dot and target markers during analog tests.

Give each prompt up to 12 seconds, with a visible remaining-time bar. Complete
early on success, pause briefly for acknowledgment, and require release/neutral
before arming the next prompt. A timeout means `not observed`, not `broken`.
Collect missed or ambiguous items for one retry round. Never consume a held
button or an event queued before the prompt as the next prompt's answer.

After required tests, use a separate results/navigation mode. Only already
discovered controls may operate its clearly labeled Retry, Optional tests, and
Finish actions. If no navigation controls were discovered, save and show an
automatic finish countdown. During capture, tested buttons do not navigate.

## 1. Inventory and neutral baseline

Read device identity and capability bitmaps through evdev; use device paths and
identity rather than fixed event numbers. Observe the gamepad and volume devices.
Keep headphone detection separate. Record advertised axes, ranges, fuzz/flat,
keys, switches, and force-feedback capabilities.

Show `Leave the controls untouched` for two seconds. Record initial key states,
stick centers, and movement at rest. A control already held must be released
before discovery starts. Label a non-neutral baseline for retry; do not silently
calibrate away a stuck control.

## 2. Discover physical inputs

Prompt one tap and release for each of these 18 physical digital controls:

1. A, B, X, Y, each by its printed label and highlighted physical location.
2. D-pad Up, Right, Down, Left.
3. L1, R1, L2, R2, with the corresponding rear location shown.
4. Left-stick click, right-stick click.
5. Select and Menu/function.
6. Volume Up and Volume Down.

Start, Power, and Reset remain visibly excluded. The previously captured device
inventory advertises 17 gamepad keys including Start, plus two volume keys; this
leaves 18 required digital controls. Verify these counts against the inventory
at runtime rather than assuming another controller has the same layout.

Associate each prompt with device identity, event type/code, pressed value, and
released value. If an event is already associated with another physical control,
or multiple new keys arrive, flag the association for retry rather than silently
overwriting it. Record incidental stick movement while clicking a stick without
mistaking that movement for the click. Never use a physical label inferred solely
from the kernel code as evidence that mapping is correct.

Discover each stick with separate rightward and upward movements followed by
release. Identify its two axes and polarity from the dominant changes; uncertain
or coupled movement gets another prompt. Preserve the raw values and signs.

## 3. Exercise the discovered inputs

Digital controls: prompt each one to `Hold until the ring fills, then release`
(one-second hold), followed by `Tap once more`. Verify down, continued held
state, up, and another down/up cycle. Auto-repeat events are not new physical
presses. Record unexpected extra transitions; do not call them electrical bounce
without supporting measurements.

D-pad: after individual tests, guide a slow clockwise sweep including diagonals.
Show the active directions. Verify adjacent pairs can coexist and return to no
directions on release. Do not request opposing directions at once.

Sticks: show four edge targets for each stick, followed by `Trace the outer edge
once slowly, then let go`. Record observed minimum, maximum, center on release,
axis polarity, discontinuities, and cross-axis changes. Display progress toward
the advertised range, but retain observed versus advertised values separately;
do not reject a working stick solely for missing an arbitrary endpoint threshold.
Flag incomplete edge coverage or unstable center for review. Then prompt a click
while moving that stick to check simultaneous axis/button reporting.

Combination check: hold L1 and tap the discovered A control, then hold R1 and tap
the discovered B control. Confirm both events coexist and release independently.
This samples simultaneous reporting; it does not prove every combination works.

L2/R2 are currently advertised as digital keys. Test their press/hold/release
behavior, not invented analog travel. If another controller advertises analog
triggers, discover and exercise their rest-to-full-travel axes instead.

## 4. Optional outputs and accessory I/O

Separate reported support from user-confirmed physical operation. Present these
after the required input test; they must not prevent input completion:

- Display: labeled color fields and moving marker, followed by user confirmation.
- Rumble, only if exposed: brief low-strength then stronger pulses, with an
  immediate stop action. Ask whether each was felt. Returning success from a
  driver is not proof the motor moved.
- Audio: brief low-volume left/right cues after a deliberate `Play test` action;
  allow volume adjustment and ask which cues were heard. Avoid assuming codec
  enumeration establishes audible output or correct channel routing.
- Headphone switch: optional insert/remove prompts if the user has headphones;
  compare switch events and, separately, confirm audio routing if tested.

USB, storage-slot, charging, radio connectivity, and destructive/restart actions
belong to separate device tests. Do not report them as tested by this controller
exercise. Start, Power, and Reset remain excluded throughout.

## Evidence and acceptance

Save after each completed control to the existing boot-ID report directory on
data and boot partitions. Include a structured JSON summary and timestamped raw
events using a monotonic clock. For each prompt record physical label, device
identity, capability declaration, event code/value, prompt start/end, observed
transitions/ranges, and outcome: complete, not observed, ambiguous, user-skipped,
excluded, or unavailable. Record software/build version and disconnects.

Handle lost evdev events by resynchronizing state and retrying the affected step;
do not score an incomplete event sequence as a hardware failure. A disconnected
device pauses its prompts and retains already saved results.

Summary must distinguish advertised, discovered, exercised, and user-confirmed
output capabilities. Show missed items explicitly and offer retry. Do not mark
the whole controller fully validated when optional functions or physical mapping
remain uncertain. Keep graphics testing behind an explicit transition screen.

The current diagnostic's 180-second service limit must be replaced for this
interactive workflow: active prompts need time to complete. Use a generous
session bound (initially eight minutes), visible idle/session warnings, and
save partial results before an orderly exit. Never let a hidden old timeout
terminate the user's input test without explanation.
