# Audio-path-9: RG35XX H sample-transfer experiment

Status: installed and fully readback-verified on the seed. Boot and data unchanged.
Validation: 348 existing ARM tests, four new callback cases, release/overlay/service
and filesystem checks passed. Only the codec module changed; 21,268 other regular
files were preserved. Records: build/debian-audio-9/installation.json.
Physical speaker acceptance remains pending. This is GuideOS 0.3.2 audio-path-9.

## Scope and purpose

Owner requested a test build of the sample-transfer fix and a remote test protocol.
The board codec provider owns this experiment. It changes no application contract,
permissions, lifecycle policy or portable audio API. Evidence from the exact working
MuOS binary is recorded in MUOS_AUDIO_COMPARISON_0.md.

Only on anbernic,rg35xx-h, the codec's DMA preparation callback first uses the
standard ALSA configuration, then sets playback source width equal to destination
width and both burst lengths to 4 transfers. S16 uses two-byte widths; S32 uses
four-byte widths. The generic DMA driver remains unchanged. Other boards retain
the default callback; capture and generic preparation errors pass through.

Clock, FIFO programming, ramp, gain, output route, test samples and userspace are
unchanged from audio-path-8. Only sun4i-codec.ko is installed. The old module/image
and a fresh returned-seed backup remain available for rollback. Boot and data
partitions must remain byte-identical across installation.

The callback writes a GuideOS audio-path-9 DMA kernel message containing both
widths, both bursts and destination address. This records the configuration handed
to generic DMAengine; it is not a readback of hardware descriptors or proof of sound.
The existing one-shot buffer evidence remains available. No continuous extra
polling is added; logging occurs only at PCM hardware configuration time.

## Remote test after owner boots and enables Wi-Fi

Leave the Home screen visible so the existing countdown and LISTEN NOW banner
can be seen. No automatic test plays during boot. Use build/Guide-Link.ps1 with
-DeckAddress 192.168.4.70 (or the current owner-reported address).

1. Run -Action Health and -Action Inspect. Check link and audio service health.
2. Tell the owner the next test is one four-second normal file tone, preceded by
   a five-second on-screen countdown. Run -Action Tone-S16 once.
3. After the countdown and tone finish, run -Action Probe-Result, -Action Inspect
   and -Action Health. Preserve the generated private reports.
4. Require the fresh kernel line to say audio-path-9, src_width=2, dst_width=2,
   src_burst=4, dst_burst=4 and destination 0x05096020 (leading zeros allowed).
   Check successful aplay completion, nonzero matching buffer evidence, PCM
   progress, no new transfer errors, restored=true, Normal source and healthy
   restarted services. A missing or truncated log makes profile evidence
   inconclusive; do not call silence a valid negative result without that evidence.
5. Ask whether the owner heard this single tone, silence, or clicks/pops. Software
   completion alone cannot confirm audible output.
6. If S16 is audible, separately run -Action Tone-S32 with the same announcement
   and collection. Expect width=4 on both sides and bursts=4. Then confirm normal
   interface test-file playback and a stop/restart cycle. Each is a separate test.
7. If S16 is silent despite a verified profile, stop repeating it. Record that
   this narrow transfer change did not restore S16 playback. Review the remaining
   FIFO/ramp leads before choosing another experiment; do not silently alter them.

No internal oscillator is mixed into these file-tone tests. Tone-Internal remains
an explicitly separate diagnostic, since it bypasses the failing sample path.

## Validation boundaries

build/test-audio9-transfer.py compiles the actual callback with a mocked generic
ALSA boundary: S16, S32, capture unchanged and error propagation. The kernel module
is built against the installed kernel and checked for matching dependencies and
vermagic. Combined ARM image suites, active-release integrity, overlay integration,
service validation and filesystem checks are required before write. Rebase checks
every pre-existing file outside the sole module payload for preservation.

These checks cannot establish speaker audibility. The listening result above is
required before calling this a working fix or promoting the experiment.

## First physical result: 25 September 2026

Owner heard the isolated S16 file tone: "very quiet, but audible." This is the
first confirmed audible normal file playback in this investigation. The fresh
kernel line at boot-relative 101.792 seconds records widths 2/2, bursts 4/4 and
0x05096020 destination. The test completed with aplay return code 0; its 4096-byte
buffer matched the expected checksum 4026200373 and 3688 nonzero bytes. Restoration
succeeded and all three audio services returned healthy with zero restarts.

Private reports: probe-result-20260925-205057.json,
inspect-20260925-205106.json and health-20260925-205112.json in private-recovery/live-link.

Acceptance is partial: S16 is audible at low volume. S32, ordinary interface
playback and stop/restart listening checks remain unconfirmed. This establishes
that the combined transfer change restores this tested path; it does not identify
which of the burst or width changes is individually necessary. Keep gain unchanged
while establishing repeatability; loudness remains a separate follow-up.

## Follow-up results: same boot

Owner confirmed the existing interface audio-file test played two quiet tones.
Owner then confirmed isolated S32 was audible, also quiet. S32 report
probe-result-20260925-205508.json completed with return code 0, restored=true,
matching 4096-byte prefix (checksum 403110573, 1716 nonzero bytes), 48 kHz stereo.
Fresh kernel log at 351.544 seconds confirms widths 4/4 and bursts 4/4.

A subsequent isolated S16 test after service recovery completed successfully:
probe-result-20260925-205602.json, matching buffer, return code 0, restored=true.
Owner listening confirmation for this repeat is pending. Health reports show
local output idle and available after recovery.

Read-only loudness inspection: application volume 100%, PipeWire route channels
1.0 and unmuted; hardware DAC volume 58/63 and line-out volume 27/31. Diagnostic
waveform amplitude is deliberately 12% of full scale; existing interface test file
peaks at about 10%. These contribute attenuation even at displayed 100% volume.
No gain was changed. This identifies attenuation to investigate, not a calibrated
measurement of speaker loudness or proof that all low-volume behavior is explained.

## Repeat listening confirmation

Owner requested another S16 test and confirmed "Heard". probe-result-20260925-210240.json records successful completion, matching buffer and restoration. Repeat playback after service recovery is now owner-confirmed. Both isolated formats and ordinary interface playback are audible; low volume remains unresolved.
