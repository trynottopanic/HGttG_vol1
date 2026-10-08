# GuideOS IPC Envelope 0 spike

The checked-in interface registry now includes `guide.media.library` 1.0 and
`guide.media.session` 1.0. Their nested record limits, authority boundary and
behavior are specified in `../../MEDIA_IPC_1.md`; generated metadata alone does
not implement either service.

Status: development-host compatibility evidence, not Deck or production acceptance.

This package tests the accepted Envelope 0 transport and wire decisions with a C
peer and a Python peer on Linux. It is deliberately a spike: it proves socket,
framing, CBOR-profile, credential, pidfd and descriptor interoperability before
the production broker library is designed around it.

## Selected codec path

- C object conversion: Debian/Ubuntu `libcbor`.
- Python object conversion: Debian/Ubuntu `python3-cbor2`.
- Guide profile enforcement: the small raw-byte validator in each language runs
  before generic decoding. This is necessary because general CBOR decoders do not
  uniformly reject duplicate keys, nonminimal forms, forbidden tags or excessive
  structure.

The profile validator does not interpret service operations or grant authority.
It only establishes that one payload obeys Envelope 0's bounded CBOR subset.

## Run in Linux

Dependencies:

```text
cc
libcbor-dev
python3
python3-cbor2
```

Run:

```sh
sh tests/run-spike.sh
```

The tests compile into a temporary directory and do not install a service or
modify an image. Passing under WSL is development-host evidence only. The C runtime subsequently
passed bounded ARM64 image verification; the live broker service and RG35XX H
physical validation remain required.

## Production-preparation candidate

`tests/run-production-prep.sh` checks deterministic interface generation, builds
the position-independent C library, tests descriptor cleanup, and exercises the
bounded Supervisor resolver, grant store and harmless health broker. The Python
authority components are behavioral references, not recommended resident Deck
daemons. See `../../IPC_PRE_ARM64_REPORT_0.md` before preparing an ARM64 package.
## ARM64 image result

`build-arm64.sh`, `install-arm64.sh`, `build/prepare-ipc-arm64.py` and
`build/verify-ipc-arm64.sh` produced and verified the runtime-only AArch64 package
inside a copied GuideOS staging image. No broker service is enabled and no card was
written. The exact result and hashes are in
`../../docs/IPC_ARM64_IMAGE_VERIFICATION_0.md`.
