# Live diagnostic connection to the development PC

The paired PC opens one persistent SSH connection to the Deck's existing port
2222. The Deck returns cached health snapshots every ten seconds while the PC
monitor is running. No new resident Deck daemon, radio-discovery loop, PC server,
firewall opening or internet service is introduced. The SSH key pair and pinned
host identity from the installed deployment bootstrap are reused.

This implements the bounded diagnostic-return portion of NETWORK_DEPLOYMENT_0.md.
Systemd continues to own services, the shell retains input/display ownership,
and the existing controller handles explicit small-release activation and rollback.
Read-only diagnostics do not pause applications or require external power.
Existing update power/quiescence/rollback rules still apply to updates.

## Use

Boot the Deck, connect its saved Wi-Fi, and read its address in System Status.
The PC can remain connected to the router by Ethernet. The two devices must be
able to reach each other on the local network; guest-network isolation may prevent
this. Use the actual Deck address in place of the example below:

```powershell
./build/Guide-Link.ps1 -DeckAddress 192.168.1.42
./build/Guide-Link.ps1 -DeckAddress 192.168.1.42 -Action Report
./build/Guide-Deploy.ps1 -DeckAddress 192.168.1.42 -Action Status
```

The first command watches until Ctrl+C. It maintains one `live.json` in
`E:\DGttG\private-recovery\live-link`, not an unbounded history. It records the
PC receipt time, Deck boot identity, CPU/memory, service freshness, audio state,
volume, connection counts and recent structured diagnostic events. Missing or
older-than-fifteen-second snapshots are marked stale. A stopped monitor or lost
connection is explicitly disconnected, with the last reading labeled as history.

The monitor reconnects after 5, 10, 20, 40 and then at most once per 60 seconds
while unreachable. It never turns Wi-Fi on or overrides Disconnect. If DHCP gives
the Deck a different address, restart the monitor with the new address. A router
reservation can avoid that manual step; no router configuration is changed here.

`Report` writes a timestamped private JSON report with deployment identity,
cached health, the last 64 KiB of structured diagnostic logs, bounded PCM status
and the onboard codec mixer settings. A report explicitly marks unavailable and
truncated data. Media filenames, Wi-Fi credentials, device aliases and Bluetooth
addresses from audio status are omitted. Reports do not include arbitrary files
or raw service journals. Existing bounded Deck logs remain available until normal
rotation; fetching does not erase them. Private report accumulation on the PC is
owner-controlled; continuous monitoring overwrites just one current file.

## Settings / Diagnostics screen (0.4.1 working source)

Settings > Diagnostics now displays the Deck's current IPv4 address, Wi-Fi state, paired SSH port, and the PC helper instructions. From the Windows GuideOS project folder, use `./build/Guide-Link.ps1 -DeckAddress <IP> -Action Report` for a bounded report, or omit `-Action Report` to watch live health until Ctrl+C. Health and Report include bounded per-process CPU time/utilization and shell timing summaries (mean, approximate p50/p95, maximum and over-100-ms count); process command lines, paths and PIDs are omitted. Reports remain under `private-recovery`; the Deck does not initiate a connection or expose a new listener. This is source-only until 0.4.1 is built and installed.

## Fixes and boundaries

The existing Guide-Deploy helper can stage/update/roll back shell and shared-input
releases over the same paired network path, up to 100,000,000 bytes per complete
release. The monitor itself never downloads or activates a fix. Reports remain
readable during an update; the next heartbeat reflects the replacement shell.

Audio-provider, networking, kernel and controller replacements are outside the
current release scope. This extension itself therefore needs a bootstrap card
installation; sending it as a normal shell release would not install it. General
remote command execution and arbitrary root-file edits are not added. A bounded
service-update/recovery contract is the next step for delivering those fixes.

The candidate also carries the source corrections from the last physical review:
size-based journal retention (so first time synchronization cannot age out boot
logs) and correct HCI controller counting. It preserves returned pairing keys,
saved Wi-Fi, media/data and user volume; it does not recalibrate audio again.

## Acceptance

Protocol tests exercise private-field omission, bounded/truncated reports,
rejection of caller-supplied paths/commands, stalled-peer deadlines, reconnect
after loss and explicit stopped-monitor state. A disposable ARM64 guest tests
the real paired SSH connection and report/monitor/reconnect behavior, alongside
the existing audio/overlay shutdown checks. Virtual display/input/audio fixtures
do not establish physical Wi-Fi reachability or live Deck performance. On device,
watch readings, play audio, fetch a report, disconnect/reconnect Wi-Fi and confirm
stale/live transitions before relying on this as the routine diagnostic path.

## Installed candidate

GuideOS 0.3.2, diagnostic-link-0, was installed on 25 September 2026. All 31
deployment/link tests passed on the PC and ARM64 runtimes; the final image passed
real SSH report/monitor/reconnect acceptance and virtual audio/overlay/shutdown
checks. Source payload, filesystem, SSH/unit configuration and saved-state checks
passed. These do not establish physical Wi-Fi acceptance.

Disk 4, Transcend seed partition 2, received the candidate. Full 2 GiB readback
matched `F31EC43CB5402160F4C8249F0CE8409FCE0D2B635D46B12B4ED13037ACA67666`.
Boot and data regions were verified unchanged. Saved Wi-Fi, Bluetooth pairing
keys, user volume and deployment identity matched the returned-seed capture.
Evidence: `build/debian-link-0/validation.json` and `installation.json`.

Physical connection verified on 25 September 2026 at the owner-supplied address
192.168.4.70. The paired PC retrieved a report at 17:10:21 UTC and the background
monitor subsequently received live health readings. Evidence is held privately
in `E:\DGttG\private-recovery\live-link\first-physical-report.json` and
`live.json`. The monitor replaces its current snapshot every ten seconds.

The first report showed local audio selected, stopped playback, an unmuted route,
enabled DAC/line-out/speaker switches and a closed PCM device, consistent with
idle playback. It does not establish the cause of speaker silence. No Bluetooth
controller was reported during this boot; earlier successful Bluetooth playback
does not establish controller availability on every boot. Physical Wi-Fi loss
and reconnection, active speaker playback capture and remote release activation
remain separate acceptance steps.

## Diagnostic-link-1: board inspection and direct speaker probe

The next seed revision adds `Inspect` and `Speaker-Probe` to `Guide-Link.ps1`.
Inspect returns bounded current-boot kernel, audio, Bluetooth and link journals,
service states, available GPIO/DAPM debug state, controller names and the latest
speaker-probe result. These explicit reports may contain system identifiers and
journal text; keep them in the private recovery directory. Routine health polling
still uses the smaller cached snapshot.

Speaker-Probe is an explicit idle-only board bring-up operation, not an application
API. It starts an independent systemd oneshot with a 40-second execution limit.
The worker holds the deployment lock, backs up the codec mixer, remembers active
audio services, stops them, and plays a three-second 440 Hz stereo tone through
ALSA directly. The generated tone has a short fade and 12 percent sample amplitude;
DAC/line gains use the existing 58/27 settings. It records PCM and available board
routing state, restores mixer settings and restarts only previously active audio
services. It does not resume media automatically. ExecStopPost repeats cleanup
if interrupted; a failed restoration retains its plan and reports failure.
Missing board debug interfaces are reported unavailable, not inferred healthy.

The probe can make audible sound and temporarily removes normal audio availability.
It rejects active playback and stale audio status. It cannot establish audible
success without the owner's observation. The paired PC can fetch Inspect after
starting the probe; no permanent shell access or arbitrary command is added.

This revision also makes silhouette samples outside the authored mask return
black instead of extending pole pixels beyond the globe. Neighbor samples use
the same bounds, preserving the horizontal cloud fringe. A software GLES render
test checks three animation phases and a black exterior; physical display
acceptance remains pending. A missing `/etc/default/locale` found in returned
SSH journals is supplied with `LANG=C.UTF-8` to remove repeated PAM errors.

Diagnostic-link-1 was written to the seed on 25 September 2026. Full root
readback matched `28CF2F18EB1C09EED780339D5E5288F9530CD237C68FA5C0DF3146693607C79B`;
boot and data regions remained unchanged. The returned seed was captured before
writing. Evidence: `build/debian-link-1/installation.json`, `validation.json`,
`payload-verification.json` and `shader-validation.txt`. Thirty-nine protocol,
client and probe-recovery tests passed; the virtual guest passed real SSH Inspect,
report/reconnect and audio/overlay/shutdown checks. Direct physical speaker-probe
output and the Deck's displayed animation remain pending owner testing.

## Audio-path revision 2 (candidate, not installed)

Implemented after the full-flow audit in `AUDIO_FLOW_AUDIT_0.md`:

- `Audio-Path` returns bounded card and component DAPM, codec register readback
  when available, GPIO, relevant clock-summary rows, regulator summary, PCM
  format/status, a compact PipeWire nodes/ports/links graph, mixer state and
  fixed test-file identity with per-channel peak/RMS. Missing and truncated
  evidence is explicit. No recording of microphones or arbitrary files occurs.
- `Probe-Result` retrieves the full direct-probe record. `Inspect` now returns
  only its state/restoration summary to avoid duplicating a large result within
  the journal report.
- The explicit idle-only speaker probe emits six seconds: left, right, then
  stereo, two seconds each. It sets and records Stereo selection and disables
  reversed DAC mixing as well as setting the existing gains/switches. It records
  bounded hardware snapshots before playback, during each segment and after
  restoration. Existing timeout/cleanup and deployment exclusion remain.
- `playing` is no longer published merely because preroll completed. Immediate
  start failure is reported; asynchronous startup waits for PLAYING confirmation.
- The overlay and telemetry now call GStreamer empty-queue notifications
  `Queue empty` / `queue_empty_events`. Older `underruns` log fields remain
  readable for historical compatibility, without presenting them as current
  hardware XRUN measurements.
- The virtual acceptance test captures the actual PipeWire sink monitor through
  pw-record while Guide's normal provider/worker plays known two-channel audio.
  It checks nonzero per-channel peaks and the expected RMS ratio in addition to
  lifecycle checks. Reference: https://docs.pipewire.org/page_man_pw-cat_1.html

The candidate is built from the verified diagnostic-link-1 root. It must be
rebased on a fresh returned-seed capture before installation if saved root state
has changed. The seed is currently in the Deck; the USB reader reports zero
capacity. No physical write or physical audio-fix claim is made for this revision.

Audio-path revision 2 was installed on 25 September 2026 at 19:08 UTC after a
fresh returned-seed capture. The tested payload was applied to the returned root;
all Guide runtime files match the tested candidate, and current saved network,
pairing, audio and deployment state were preserved. Full 2 GiB readback matched
`C268FF61B752510659ADE3F6C1C69508D8B5E0992ECC25926E338C443BB1C959`.
Boot and data regions were verified unchanged. Evidence is in
`build/debian-audio-2/installation.json`, `install-validation.json` and
`rebase-verification.json`. The earlier candidate-not-installed note is superseded
by this installation record. Physical deep-path capture and the segmented speaker
probe remain pending the next boot; speaker silence is not yet resolved.
