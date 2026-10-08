# Anbernic Failsafe Status

## Latest seed — Debian diagnostic 1

The first Debian test reached userspace but exposed missing display, GPU,
joystick and radio dependencies. The corrected diagnostic 1 is now on the seed,
with Linux `7.2.7-guide-debian1`. Full image readback verified SHA-256
`4BECEA7B5AC00FFF162E6D4241816E2626D57D93FDD4C769336849CD411EDA05`.
Physical acceptance of this second image is pending. See
`ROCKNIX_ALIGNMENT_1.md` for the comparison, corrections and validation record.
The first diagnostic image/reports and both recovery captures remain preserved.

## First Debian diagnostic, 21 September 2026

After the full backup below was completed, the seed was replaced with the
minimal Debian ARM64 diagnostic image and Linux `7.2.7-guide-debian0`.
Image size: 3,490,709,504 bytes. The entire written range was read back and
matched SHA-256:
`2D79860BA3E703F447F4749D62EBBDF777710D8F34FDDD591438A03D56A5AC44`.
The old backup GPT at the card's end was cleared and checked separately.
Evidence: `build/debian-minimal/flash-result.txt`.

The card now contains a diagnostic system, not the earlier Guide application
environment. The first physical test reached Debian and saved diagnostics;
the user observed automatic power-off. Display, game controls and radios still
need driver integration fixes. See
`build/debian-minimal/hardware-tests/2026-09-21-first-boot/RESULT.md`. Both recovery
captures below remain on the SSD unchanged.

## Full seed backup — 21 September 2026

Before the modern Linux rework, the complete current seed card was captured
read-only to `E:\DGttG\private-recovery\guideos-seed-full-2026-09-21.img`.
The matching `.txt` manifest records `CAPTURE_OK`, disk identity and all six
partition boundaries. Size: 62,239,277,056 bytes, including partition metadata
and space beyond the last partition. The saved-image SHA-256 matched a separate
full-card reread:
`133149EBF6410D17662EFA4E48856C91A9E4E12B9502836FEACBBD741CE72280`.

An initial buffered-read failure at the card's end was resolved by reading the
remaining bytes without read-ahead, followed by complete verification. The seed
was not written during capture. This is a verified pre-rework capture, not a newly proven
boot image: restore and physical boot testing of this backup remain unperformed.
The earlier physically proven baseline below is retained separately.

## Earlier physically proven baseline

As of September 6, 2026, the working GuideOS seed has a verified read-only
failsafe capture. The source card is the physically proven boot source; the
capture covers every partition and all bytes through the end of the final
partition.

- Image: `E:\DGttG\private-recovery\guideos-seed-failsafe-2026-09-06.img`
- Manifest: `E:\DGttG\private-recovery\guideos-seed-failsafe-2026-09-06.txt`
- Captured size: 6,442,450,944 bytes (6 GiB)
- Source disk size: 62,239,277,056 bytes
- Final partition end: 6,442,449,408 bytes
- SHA-256: `9C2E3A6A9935DF58FE32A45681D833EB5A499FFAAECB97CD1ACA1F6F6801F001`

The capture process independently hashed the same 6 GiB range from the source
card and required it to match the saved image before writing `CAPTURE_OK` to
the manifest. A later independent hash of the saved image produced the same
digest. The image is stored outside the public repository because it includes
the Deck's private, lived-in state.

The retained `GuideOS-RG35XXH-ddr3.img` and
`GuideOS-RG35XXH-ddr4.img` files are engineering candidates, not failsafe
images. The hardware audit records that both reached a green status light with
a blank display. They may now be removed during a later deliberate cleanup;
the private verified capture above is the recovery baseline.

The completed capture procedure was:

1. connect the known-working internal seed through the card reader;
2. identify its physical disk by model and exact capacity;
3. capture it read-only to a dated image on the SSD;
4. calculate a SHA-256 digest of the image;
5. read back and compare the source card's imaged byte range;
6. retain the image, digest, partition inventory, and physical boot record.

This verified capture is the failsafe safe-boot image. Restoring it to another
card remains a separate destructive operation and should be followed by a
physical boot test; restoration is not required before using the capture as the
pre-update recovery baseline.
