# Bluetooth Audio 0

## First use case

A person puts an earbud into pairing mode, opens **Bluetooth Audio** on the
Deck, selects the device by its human-readable name, confirms the choice, and
hears GuideOS media through it. The Deck remembers the pairing locally and
attempts a bounded reconnect after later boots. The internal speaker remains
available as an explicit fallback.

## Small implementation

The RG35XX H uses the Bluetooth half of its RTL8821CS combination radio over
UART. The current vendor kernel exposes Bluetooth Classic, Bluetooth LE,
RFCOMM, HIDP, H4, and three-wire H5 support, and its boot log identifies UART1
as `/dev/ttyS1`. Live testing has now confirmed the `sunxi-bt` power path, the
Realtek H5 attachment, the model-specific 29-byte UART configuration, and the
RTL8821CS firmware. Together they produce `hci0` without interrupting Wi-Fi.

GuideOS uses:

- BlueZ for discovery, pairing, trust, and connection;
- BlueALSA for the A2DP audio path, avoiding a full desktop audio server;
- the SBC codec as the required interoperable baseline;
- a bounded Guide helper and framebuffer screen instead of exposing a command
  shell or raw D-Bus interface;
- a persistent pairing store owned by root and inaccessible to cartridges.

Optional codecs are not part of Bluetooth Audio 0. Earbuds must work with SBC
before AAC, aptX, LDAC, microphones, calls, or multi-device behavior are
considered.

## Interface states

The screen must distinguish:

1. **Bluetooth unavailable** — no `hci0`; show a diagnostic reference.
2. **Bluetooth off** — adapter exists but is intentionally powered down.
3. **Searching** — bounded discovery is active.
4. **Devices found** — show name and paired/connected state, never only an
   unexplained hardware address.
5. **Confirm pairing** — identify the selected device and requested capability.
6. **Connected for audio** — show the active output in the status area.
7. **Connection failed** — preserve the internal speaker and provide a plain
   explanation.

The user can forget a pairing from a separate confirmation screen. A cartridge
cannot silently pair, trust, connect, or change the active audio output.

## Audio routing

The Deck keeps one logical `default` output. When a paired A2DP earbud is
connected, that output targets BlueALSA; otherwise it targets the physically
verified internal ALSA speaker path. Starting or losing Bluetooth must not
leave a media process writing indefinitely to a dead device. The player may
restart at its current position after an intentional output change.

Volume remains a Deck policy. The existing hardware volume buttons adjust the
active output and continue displaying the same visible percentage indicator.
Bluetooth absolute-volume synchronization is deferred until tested with more
than one earbud model.

## Safety boundaries

- Discovery stops automatically after a short interval.
- Pairing and trust require an explicit local confirmation.
- Only the A2DP audio capability is enabled for this milestone.
- Device names and protocol output are length-bounded and treated as untrusted.
- Bluetooth does not grant a device access to Deck files, identity, input,
  microphone, networking, or the Developer Link.
- A failed Bluetooth service cannot disable safe shutdown or the internal
  speaker fallback.

## Physical proof sequence

1. Boot the Deck with Developer Link enabled and capture UART, rfkill, GPIO,
   firmware, and HCI diagnostics.
2. Produce `hci0` using the confirmed RTL8821CS power, H5, and firmware path.
3. Run BlueZ and perform a time-bounded scan with the earbud in pairing mode.
4. Pair, trust, and reconnect the earbud with local confirmation.
5. Send a short known audio sample through BlueALSA using SBC.
6. Route Node music and video audio through the earbud and test volume.
7. Reboot, reconnect, fall back to the speaker, forget the device, and perform
   safe shutdown.

Bluetooth Audio 0 is complete only after those behaviors are observed on the
physical Deck. A successful package build alone is not a hardware result.

Steps 1 through 5 have passed on the physical prototype with a soundcore P20i:
the Deck retained Wi-Fi, bonded and trusted the selected earbud, connected its
Audio Sink service, exposed a 48 kHz 16-bit stereo A2DP path, and delivered an
audible low-volume SBC test tone. The seed implementation now starts Bluetooth
without delaying the interface, reconnects only previously trusted devices,
routes Node music and video to a connected A2DP output, sends the hardware
volume buttons to the active output, falls back to the internal speaker, and
stops Bluetooth before the root filesystem is made read-only at shutdown.
Reboot/reconnection, media playback, fallback, and shutdown still require one
physical confirmation after the image is installed; forgetting-device UI is a
later interface task.

The Home menu includes **Bluetooth Audio**. It reports readiness, names the
connected output, and lets A retry devices the person already paired and
trusted. Startup validates the D-Bus process itself so an abandoned socket from
an interrupted run cannot masquerade as a working Bluetooth service.

On the first post-install boot, the menu appeared and the P20i reconnected, but
Node media still played through the internal speaker. Live diagnosis showed
that radio, pairing, A2DP, BlueALSA, endpoint discovery, and route selection
were all healthy. FFmpeg failed when opening the selected endpoint with
`Unknown PCM bluealsa` because it received the BlueALSA plug-in directory but
not the combined ALSA configuration path; the bounded player then correctly
used its speaker fallback. GuideOS now supplies an explicit `alsa-media.conf`
which loads both the isolated standard ALSA definitions and BlueALSA's PCM
definition, and the bridge passes it as `ALSA_CONFIG_PATH`. A quiet one-second
FFmpeg test opened the P20i PCM and completed successfully. The same fix was
installed live with matching hashes and added to the persistent seed packaging
path. Ordinary Node media playback through the earbud and a later reboot remain
to be physically confirmed.

## Installed candidate

On September 6, 2026, the current Bluetooth and media candidate was written to
the physically proven seed only after a verified failsafe capture was retained.
The prepared two-GiB root filesystem and the independent card read-back both
produced SHA-256
`42241D09CD622FD1B6F105B4B6BCEE3A27A05ED00D72878CB6D6450B702895CE`.
The installed Deck shell produced SHA-256
`0D3AE6D608E6B97EA29AFC5B39996608E9ED8222FC26991A098AF3CDC2E99057`.
This proves the intended bytes reached the card; boot, menu, reconnection,
Bluetooth routing, controls, speaker fallback, and shutdown remain physical
tests.

## Prototype provenance

The isolated compatibility build uses Buildroot 2025.02.17 with musl, BlueZ
5.79, BlueALSA 4.3.1, ALSA utilities, D-Bus, and SBC. The UART initializer is
from Radxa's open `rtkbt` source at commit
`72ef9b75374fdde945e0a19f6aba68e13d4d426d`. The checked RTL8821CS firmware
and 29-byte H5 configuration were taken from PanicOS commit
`114788bd4374cc5a380a6b909a9f9a59b4eabfc6`; the configuration MD5 is
`37338e0b8861a20ce877c0a10cbaaae3`. These inputs remain separately identified
so a later cartridge can carry complete license notices and reproducible
checksums.
