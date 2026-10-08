# GuideOS 0.3.2 boot-animation integration

Status: installed on the seed and fully read-back verified on 2026-09-25 at
05:07:58 UTC. Boot and data regions are verified unchanged. Physical display
acceptance failed on the first Deck test: EGL setup exited before a frame was
shown. See [failure analysis and correction](BOOT_ANIMATION_FAILURE_1.md).
This supplements the installed 0.3.2 network bootstrap.

## Scope and source

The Discuss task supplied the fixed globe renderer and assets in
`apps/boot_animation`. This integration preserves its black 640x480 background,
centered 320-pixel globe, fixed terrain and cloud textures, screen-right lighting,
two-second rotation acceleration, and eight-second animation. It does not add
the later procedural animation ideas.

The renderer uses DRM/KMS, GBM, EGL and OpenGL ES. It discovers a connected
display rather than assuming that the panel belongs to card0. No runtime
packages were added to the existing Debian bootstrap.

## Ownership and failure handling

The animation runs before Guide Shell. It has no input or Power ownership.
Shell startup is ordered after the animation but does not require its success.
Ordinary shell restarts do not replay it, and direct manual animation starts
are rejected to avoid competing with the running shell for the display.

Page-flip waits stop on interruption and expire after one second without an
event. Invalid non-finite timing arguments are rejected. The systemd unit has
a twelve-second startup limit and a further two-second stop limit before forced
termination. These limits bound the service, not the entire device boot.

A separate console helper saves tty1's mode and suppresses console drawing
during the animation. Both successful completion and failure invoke restoration
before the shell starts. Restoration also runs when systemd kills the renderer;
it does not depend on the renderer executing its own cleanup.

## Evidence

Candidate: `build/boot-animation-0/guide-0.3.2-boot-root.ext4`

Size: 2,147,483,648 bytes. SHA-256:

`3CB75C8801B5298597C4AF973E8A84AA5190FA297E97B887A66C7260E8AE8B0E`

`build/boot-animation-0/validation.json` records the checks and evidence hashes:

- Native ARM64 build and dynamic dependency resolution against this image.
- Page-flip completion, missing events, interruption, event failure and timing
  argument tests; independent console cleanup tests.
- Real systemd virtual boots exercising unavailable graphics, a hung renderer,
  shell startup after both failures, rejection of direct animation starts, and
  shell restart without replay; clean virtual power-off.
- Filesystem check and unchanged package inventory. Existing deployment,
  connectivity, credentials and Guide state match the baseline image.
- Guest-only fixtures are absent from the candidate. Temporary virtual guest
  images are removed after exporting the evidence.

Virtual tests do not establish panel orientation, visual smoothness, real DRM
cleanup, or physical controls. Those remain Deck tests.

## Installation and recovery

The current network delivery contract updates shell/input files only. This
native renderer, its assets and its boot service require a bootstrap root image
update. Their approximately 2.14 MB payload fits the requested network size
ceiling, but size alone does not make them an allowed update type.

The prepared installer targets only partition 2 of the previously identified
USB seed: Disk 4, TS-RDF5 SD Transcend, serial 00000000TS38, total size
62,239,277,056 bytes. Root offset is 135,266,304 bytes and length is
2,147,483,648 bytes. It checks identity, layout, baseline contents and recovery
files before writing, then reads back root, boot and data. A changed card must
be captured and re-evaluated; the checks must not be bypassed.

Recovery consists of the verified installed bootstrap root image and the
unchanged boot/data regions in the retained pre-bootstrap capture. This is a
composed recovery source, not a newly captured complete current card. Exact
paths and hashes are in `build/boot-animation-0/prewrite.json`.

The user approved this candidate's seed write. Installation completed with a
matching full root readback; the boot and data regions also match their expected
hashes. See `build/boot-animation-0/installation.json` and `seed-install.txt`.
The earlier `validation.json` retains its pre-installation snapshot. Any future
write needs its own current checks; an interrupted write can leave root
unbootable until restored.

## Physical test

1. Confirm the centered, circular globe appears and terrain accelerates smoothly.
2. Confirm clouds move independently and lighting remains fixed on screen.
3. Confirm the shell appears after the animation without lingering artifacts.
4. Exercise menu navigation, keyboard, Wi-Fi and normal Power behavior.
5. Return the seed or retrieve logs to check animation completion and cleanup.

## Later shell rendering migration

First test this animation and its display handoff while retaining the current
shell presentation path. Then extract a common display presenter with explicit
acquisition, buffer presentation and release. The boot renderer should be a
client of that presenter rather than the shell embedding a boot-only program.

The smallest shell migration keeps the existing layout, text rendering,
keyboard and input handling. It uploads each rendered shell frame to a GPU
texture and presents it through the shared graphics path. This avoids a full
GUI rewrite but requires handling pixel formats, buffer lifetime, display
orientation, ownership and recovery. It does not itself move layout or text
drawing onto the GPU, so CPU and memory improvements require measurement.

Moving selected drawing operations onto the GPU is a separate later option.
Do not combine that broader rewrite with the first physical boot-animation test.
