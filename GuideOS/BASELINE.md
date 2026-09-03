# GuideOS source baseline

Approved: 2026-09-03

| Component | Initial line | Current decision |
| --- | --- | --- |
| System builder | Buildroot 2025.02.x LTS | Pin 2025.02.17 |
| Linux kernel | Linux 6.18.y LTS | Pin an exact maintenance release after RG35XX H bring-up testing |
| GuideOS source | GuideOS `main` | Reviewed, stable project work |
| Hardware bring-up | `bringup/rg35xxh` | Temporary integration work before review and merge |

KNULLI and other working RG35XX H systems are hardware-support references, not
the GuideOS distribution base. Any reused patches, configuration, firmware, or
code must have its source revision, purpose, modifications, and license
recorded before inclusion.

An exact build-input lock containing source URLs and cryptographic hashes will
be created before the first candidate image is compiled. A branch name alone
is never sufficient release identification because its contents can change.
