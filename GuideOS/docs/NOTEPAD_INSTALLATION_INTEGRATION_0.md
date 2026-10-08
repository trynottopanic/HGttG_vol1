# Notepad and cartridge installation integration 0

Step 1 follow-up, 26 September 2026: the [installed application host](APPLICATION_HOST_0.md) is implemented and host-verified, with staged ARM64 binaries and runtime dependency. The earlier probe-only readiness assessment below is historical. No seed write or physical acceptance is claimed. Cartridge catalog/installer work remains step 2.

Status: reviewed against the current source and last written 0.3.7 image on
26 September 2026. This integrates the Musings handoff into the implementation
plan; it does not install Notepad, enable external writes or claim a runnable
application cartridge. No seed or external card was written during this review.

## Sources and authority

- [Accepted Notepad behavior and runtime agreement](../NOTEPAD_CARTRIDGE_0.md).
- [Notepad transaction-core evidence](NOTEPAD_STORAGE_DEPENDENCY_0.md).
- [Proposed document broker interface](NOTEPAD_STORAGE_BROKER_DESIGN_0.md).
- [External Storage ownership](../EXTERNAL_STORAGE_0.md).
- [Cartridge packaging](../CARTRIDGE_FORMAT_1.md).
- [Current Supervisor/broker candidate evidence](SUPERVISOR_CAPABILITY_IMPLEMENTATION_EVIDENCE_0.md).
- [Latest installed release](RELEASE_0_3_7_HANDOFF.md).

The Musings chat confirms that the visual reconciliation is design-only and the
storage interface is proposed, not registered. Its earlier reference to only the
historical custom-PID-1 supervisor is superseded by the modern systemd-backed
implementation in `package/guide-foundation/`. The installed build admits the pinned harmless probe. The source now also
implements the bounded installed Python application host described in
[Application Host 0](APPLICATION_HOST_0.md); its new payload remains staged. Do not revive the historical C PID-1 shell.

## Current readiness

| Component | Current evidence | Remaining integration |
| --- | --- | --- |
| Field presentation, keyboard and typography | Shared shell renderer/input exist; owner accepted 24 px main, 28 px headings, 20 px secondary/control text | Application-owned semantic document model, editor/caret layout, out-of-process presentation and input/text sessions |
| Notepad executable | Accepted specification and three visual concepts; no `apps/notepad/` implementation | Document model, commands, private drafts/checkpoints, lifecycle and views |
| External card recognition | Read-only single-owner service installed; recognition works after reinsertion; startup race correction remains pending | Reliable startup acceptance, bounded cartridge catalog and authorized read handles |
| Format 1 host tools | ZIP inventory, SHA-256, normalized timestamps and card index/copy tools exist | Explicit application profile, typed entrypoint, `application.install.v0`, bounded metadata and compatibility validation |
| Deck application installer | Not implemented in current Debian shell | Owner agreement, internal staging, verification, durable transaction, immutable release activation, rollback, uninstall and app catalog |
| Envelope 0 | Common transport, generated registry and foundation control interfaces exist | Application-facing UI/text/private-storage and document contracts, richer generated field validators and codecs |
| Supervisor/capability Foundation 0 | Tested source, verified Foundation write record and binaries present in the later installed image; recorded live host integration | Application Host 0 now supplies the bounded Python profile in source; combine its verified payload with current state and physically verify it |
| Notepad external saves | Provider-private core and seven tests; proposed broker design | Provider-owned descriptors, grants, writable lifecycle, retry/recovery, quotas, safe eject and physical exFAT validation |

The latest written root is
`353952426007CD096E2926BD93DDBB21D490CE5D1D01EDF6572E208219E134D1`.
The Foundation installation record reports `ROOT_WRITE_VERIFIED` at
2026-09-26 05:50:40 UTC, and a read-only check of the later saved image confirms
`/usr/libexec/guideos/guide-supervisor0` is present. Both it and
`guide-capability-broker0` byte-match the verified Foundation ARM64 build. This supersedes the original
Foundation handoff's unwritten-candidate status. It does not establish physical
lifecycle/grant acceptance or current live service health. The old Foundation
image predates later installed changes: preserve its existing payload when
integrating onto a fresh current seed capture, rather than writing that older
whole image or bypassing its stale prewrite guards.

## Visual handoff reconciled with current implementation

The three reference images are:

- [Document list](../design/ui-theme-drafts/guideos-field-theme-notes-list.png).
- [Editor](../design/ui-theme-drafts/guideos-field-theme-notes-editor.png).
- [Empty state](../design/ui-theme-drafts/guideos-field-theme-notes-empty.png).

Use Field Theme roles and the physically accepted text sizes, not a scaled bitmap
of the large mockups. Shell-owned status/footer, Menu, Power and the existing
shared keyboard remain authoritative. Build list, empty, editor, actions and
supporting confirmation/progress/error/recovery views from semantic state.

The editor mockup's `X Rename` is illustrative: rename is explicitly deferred
by the accepted 0.1 requirements. Its vague `Saved locally` and example `SAVED`
labels must become acknowledged states with explicit `External`, `Internal
draft` or `Unsaved` location. Never render fixture save success, timestamps or
text as runtime evidence. The application needs independently releasable visual,
action-input and text-input grants; importing the trusted in-process shell
renderer into an otherwise unrestricted Python app does not supply that boundary.

## Installation path and document-save path

Installation reads the external cartridge and writes an immutable program copy
and agreement into internal storage. It does not require writable external
storage. The first end-to-end installation milestone can therefore install,
launch, checkpoint an internal draft, return Home and relaunch after removing
the cartridge. This exercises the accepted offline/internal-draft behavior;
it does not complete Notepad's full external-document acceptance campaign.

External saving separately requires the `documents.notepad` service and grants.
Complete release acceptance still includes real external save/open/recovery and
all requirements in Notepad sections 11 and 12. An unavailable optional document
feature must be reported explicitly, never mistaken for a working save path.

## Concrete contract gaps to close

1. **Application package profile.** `New-GuideCartridge.ps1` currently emits a
   null entrypoint. `Test-GuideCartridge.ps1` rejects non-null entrypoints and
   both restrict install actions to older pinned features. Define and implement
   the accepted validated module/callable form and application metadata together
   in builder, verifier and Deck installer. Keep legacy packages valid. Merely
   adding an action to an allow-list does not implement installation.
2. **General application hosting: source step complete.** The bounded Python
   profile now uses installed policy/identity, kernel confinement, shell-owned
   presentation/input, durable private storage and observed lifecycle results.
   See [its evidence and deployment limits](APPLICATION_HOST_0.md). The installed
   Deck still has the earlier probe-only payload.
3. **Generated data types.** The current schema generator and foundation control
   codec support `uint` and `bytes16`. Documents need bounded UTF-8, bytes32
   digests, bounded result collections, descriptor schemas and retry metadata.
   Extend matching C/Python validation and fixtures; define numeric field keys,
   limits and typed outcome mapping before registering the proposed interface.
4. **One physical mount owner.** The writable-provider handoff must not produce
   two independent owners of TF2. Retain the old read-only service as a test and
   rollback configuration, with mutually exclusive ownership when selecting the
   new lifecycle. Read-only and writable operations share the authoritative card
   identity/insertion state in the active owner. No application gets mount paths.
5. **Transaction-core completion.** The current constructor opens provider paths;
   it is not yet the proposed provider-owned-FD interface. It has no public list,
   open/FD transfer, client retry-token/result ledger, writer queue, persistent
   quotas or safe-eject integration. `_record` flushes the record file but does
   not fsync its parent after publishing it; successful cleanup also lacks that
   directory flush. Recovery reads/listing require bounded parsing and validated
   leaf names. Reinsert recovery must distinguish stable card identity from
   revoked old-generation authority: inspection may classify prior transactions,
   but any resumed action needs a new grant and explicit decision. These are
   integration requirements; the seven passing tests do not establish durability.

## Recommended implementation order and acceptance

1. Reuse and extend Foundation 0 into an installed-application host with enforced
   private storage and resource limits, plus shell-owned presentation/action/text
   adapters. Prove one unprivileged test application with the required grants,
   ready/stop/checkpoint transitions and denied ambient access.
2. Implement the bounded cartridge catalog/read-handle path and internal
   `application.install.v0` transaction using that host for health checks. Test
   altered archives, card removal mid-copy, interrupted activation, same-version
   content conflict, rollback and separation of uninstall from private data.
3. Implement Notepad from its accepted specification, with Field presentation,
   shared text entry, internal drafts and checkpoint recovery. Produce its
   deterministic `.guide`, `.gde`, sidecar and validation record. Prove install,
   remove cartridge, relaunch and recover an internal draft.
4. Complete the document provider and broker interface above; add Notepad's
   external-document adapter. Test read/write grant separation, revocation,
   stale card/destination, conflict, bounded retries, safe eject and recovery.
5. Integrate the exact validated payloads with pending star/caption and card-retry
   changes onto a fresh seed capture. Perform physical cold-start detection,
   install/removal/relaunch, maximum-size editing, exFAT save/reopen/interruption,
   and memory/timing/descriptor measurements. Record exact release/package hashes.

## Checks performed for the initial review (before Application Host 0)

`build/notepad-integration-review/` contains current evidence:

- 23 Linux tests pass: 16 recognition/lifecycle tests and seven Notepad-store tests.
- Strictly compiled foundation core and control-codec tests pass.
- Existing generated Envelope outputs match their registry (`--check`).
- Source inspection verifies the probe-only launch/policy boundary and the
  application entrypoint/install-action rejection in current cartridge tools.
- No general Notepad runtime, application installer, writable broker or new
  physical behavior is claimed. The proposed interface remains unregistered.


## Step 2 implementation follow-up — 26 September 2026

The owner-approved cartridge catalog, internal installer, agreement flow, isolated
health checks and recovery implementation are now described in
[Cartridge Installer 0](CARTRIDGE_INSTALLER_0.md). Its evidence supersedes the
earlier statement that the installer is the next implementation task.

The harmless reference application exercises delivery and retained private data;
it is not Notepad. The next application task remains implementing Notepad from
its accepted specification, including its storage categories and internal draft
recovery. External document writes still require the separate provider/broker
work. Seed installation and physical Deck acceptance remain separate gates.
