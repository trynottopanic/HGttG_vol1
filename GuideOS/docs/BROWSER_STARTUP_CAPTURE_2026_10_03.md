# Controlled Browser startup capture, 3 October 2026

## Owner-observed phases

The owner opened Browser, confirmed that the initial address keyboard was still
displayed, then entered Google and confirmed Google was on screen. The owner
intended to search for earth but reported that Browser closed before the page
keyboard could be opened. No earth search or second keyboard activation occurred.

The paired Wi-Fi capture confirms running release 0.4.3.02. No runtime edits,
installation, limit changes, Seed writes or remote navigation were performed.
Phase labels come from owner reports; exact action timestamps are approximate.

## Measurement

Current boot: d90baf74-523a-43ce-aab9-3776b247fced.
Browser started at 127.892 seconds after boot and stopped at 261.512 seconds.

| Phase / time after boot | System available MiB | System swap used MiB | UI RSS MiB | Weston RSS MiB | Network RSS MiB | Page RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Before launch, 127.3 s | 617.2 | 0 | absent | absent | absent | absent |
| Initial address keyboard, 142.5 s | 440.0 | 0 | 195.7 | 82.2 | 63.0 | absent |
| Initial address screen, 193.3 s | 436.4 | 0 | 196.6 | 82.8 | 63.1 | absent |
| First captured page process, 208.5 s | 410.1 | 0 | 195.3 | 82.8 | 70.7 | 80.2 |
| Google loading / displayed, 223.7 s | 317.2 | 64.4 | 131.0 | 66.3 | 46.5 | 240.3 |
| Before recovery, 259.3 s | 297.5 | 65.1 | 120.5 | 68.1 | 36.5 | 237.2 |
| After closure, 264.4 s | 602.2 | 0.8 | absent | absent | absent | absent |

RSS includes shared mappings and cannot be added as unique memory. System swap
includes other services; its 65.1 MiB reading is not a violation of Browser's
64 MiB swap ceiling.

At 142.496 seconds the aggregate Browser UID cgroup was charged 242,921,472
bytes (231.7 MiB), with no memory.high events. At 218.208 seconds it was charged
335,663,104 bytes (320.1 MiB) and had 161 high events.

At 260.752 seconds the resource guard logged Browser pressure and requested a
stop. Final resource status recorded 2,515 high events, zero max events, zero
OOM events and zero OOM kills. The session scope recorded a 316.8M memory peak
and 60.9M swap peak; this is not the whole UID aggregate. Browser deactivated
successfully. This was a safeguard closure, not a recorded spontaneous process
crash or OOM kill.

## Conclusion

The address-screen startup has a substantial but relatively stable footprint.
The Browser UI remains near 196 MiB for approximately a minute before the page
process appears. Google alone then drives sustained reclaim near the aggregate
320 MiB soft threshold and fills the Browser swap budget. The page RSS rises
to about 240 MiB and then fluctuates near that level before recovery.

This reproduces insufficient usable memory within the Browser session budget
without extensions, image search, a second keyboard opening or an earth search.
It does not prove an allocation leak: both sampled processes plateau, and most
system available memory returns after the complete session closes. A process
local leak that vanishes on exit remains possible.

The next needed measurement is an allocation breakdown during startup:
per-process PSS/private/shared memory, cgroup anonymous/file/kernel and swap
charges, graphics attribution where supported, and address-free initialization
markers. This run used the existing diagnostics; it did not add those missing
measurements. Preserve containment while isolating GTK/WebKit, graphics, fonts
and initial native-keyboard costs.

## Artifacts

Owner-private artifacts remain in private-recovery/live-link:

- full-capture-20261003-091943.zip: initial address-screen capture
- full-capture-20261003-092054.zip: Google loading/displayed capture
- full-capture-20261003-092140.zip: shutdown and recovery capture
- inspect-20261003-091928.json, inspect-20261003-092043.json,
  inspect-20261003-092117.json and inspect-20261003-092145.json
- browser-startup-20261003-timeline.json: filtered numeric current-boot samples

The bounded live health monitor was stopped after recovery. The existing
Browser-specific journal filter is still defective; the complete boot journal
was used instead.
