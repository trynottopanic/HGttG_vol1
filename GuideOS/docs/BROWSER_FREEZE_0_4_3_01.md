# Browser freeze investigation — 0.4.3.01

Investigated 2 October 2026 after the owner reported extremely slow Google image
loading, an unresponsive display and delayed Power response requiring a held
Power button. Earlier ordinary functional checks passed; Browser stability under
this workload did not. No corrective release or physical write was performed.

## Finding

Confirmed defect: the installed Browser service sets MemoryHigh=384M,
MemoryMax=512M and TasksMax=256 on guide-browser.service, but PAMName=login
migrates its workload into /user.slice/user-984.slice/session-1.scope. Journal
metadata confirms both Weston PID 900 and GTK Browser PID 907 belong to that
scope, not guide-browser.service. The scope reports 616.1M peak memory at exit.
The service limits therefore do not contain the complete Browser workload.

This matches systemd's documented PAMName behavior: descendants belong only to
the migrated session scope. Reference:
https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml
(PAMName section). Keeping the logind seat session is necessary for the existing
unprivileged display ownership path; simply deleting PAMName is not an established
repair. Correct containment must cover the actual session and all descendants,
with whole-session stop/recovery and protection for global system controls.

## Physical evidence

Boot: edb88af3-45a6-4425-99bb-2e251f82fe96, installed 0.4.3.01.
Times below are seconds since boot, unaffected by wall-clock correction.

- Browser attempted at 216.48 s and ready at 229.53 s.
- Available memory: 613.7 MiB at 200.6 s before Browser; 361.9 MiB at
  261.5 s; 95.3 MiB at 348.0 s; minimum sampled 57.7 MiB at 681.1 s.
- SwapTotal=0. Samples show repeated uninterruptible D states in WebKit,
  GTK, Weston, journald, NetworkManager, D-Bus and eventually PID 1.
- Repeated Panfrost resource purges and input processing lag follow Browser
  startup. Weston reports SYN_DROPPED at 666.65 and 674.56 s.
- Late total CPU samples are about 10–17%; this was not sustained saturation
  of all four CPU cores. The blocked states support reclaim/storage stalls;
  no retained kernel stacks or pressure counters identify each wait precisely.
- NetworkManager D-Bus queries time out repeatedly from 537.86 s. Wi-Fi remains
  associated in the last recorded provider state. Network latency alone does
  not explain the broad local process and input failures.
- Resident control overlay opening took 17,890 ms. Its event completed at
  691.09 s, providing another direct measure of impaired global responsiveness.
- logind records Power at 684.72 s, requests poweroff at 684.79 s; systemd reaches
  poweroff at 702.41 s and filesystem sync at 702.65 s. Shell cleanup reports
  no errors, shutdown_requested=false: shutdown came through logind, not the
  shell Power page. The journal has orderly shutdown progress despite the
  owner's held-button report; it cannot establish when the first physical press
  happened or whether the hardware eventually forced final power loss.

Strongest supported explanation: uncontained Browser memory growth caused severe
system memory pressure, accompanied by widespread blocked I/O/reclaim and input
loss. The containment failure is confirmed; the precise allocation/driver/I/O
trigger and the particular Google page behavior remain unresolved. There is no
recorded OOM kill, GPU reset/job timeout, card I/O error or kernel panic in this boot.
GPU acceleration is active (Mali-G31/Panfrost); software-only rendering is not the
explanation. Shader caching is disabled by the unwritable /nonexistent home,
a separate efficiency issue, not established as the freeze cause.

## Preservation and evidence locations

The inserted card was uniquely matched by model, serial, capacity, USB type and
three-partition geometry. Capture opened the raw disk with FileAccess.Read only.
Root, data, boot and bounded reserved-tail captures and SHA-256 receipts are in
build/release-0.4.3.01/returned-browser-freeze-20261002/capture.json.
The card was not mounted, repaired or written.

Read-only filesystem checks on the captured root and data report no structural
errors; the root has extent-tree optimization suggestions only.

Private raw journals and owner-state extracts remain outside the public source:
E:\DGttG\private-recovery\browser-freeze-20261002\

Key files: last-boot.txt; resources-summary.json; browser-process-journal.txt;
weston-process-journal.txt; root-fsck.txt; data-fsck.txt; and the copied
GUI/diagnostics records under guideos/.

## Repair acceptance

A subsequent repair must demonstrate limits on the actual Browser process tree,
not merely settings on the launcher service, while preserving logind/DRM access,
WebKit sandboxing and shell ownership. Under an excessive page workload, the
Browser must fail visibly or recover without starving input, Power, volume,
Wi-Fi and diagnostics. Close must reap the complete session before returning
display ownership. Repeating this workload on the Deck is still required.
