# Anbernic Failsafe Status

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
