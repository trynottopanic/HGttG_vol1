# Browser memory and resident recovery

Implementation for the RG35XX H Debian profile, following the owner's acceptance
of the containment recommendations and Start + Select recovery request on
2 October 2026. The preceding incident is recorded in
[BROWSER_FREEZE_0_4_3_01.md](BROWSER_FREEZE_0_4_3_01.md).

## Installed policy

The Browser retains its unprivileged PAM/logind seat session. Limits apply to its
dedicated UID's parent slice, covering Weston, WebKit, GTK and user-session helpers,
as well as the launcher. The UID is resolved from the image's existing accounts.

| Control | Initial bounded policy |
| --- | --- |
| Browser memory.high | 320 MiB soft reclaim threshold |
| Browser memory.max | 384 MiB charged resident memory ceiling |
| Browser memory.swap.max | 64 MiB swapped pages maximum |
| Browser tasks | 256 maximum, including threads |
| Launch admission | 512 MiB available RAM: full Browser ceiling plus 128 MiB headroom |
| Early pressure recovery | Sustained 2 seconds below 96 MiB available, or below 128 MiB with reclaim/pressure evidence |
| Browser reclaim livelock | Sustained repeated high-limit events, even if system RAM remains available |
| Compressed swap | 128 MiB logical zram, 64 MiB compressed storage ceiling, no disk swap |

These are initial engineering settings, not measured optimums for every webpage.
The ceiling covers cgroup-accounted memory, including charged page cache and
kernel allocations. It does not cap virtual address space, all GPU/driver memory,
or every system service's indirect cost. The available-memory guard supplements
the ceiling. Bounded swap is additional cushion, not extra admission capacity.

The recovery service and resident input owner receive memory protection, CPU
priority and individual ceilings. logind and D-Bus also receive memory protection
and a reduced global OOM preference. Ancestor protection is set on system.slice.
The shell receives a separate ceiling; installed applications retain the existing
Supervisor limit of four instances and their individual 64 MiB ceilings. This
change does not claim a new general reservation ledger for all system services.

Browser launch fails visibly when memory headroom or the recovery service is
unavailable. Before starting its compositor, Browser checks the actual kernel
limits, whole-session policy and its own session membership. Launcher limits alone
are insufficient. Pressure closure reports why Browser closed; unsaved page state
may be lost under this explicitly adopted ephemeral-session recovery policy.

The guard writes and reads back the kernel's memory.oom.group attribute on the
dedicated UID slice before advertising readiness. There is no systemd
MemoryOOMGroup slice directive; OOMPolicy=kill applies to the launcher service
only. See [systemd OOMPolicy](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#OOMPolicy=)
and [kernel cgroup memory controls](https://docs.kernel.org/admin-guide/cgroup-v2.html).
The live PAM fixture verified an actual whole-group OOM kill, rather than assuming
a unit-file setting was accepted.

Every stop checks the original service invocation and cgroup directory identities,
requests normal termination, then escalates through pinned cgroup directories.
The dedicated Browser cleanup hook also reaps PAM/user-manager helpers. Home is
not granted display ownership while original processes remain alive.

## Resident overlay

Start + Select opens the existing resident control service from Guide screens,
Browser or video. The shell explicitly yields its framebuffer before switching
to reserved VT3. Display owners handle the VT release before their groups pause.
The overlay has its own input and rendering loop, protected from Browser memory
growth, and does not depend on the Browser's page loop.

- Left / Right: system/process diagnostics, performance, active applications.
- B or Start + Select: resume the previous screen.
- On Active Applications, A opens confirmation; A again force closes the listed
  managed application trees and returns Home. B cancels. The prompt states that
  unsaved work may be lost.
- Power remains owned by logind. Volume requests go directly to the audio service
  while the shell is paused.

Recovery targets managed Browser, media-player and authenticated Supervisor
application records. It does not offer arbitrary PID killing or terminate critical
system services. Force Home restarts the shell only after applications are empty
and the overlay has released the display. This closes active application sessions;
it does not delete downloaded files, owner data or saved application state.

Crash checkpoints record the original VT and paused Browser group identity before
freezing. The control service's stop hook thaws those original groups and restores
the screen, or completes Home return after an owner force-close.

An unacknowledged display release is refused rather than silently discarding work.
The shortcut cannot promise recovery from a kernel/GPU hang, uninterruptible device
I/O, or a shell that cannot acknowledge display release. Those remain explicit
physical failure cases; the memory containment aims to prevent the observed
Browser-induced starvation before they occur.

## Evidence boundaries and acceptance

Source tests cover admission, actual session membership, pressure and reclaim
signals without PSI, stale recovery identities, incomplete termination, A/B/chord
behavior, authenticated display acknowledgements and crash cleanup ordering.
The disposable Linux/systemd fixture exercises a real PAM migration, memory OOM
and production cleanup while sampling an unrelated heartbeat. It is host evidence,
not physical Deck proof.

Additive zram/zsmalloc modules use the exact installed kernel source, configuration
and original compiler; export/version checks are recorded separately. The kernel
Image and device trees are preserved. Physical module loading and zram behavior
remain unverified until deployment.

Deck acceptance must repeat the Earth image workload, prove all actual Browser
descendants remain inside the limited slice, observe early recovery and continued
Power/volume/Wi-Fi responsiveness, and open/resume/force-close the overlay from
Home, an editor, Browser and video. Confirm saved files survive, unsaved-work
warning appears, and Home waits for compositor/process exit. A source or candidate
image pass cannot substitute for those tests.
