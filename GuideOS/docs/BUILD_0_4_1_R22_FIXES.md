# r22 browser ownership and NDI diagnostics repair

The owner reported successful NDI connection and r21 installation, but failed
diagnostic capture and a browser display refusal. The live pinned Deck reported
r21 active, sequence 56, committed. The NDI operation log contained the Deck's
`invalid-request-or-local-failure` response for capture. A live inspection found
no browser service startup in the current boot journal.

## Diagnostic cause and working recovery

`deploy_board_diagnostics.begin_full_capture()` calls `report()` without importing
it. The installed handler catches unexpected exceptions and returns the generic
failure. The working source now imports the reporting function, but the installed
root helper is outside the existing signed shell update profile. r22 does not
claim to replace that root helper.

The PC capture client now handles that old-handler failure through the existing
fixed, authenticated `health`, `report`, and `inspect` operations. It creates a
bounded ZIP with explicit compatibility metadata: included readings and missing
complete retained log files/raw journal. Other rejection reasons and connection
failures propagate; incomplete snapshots are not promoted to completed captures.
Successful fallback is labelled in NDI 1.0.1. No additional approval or credential
exchange is required. PowerShell describes the result as a diagnostic capture.

A live invocation of the same PowerShell helper used by NDI saved:
`E:\DGttG\private-recovery\live-link\full-capture-20260930-192726.zip`.
This proves the PC-to-Deck compatibility path works, not that the full export
handler on the Deck has been repaired. The archive identifies its reduced scope.

## Browser ownership correction

The browser lease callback previously treated every pending Updates future as
a display owner. Updates polling ran only for the selected operations page, so
a completed future could stay pending after leaving Updates. A read-only status
query could therefore block launching the browser. This follows directly from
the source and matches a refusal before browser service startup; the private
in-memory guard state on the running Deck was not inspected directly.

Updates now distinguishes a pending interface-changing request from ordinary
status reads. Completed requests cease owning the display. Update completion and
status polling continue when the owner leaves the Updates page. Receiving an
upload does not acquire the display. Actual activation, queued installation,
trial and recovery still prevent a conflicting handoff. Video, active text entry
and shutdown retain their existing ownership. A refused handoff now explains the
actual blocking activity instead of displaying the generic control failure.

The browser frontend also converts input-provider startup failures into its
declared failure type so they return through browser restoration instead of
escaping the shell's browser error handler. A prior r20 journal contained a shell
exit labelled `UInputError`; this change contains that category without claiming
the underlying input provider has been physically validated.

## Delivery and evidence

NDI 1.0.1 is `E:\DGttG\GuideOS-NDI\GuideOS-NDI-1.0.1.exe`. The current running
NDI was preserved rather than overwritten or terminated. Close it before opening
the replacement, since both use the same Deck-facing port. The new executable
uses the existing identity, media folders and remembered relationships.

The signed r22 package is sequence 57, compatible with installed sequence 56.
It carries the shell guard, update panel, operations polling and browser failure
handler. Syntax, signature, canonical manifest identity, and all payload hashes
were checked. The paired Wi-Fi delivery was read back as `validated`, transaction
`9ed1cde6535ffbcd8a243a128624dcaf07ca8abc4909aed78692abf3a7b9b3b5`.
Installation and subsequent physical browser acceptance remain pending. No
repository test suites, playback probes or Seed writes were performed.
