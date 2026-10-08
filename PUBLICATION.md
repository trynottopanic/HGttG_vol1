# Public repository boundary

Target: https://github.com/trynottopanic/HGttG_vol1.

Public source includes the GuideOS shell/providers, NDI source, public foundation
documents, board/configuration material, original generic UI/boot assets and
desktop prototypes. The repository's existing software/documentation licenses
remain unchanged. Third-party material retains its own notices.

The following remain local: build outputs and receipts, handoff copies, physical
card captures/writers, credentials and saved owner state, packaged cartridges,
and Planegotchi-specific source, tools, tests, data, service, documentation and
artwork. The Home globe sheets derived from Planegotchi artwork are also excluded;
the public shell has a simple placeholder and handles the missing application.
The export omits the application-specific sections of the shared alignment
index while preserving the complete local document. Optional shell interface
names remain in generic GuideOS code; the application's implementation does not.

`.gitignore` prevents accidental future additions but cannot remove an object
already in Git history. The local unpublished `0.3 beginnings` commit contains
multi-GiB root images. The publication candidate is therefore prepared on top of
the existing GitHub `main` instead of inheriting that unpublished commit. Its
parent remains the published history, allowing a normal fast-forward update.
The original local checkout, history, releases and private files remain intact.

`tools/repository/publication.py --check` checks the source candidate's file
boundary, size and common credential patterns without printing secret values.
The export option copies only selected source files into a fresh publication
worktree; it does not push or rewrite history. Local audit reports stay outside
this repository. This is a focused preparation check, not a claim that every
feature or every historical link has been validated.

The installed version record is 0.4.4.03, while this source checkout can contain
later development. It does not supply the private base image or a fully pinned
from-scratch recipe for the installed release. Public release images and a
complete image build are separate preparation tasks.
