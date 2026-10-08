# GuideOS source baseline

Approved: 2026-09-03

Historical Buildroot baseline. The owner selected minimal Debian for the rework
on 21 September; see [Modern foundation 0](MODERN_FOUNDATION_0.md) and
[design alignment](docs/DESIGN_ALIGNMENT_0.md). Preserve these original pins as
history; this table does not identify the current diagnostic image's inputs.

| Component | Initial line | Current decision |
| --- | --- | --- |
| System builder | Buildroot 2025.02.x LTS | 2025.02.17, commit `d0820dd09916edcefc44e525355afbea30d5bee4` |
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
