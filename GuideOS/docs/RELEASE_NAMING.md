# Release naming and update compatibility

On 6 October the owner selected `0.4.4.xx` for the combined pending changes.
The first revision, `0.4.4.01`, is signed sequence 73, built from a fresh capture
of installed `0.4.3.08` / sequence 72. Its system/native additions are delivered
as the combined root image. The internal signed UI payload declares base
sequence 72, but does not contain the system/native additions. Use the root
image for this release; do not present that payload as a complete network upgrade.
[Release and write evidence](BUILD_0_4_4_01.md) records card/physical status.

On 2 October the owner selected `0.4.3.xx` for the Planegotchi integration and
pending repairs. `0.4.3.01` is sequence 65, following the inserted Seed's actual
`0.4.2.05` at sequence 64. The prepared `0.4.2.06` was never installed and does
not consume an installed sequence. This image contains native/system changes;
its internal signed UI bundle deliberately accepts base sequence 65 only and
cannot be activated as a standalone network update from sequence 64.

The owner selected `0.4.2` as the consolidated release. Its later revisions are
`0.4.2.01`, `0.4.2.02`, and so on through `0.4.2.99`. Signed package version,
visible About/System Info and the source `VERSION` must match.

Version labels are display names, not the update ordering mechanism. Signed
`releaseSequence` orders updates; signed `baseReleaseSequences` lists compatible
bases. The highest accepted sequence governs downgrade handling. A new spelling
does not reset this history, change a release's content identity or bypass its
signature. `0.4.2` is sequence 59; `0.4.2.01` is sequence 60 with base sequence 59.
`0.4.2.02` is sequence 61 with base sequence 60 and retains the existing Wi-Fi
scope because its changes are confined to Python/interface files and assets.

The shared `release_version.py` keeps the existing bounded historical-label
validation for readers, including `0.4.1-home-v3-r23`. It enforces the two-digit
spelling when building new 0.4.2 packages. Old releases and their signed manifests
retain their actual names; renaming them would change authenticated identities.

NDI displays the Deck's actual active version. Its update picker discovers local
signed packages by numeric sequence across current and legacy output folders;
it no longer defaults to the old r21 folder or sorts labels lexically. Discovery
only chooses the starting folder. The Deck still verifies signature, target,
base sequence and delivery scope when a package is selected.

The 0.4.2.01 image audit verifies the real installed 0.4.2 validator accepts the
new signed label and the new validator accepts the real signed r23 package.
These package checks do not imply hardware acceptance or change the delivery
scope: the current Wi-Fi package replaces the signed interface generation;
native libraries and system services still require the full root image.
