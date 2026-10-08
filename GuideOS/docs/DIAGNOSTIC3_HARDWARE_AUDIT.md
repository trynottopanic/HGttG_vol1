# Diagnostic 3: complete non-controller hardware report audit

Audit date: 2026-09-22. Source run:
`build/debian-diagnostic-3/hardware-tests/2026-09-22-012829/diagnostics/ed673d0c-8f98-4d96-87d6-3a8e3150c5d9/`.

All 28 non-controller-data artifacts listed below were read in full, including
all 517 kernel-log lines, all 656 journal lines and every field of all 97 telemetry
records. This was not a keyword-only log review. The four controller/derived
report artifacts are assigned to the main audit and explicitly identified below.
This document records findings; no card, runtime, boot script or configuration
was modified during this audit.

## Findings supported by this run

### Wi-Fi failed to initialize, before the guided session

The SDIO function appears at uptime 2.424197 s. `rtw88_8821cs` identifies firmware
24.11.0 at 9.207416 s, then logs 18 failed SDIO read32/write32 operations with
`-110` and 19 MMC data-error/stop messages around 9.5395–9.5412 s. Reserved-page
and firmware download fail, chip information setup fails, and the driver probe
ends with `-110` at 9.541658 s. This is a recorded initialization failure, not
merely an unassociated interface.

`network.txt` contains only loopback, `wifi.txt` is empty, and `wifi-link.txt`
reports `No such device (-19)` with exit status 237. Starting wpa_supplicant and
reaching systemd's network target do not establish a usable Wi-Fi interface.
The earlier diagnostic 2 run enumerated wlan0; this run did not. The archive
does not establish the cause of that difference.

A separate cfg80211 warning at 2.336943 s says regulatory.db is malformed or its
signature is missing/invalid. Record and investigate this independently; the
logs do not establish it as the cause of the SDIO failure. The SDIO voltage-range
notice at 2.400967 s is another relevant observation, not a diagnosis.

These failures occurred before the diagnostic service's user-facing session.
There is no evidence that a pause, delayed answer, or controller interaction
caused them. The radio transport error is on `4021000.mmc`/SDIO, not evidence that
either filesystem card suffered the same failure.

### Bluetooth appeared, with unresolved early transport errors

Unlike the inspected diagnostic 2 run, `device-nodes.txt` contains hci0 under
the UART/serial device. The complete kernel log contains five out-of-order packet
messages at uptimes 10.263044, 10.668395, 11.085139, 11.496610 and 11.927039 s.
The driver identifies RTL8821, loads `rtl8821cs_fw.bin` and its config, reports
config size 25 / total size 36953, then firmware version `0x75b8f098` at
12.674336 s. This establishes enumeration and firmware initialization progress
despite H5-path errors. It does not establish discovery, pairing, connection or
accessory operation. No later Bluetooth errors appear in the saved logs, which
is not proof that the transport is fixed. No pause-related cause is established.

### Short graphics operation completed successfully

The panel is connected at 640x480. The inventory advertises 60 Hz preferred and
120 Hz alternate modes; the active CRTC is 640x480 at 60 Hz. The alternate mode
was not functionally tested. HDMI-A-1 is disconnected with no modes; HDMI
operation remains untested. Plane inventories describe capabilities, not tests
of every plane or format.

EGL exits zero and identifies Mali-G31 (Panfrost), EGL 1.5, OpenGL 3.1 and
OpenGL ES 3.1 using Mesa 25.0.7-2+deb13u1. The cube command exits zero within its
bound: uptime 472.94–503.60 s, final logged count 1799 frames in 29.983292 s,
60.000082 fps. The requested command was 1800 frames; retain the distinct logged
count. This is evidence of short sustained rendering, not long-term stability,
input latency or subjective visual quality. User-visible observations belong
to the controller/main audit rather than being inferred from these logs.

No kernel WARNING/BUG stack trace, GPU fault or previous DRM property-registration
warning appears in the full saved kernel log. Ordinary warnings and failures
described elsewhere in this audit do remain. Panel ID changes from `305201` to
`400003` during initialization; that message alone does not establish a defect.

### Audio exists, but initialization/routing remains unresolved

The H616 Audio Codec exposes playback device 0, and the headphone jack exposes
an input switch. The early kernel message `No soundcards found` precedes this
later registration and must not be mistaken for the final device state.

The journal records invalid ALSA udev GOTO labels (lines 18 and 22 in the rule),
an ALSA restore worker exit 99, missing `/var/lib/alsa/asound.state`, missing
`/usr/share/alsa/ucm2/ucm.conf`, and a failed use-case configuration import. ALSA
then uses generic initialization and its service finishes. Zero final failed
units therefore does not mean audio is configured correctly. These hardware
files alone cannot establish audible output, stereo routing, headphone detection
transitions or speaker muting; consult the complete controller evidence for
attempted optional checks and actual user responses.

### Boot, storage and lifecycle evidence

Linux `7.2.7-guide-debian2` on the Anbernic RG35XX H brings up four CPUs and
reaches the diagnostic service. The gamepad driver probes successfully and
advertises rumble; inventory includes power-key, volume, gamepad and headphone
devices. This does not replace the main audit's physical mapping/event review.
Start, Power and Reset remain excluded from requested tests.

The 58 GiB primary card has `/boot` (vfat), `/` and `/data` (ext4). The 233.2 GiB
secondary card and its vfat partition enumerate without a mount point.
GUIDE_DATA is reported clean on boot. Snapshot free space is 994M on root,
906M on data and 84M on boot. No filesystem-card I/O failure is recorded in these
logs. This is neither a media endurance test nor a secondary-card file-read test.

The final failed-unit inventory lists zero units, and deferred-devices is empty.
The controller service and report generator each record exit status zero.
The empty sampling-service log has no explicit exit status; its actual output
contains 97 valid records. Successful process exit does not mean every prompted
test passed. `completion.txt` records the request for orderly poweroff. The
journal ends at the cube-start message and does not contain the final shutdown
path, so completed shutdown requires separate evidence.

RTC initially supplies a January 1970 time; systemd advances it to its built-in
April 2026 epoch. `date.txt` reads April 13, not the host archive's September 22.
Use boot ID and monotonic time for this run; wall-clock timestamps are invalid
as real dates. RTC retention or time synchronization is not tested.

Other initialization observations retained for follow-up: dummy regulators for
pinctrl/panel/HDMI, USB PHY exclusive-vbus dummy-supply notice, PMIC DMA-mask
not-set notices, deprecated static GPIO bases, systemd's `unmerged-bin` taint,
duplicate `/run/lock` tmpfiles entry and a nonempty `/tmp` mount point. None alone
establishes the cause of the observed failures. USB host controllers and root
hubs enumerate, and a USB gadget target is reached; neither proves physical
port or accessory operation. The watchdog is registered with timeout 16 s;
there is no watchdog reset test. `aldo3: disabling` at 34.163201 s is observed,
but no logged failure ties it to a user-visible effect.

## Every telemetry sample parsed

All 97 JSONL lines parse. Each has the same five top-level fields, three memory
fields, four thermal-zone records and two power-supply records. Every power
property line was traversed, including the duplicated, identical
`POWER_SUPPLY_TYPE` entries present for both devices in each sample.

- Monotonic time spans 21.753056925–503.358738530 s (481.605681605 s). All 96 gaps
  are positive, 5.014420252–5.034719753 s; mean 5.016725850 s. No multi-sample
  gap or out-of-order timestamp was found. Sampling starts after radio failures
  and finishes during the last fraction of the cube command; it does not cover
  early radio initialization or completed shutdown.
- MemTotal stays 984304 kB; MemAvailable ranges 810736–833780 kB, ending 818572 kB.
  SwapFree remains zero and the separate memory inventory confirms no swap.
  Load averages vary; one-minute values span 0.18–0.83, with final 1/5/15-minute
  values 0.83/0.56/0.27. This is not CPU-utilization or memory-integrity testing.
- Battery reports present/online, `Discharging` and `Good` for all records.
  Capacity moves from 83 to 82%; voltage spans 3939000–3959000 microvolts,
  ending 3944000; current spans 401000–419000 microamps, ending 419000.
  Raw design/limit fields remain unchanged. Do not extrapolate endurance,
  validate charge capacity or infer battery degradation from this short sample.
- USB supply is absent and offline in every sample, health `Unknown`, USB type
  `[Unknown] SDP DCP CDP`; raw voltage values are 2000, 4000 or 6000 microvolts.
  These are not observations of an attached charger. Charging was not tested.

| Sensor | Minimum C | Maximum C | Peak uptime s | Final C |
| --- | ---: | ---: | ---: | ---: |
| CPU (zone2) | 34.730 | 43.154 | 443.169853168 | 41.048 |
| GPU (zone0) | 36.350 | 42.992 | 453.203508506 | 42.182 |
| DDR (zone3) | 35.864 | 42.749 | 458.222564550 | 42.020 |
| VE (zone1) | 34.892 | 41.453 | 463.238613052 | 40.562 |

All four sampled peaks precede cube start at 472.94 s. The telemetry has no
frequency, trip-point, governor or throttling-state fields; it cannot establish
absence of throttling or a thermal acceptance threshold. No thermal shutdown
appears in the captured logs.

## Explicit file-read coverage

Line counts include blank lines. Empty files were explicitly checked as empty.

| File | Lines / records | Audit coverage |
| --- | ---: | --- |
| audio.txt | 4 | Entire contents read |
| boot-id.txt | 1 | Entire contents read |
| cmdline.txt | 1 | Entire contents read |
| completion.txt | 1 | Entire contents read |
| controller-service.txt | 2 | Entire contents read; process status only |
| cube.txt | 34 | Entire contents read, including extension list and all frame statistics |
| date.txt | 1 | Entire contents read |
| deferred-devices.txt | 0 | Zero-byte file checked |
| device-nodes.txt | 21 | Entire contents read |
| displays.txt | 6 | Entire contents read |
| dmesg.txt | 517 | Entire contents read in contiguous chunks, no omissions |
| drm-connectors.txt | 418 | Entire contents read, including all plane/property/format entries |
| egl.txt | 20 | Entire contents read |
| failed-units.txt | 3 | Entire contents read |
| input.txt | 42 | Entire contents read; inventory only |
| journal.txt | 656 | Entire contents read in contiguous chunks, no omissions |
| kernel.txt | 1 | Entire contents read |
| memory.txt | 54 | Entire contents read |
| network.txt | 1 | Entire contents read |
| power.txt | 35 | Entire contents read |
| report-generation.txt | 2 | Entire contents read; process status only |
| samples.jsonl | 97 | Every JSON record parsed; every nested field traversed and compared |
| sampling-service.txt | 0 | Zero-byte file checked |
| storage-free.txt | 4 | Entire contents read |
| storage.txt | 7 | Entire contents read |
| userspace-reached.txt | 1 | Entire contents read |
| wifi-link.txt | 3 | Entire contents read |
| wifi.txt | 0 | Zero-byte file checked |
| controller-events.jsonl | 3707 | Main audit's assigned full event review; not duplicated here |
| controller-summary.json | 2199 | Main audit's assigned full summary review; not duplicated here |
| results.html | 18 | Main audit's assigned derived-report review; not duplicated here |
| results.json | 1699 | Main audit's assigned derived-report review; not duplicated here |

The directory contains exactly these 32 files. No unread non-controller file
was left in this directory. The controller/derived-report review must be joined
with this audit before claiming review of the entire run.

## Implications for the next decision

Preserve this run's radio distinction: Wi-Fi initialization failed; Bluetooth
enumerated with errors and functionality remains untested. Do not reuse the
diagnostic 2 radio statuses. Evaluate the main audit's guided-test findings
separately from these boot-time issues. Before choosing a radio fix, compare
the existing firmware/configuration, SDIO/UART power and binding evidence across
boots; these logs alone do not choose between causes. Before claiming audio
success, reconcile the optional-test responses with the ALSA configuration
errors. No reflash, driver reload, suspend, reset or physical-button experiment
is authorized or performed by this audit document.
