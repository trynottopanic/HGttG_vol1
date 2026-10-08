# GPU presentation work after 0.4.2

The first increment moves UI composition and presentation to the Deck's Mali
GPU. It does not change navigation or introduce a new visual design. Guide View
still owns text, layout, focus, hit targets and input; the board adapter owns the
display. CPU-side providers, storage, decoding policy and authorization are
unchanged. This follows Guide View's renderer boundary and the framework's
separate Guide View, Media and Remote Application surfaces.

## Implemented source

- `guide_gpu.c` uses EGL/GLES2 and GBM on the connected 640×480 internal display found
  by `sun4i-drm` driver identity. Card numbers are discovered. It accepts hardware
  Mali/Panfrost renderers and rejects software rendering. The returned kernel
  identifies Mali-G31; the board device tree identifies the internal DPI panel.
- Home caches its neutral/highlight wheel shapes, upright icons, shortcut cards
  and text layers. Rotation, translation, fades, pixel conversion and scanout
  happen in the compositor. Text rasterization remains bounded CPU work.
- Pointer motion reuses the content and cursor textures. Status and volume
  overlays are cached; volume fades change a shader parameter. Context menus
  and text editors retain their existing bounded rasterization.
- The native adapter has 32 texture slots and a 16 MiB texture ceiling. The
  Python LRU drops old textures before reaching either limit. Temporary scanout
  buffers, driver allocations and Python images are additional memory.
- The 0.4.2.05 development candidate uses named mutable textures for the base
  viewport, status, volume and planet, replacing the previous retained CPU image
  in each slot. RGBA changes upload their bounding rectangle through
  `guide_gpu_update`; unchanged frames reuse the texture. The 144×144 planet
  scales to 288×288 at draw time with the same nearest-neighbor appearance.
- The existing framebuffer is the recovery path. Startup rejects an unsuitable
  GPU; upload/presentation failure restores framebuffer scanout before fallback.
  A failed restoration retains the context and reports failure.
- Browser release is acknowledged before its lease is granted. Video release
  happens before the asynchronous open request is submitted. Resume acquires
  the GPU lazily after the previous owner stops. The boot handoff barrier remains
  in place. EGL and display calls run only on the shell thread.
- Page-flip completion has a 250 ms bound; cleanup drains for up to one second.
  Pending event data lives in the retained context rather than a stack variable.
  A release failure cannot silently grant the display to another owner.

## Build and evidence

`package/guide-ui/gpu/build-debian.sh` builds the ARM64 shared library against the
existing Deck runtime graphics libraries. The build does not modify that root.
Install the library at `/usr/lib/guideos/ui/libguidegpu.so`; the shell selects this
adapter with `GUIDE_UI_GPU=1`. The 0.4.2.01 root image enables this adapter;
source deployments without that setting retain the framebuffer. The existing Wi-Fi shell payload
cannot install this native library or host service changes.

The ARM64 build passed `-Wall -Wextra -Werror`. Python sources compile. Rendered
previews cover neutral, held, moving and extended-tray Home states; their semantic
regions match the existing renderer. Those initial checks did not include test
suites or Deck playback experiments. The [0.4.2.05 performance pass](BUILD_0_4_2_05.md)
adds focused cache/update tests and 120 host pixel/control comparisons. Its native
library also builds with strict warnings. These are source/build/preview checks,
not hardware performance proof.

Physical acceptance still needs renderer evidence, measured CPU/frame timings,
memory under normal use, cancellation/power behavior, repeated Browser/Video
handoffs and recovery after a failed presentation. No speedup or battery saving
is claimed yet. The returned 0.4.2 Seed provided the browser/media failure logs.
The assembled 0.4.2.01 image includes the native compositor and repairs described
in [the release record](BUILD_0_4_2_01.md). Its installation receipt records Seed
write/readback separately from the pending physical acceptance.

Mesa documents Mali-G31 and the separate rendering/display arrangement through
`kmsro`: [Panfrost driver](https://docs.mesa3d.org/drivers/panfrost.html).
Page flips complete at vertical blank; buffer ownership follows that event:
[DRM user interfaces](https://www.kernel.org/doc/html/v6.8/gpu/drm-uapi.html).

## Video rendering follow-on — 2 October 2026

Owner direction: establish hardware rendering for the NDI video/game-streaming
framework. The native player already selects mpv's GPU output on DRM/EGL with
OpenGL ES, bilinear color/scaling and the existing direct-display lease. This
source follow-on explicitly rejects software OpenGL (`--gpu-sw=no`) while
retaining the DRM software output as recovery. It does not change controls,
audio routing, buffer policy, source admission or decoder thread counts.

The native player subscribes to `current-vo`, `current-gpu-context` and
`hwdec-current` on its existing single IPC reader. Session diagnostics and the
decoder-ready event report these observed values, distinguishing GPU rendering
from hardware decoding. Missing/invalid values remain unknown; an option selected
on the command line is not proof of an active path. The software DRM output and
headless test output cannot report hardware rendering. No per-frame synchronous
property polling is added.

The owning components are the native mpv backend, video adapter and media
provider. Acceptance requires actual GPU output with the DRM context, successful
audio/display ownership and recovery after interruption or rendering failure.
The added source boundary tests cover observed-path reporting, software fallback,
unknown values and zero additional status requests. Physical scanout, GPU timings,
CPU reduction and repeated video/shell handoff remain untested on the Deck.

Hardware decoding uses the SoC's separate video engine, not the Mali shader
renderer. In the inspected working Linux 7.2.7 configuration,
`CONFIG_VIDEO_SUNXI` is disabled. Its H616 device tree, inherited by the H700 board,
has no video-engine decoder node; the Cedrus match table has no H616/H700 entry.
The saved board boot log does show Panfrost initializing Mali-G31. These are
working-source and saved-log observations, not a fresh live-device inventory.
The machine-readable kernel audit is
`build/release-0.4.2.05/gpu-video-kernel-audit.json`.

Decoder enablement therefore requires a compatible H700 video-engine driver,
device-tree resources, kernel configuration and userspace decoder integration.
Do not substitute an H6 compatible string or enable automatic hardware decoding
as evidence that the H700 path works. Evaluate a maintained board-specific
implementation in isolation, then demonstrate actual H.264 decode, correct
frames, bounded buffers and display/audio handoff before enabling it. Until
then, software decode and Node-side preparation remain available.

Upstream separates [stateless decoder requests](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/dev-stateless-decoder.html)
from display rendering; mpv documents
[software GPU rejection](https://mpv.io/manual/stable/#options-gpu-sw) and
[observed output properties](https://mpv.io/manual/stable/#property-list-current-vo).
This follow-on is source work for 0.4.2.05. The previously verified offline image
does not yet contain these additions, and no Deck or Seed write was performed.

Validation: 117 focused source checks passed. The saved image's actual ARM64 mpv,
running under emulation with the updated source overlay, accepted the software
GPU option and reported headless output with software decoding correctly. Real
video pause, seek, readiness, EOF and status reads without additional property
requests passed. This exercises the runtime/IPC boundary, not EGL/DRM hardware.
Receipts: `build/release-0.4.2.05/gpu-video-result.json` and
`build/release-0.4.2.05/gpu-video-native.log`.

The owner subsequently selected the downstream H700 Cedrus implementation. The
[development integration](../board/rg35xxh/debian/cedrus/README.md) adds the driver,
device-tree resources and a private patched player runtime. H.264 can request
`v4l2request-copy` after runtime/device admission, preserving this GPU presentation
path. It still reports observed decoder use, with software fallback and no new
status polling. This supersedes the baseline's missing-driver work item above;
physical hardware decode and a coherent full-image deployment remain outstanding.

## Combined 0.3 optimization prototype, 3 October 2026

The [implementation record](PLANEGOTCHI_0_3_OPTIMIZATION_IMPLEMENTATION.md) supersedes the earlier preparation-only status.
GuideOS 0.4.3.08 contains GPU globe/ordered atlas rendering, bounded background
loading, one supervised durable world worker and an exact selective calculation
optimization. Source, offscreen host and ARM64 image checks pass; Seed readback,
boot and physical acceptance are reported separately in the .08 deployment records.
The five-mark world remains explicitly a prototype, with site activity unbound.
