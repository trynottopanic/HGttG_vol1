# Browser pressure investigation, 3 October 2026

## Evidence and outcome

A paired read-only Wi-Fi capture from the running Deck confirmed release
0.4.3.02, release id
4cc0a0b6b9be00a529a760fcc121bdbe4a2fe945447ffd8dd8dec265bc3a1f13.
This is device evidence, rather than source-only validation.

Current boot: 33e90611-c34d-48a3-8655-733ed5511439.
Browser started at approximately 257 seconds after boot. Resource recovery began
at 391.949 seconds; Browser stopped at 392.787 seconds.

The resource status records memory pressure, 2,089 memory.high events, zero
memory.max events, zero OOM events and zero OOM kills. The configured soft
threshold is 320 MiB, hard ceiling 384 MiB, and Browser swap allowance 64 MiB.
The guard can close Browser after sustained soft-limit reclaim/throttling even
while the rest of the system has ample available memory. This capture therefore
does not show a hard-ceiling overflow or an OOM kill.

## Current-boot resource timeline

The retained logs contain multiple boots; the following samples are filtered to
the current boot. Times are seconds after boot. All memory values are MiB.

| Time | System available | Swap used | Browser UI RSS | Weston RSS | Network RSS | Page RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 258.5 | 600.8 | 0 | absent | absent | absent | absent |
| 263.6 | 525.7 | 0 | 62.9 | 84.9 | absent | absent |
| 268.6 | 419.6 | 0 | 212.1 | 84.9 | 62.8 | absent |
| 344.7 | 409.5 | 0 | 216.6 | 86.7 | 61.4 | absent |
| 349.8 | 360.3 | 0 | 215.2 | 87.9 | 68.3 | 175.9 |
| 365.0 | 318.2 | 64 | 152.8 | 71.3 | 45.7 | 221.0 |
| 390.4 | 281.2 | 64 | 142.4 | 70.3 | 35.1 | 219.5 |
| 395.4 | 599.5 | 0 | absent | absent | absent | absent |

PIDs: Browser UI 914, Weston 904, WebKit network 946, page renderer 1140.
RSS includes shared mappings and must not be summed as unique physical memory
or compared directly against the aggregate cgroup limit. Decreasing RSS during
pressure also does not establish that allocations were freed, since pages may
have been swapped or reclaimed.

The session scope journal records a 314.2M memory peak and 62.6M swap peak.
That is one scope, not the entire Browser UID budget, which also contains
user-manager/helper overhead.

## Interpretation and limits

The largest early increase occurs in the Browser UI process before the retained
samples show a WebKit page process. Its RSS then remains nearly flat at about
217 MiB for roughly 80 seconds. The page process adds substantial demand and
the session exhausts its swap allowance before the guard closes it.

The evidence supports excessive startup overhead plus page demand exceeding the
usable session budget. It does not establish a leak. The browser source uses
one WebView and an ephemeral network session; the native keyboard renders a
640x480 image. GTK/WebKit initialization, font caches, graphics allocations and
native-keyboard rendering are candidates for the early increase, not confirmed
allocation owners. The current logs do not include PSS, memory.stat, allocation
stacks or precise page-navigation phase markers. The page identity is based on
the owner's report; diagnostics deliberately do not record visited addresses.

System available memory recovers almost to the pre-launch level after closure.
This gives no evidence of a substantial allocation surviving this launch.
It cannot exclude a leak inside the process that disappears when it exits.

## Diagnostic defect and next measurement

The Browser-specific journal request fails with:
"+" can only be used between terms.
deploy_board_diagnostics.py combines the -u option with a bare "+" disjunction.
The full boot journal recovered the necessary timeline for this investigation.

Next profiling should measure blank-browser startup, keyboard open/close and
one page load separately, with per-process PSS and anonymous/file/shared memory,
aggregate cgroup memory.stat/current/events and swap, and address-free phase
markers. Repeated idle and navigation measurements can distinguish a one-time
cache/initialization cost from continued allocation growth. Keep the guard and
limits intact while measuring; simply raising the ceiling would hide the
problem and reduce protection.

## Capture provenance

Paired capture: full-capture-20261003-090112.zip.
Inspect: inspect-20261003-090040.json.
Health: health-20261003-090122.json.
These owner-private artifacts remain under private-recovery/live-link.
Extracted current-boot numeric timeline:
browser-pressure-20261003-timeline.json in the same private directory.

No runtime changes, activation, Seed write or controlled Browser relaunch were
performed during this investigation.
