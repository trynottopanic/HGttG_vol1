# Build 0.4.1 r20 physical-review corrections

## Requirements and changes

- **Nodes diagnostic row:** shorten the disabled explanatory row to `Diagnostics from Desktop Node`. It remains informational; the Desktop Node owns the capture action. Navigation skips disabled rows.
- **Node trust:** the shell reads the selected session identity and bounded saved trust record. It exposes `Trust this Node` for an untrusted session and `Revoke trust` for a trusted session. Failed bridge operations retain their error and do not claim a successful trust change. A trusted automatic reconnection opens the session view.
- **Video presentation:** videos retain the Video heading after startup failure, instead of entering the Music presentation. Recovery/status polling no longer clears the startup error. Catalog/source and output admission remain with the existing providers.
- **NDI capture:** provide an editable Deck IP, start discovery, report missing address/helper and command failures, locate Guide-Link from a packaged executable, retain full-capture support, and keep the helper process hidden. Several discovered endpoints require an explicit address. Node trust does not grant Guide-Link access; the existing pinned development-PC identity is still required.
- **Video backend, separate from the Wi-Fi release:** select the accessible `sun4i-drm` controller by driver identity and pass its device path to mpv. Live inspection found the connected DSI panel on card1. Automatic mpv card selection is a suspected startup cause; physical playback has not established the cause or acceptance of the correction. This file lives outside the currently supported replaceable shell/input/browser payload, so this change is source-only pending an offline root update or an approved service-update contract.

## Artifacts and evidence

- `build/release-0.4.1/wifi-r20/GuideOS-0.4.1-home-v3-r20.guide-release`: signed shell release, sequence 55, based on the active r19 release. The installed controller reports effective base sequence 42 and highest sequence 54; the package uses the reported effective sequence for compatibility. An offline-r19 assembly metadata omission causes this difference and is not silently rewritten on the Deck.
- `build/release-0.4.1/wifi-r20/source-verification.json`: Python syntax, manifest identity, signature and payload-hash checks passed. No test suites ran.
- `build/release-0.4.1/wifi-r20/delivery.json`: paired Wi-Fi transfer completed; the Deck validated the signed payload and awaits local owner approval. This record is a delivery snapshot, not an installation claim.
- `E:\DGttG\GuideNode-DeckDiagnostics-r20-dist\GuideNode-DeckDiagnostics-r20.exe`: rebuilt Windows NDI. The earlier executable remains intact. Executable construction does not establish an end-to-end diagnostic capture.
- Private live inspection: `E:\DGttG\private-recovery\live-link\r19-ui-fault-inspect.json`.

## Acceptance still required

On external power, approve r20 in Settings / Updates / Review ready update / Install now. Confirm Nodes labels fit, pairing/trust/revocation show the appropriate action, and a failed video retains a Video error. Run diagnostics using the rebuilt NDI and confirm the capture is saved. Video playback acceptance remains pending installation of the backend correction; the Wi-Fi shell release does not claim to repair its shared service.
