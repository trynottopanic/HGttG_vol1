# Lightweight diagnostics 0

Status: included in candidate 0.4.1-home-v3-r17 with process sampling, timing aggregates, and Guide-Link health/report delivery. On-device monitoring overhead and physical playback measurements remain pending. This implements the owner's request for low-rate
CPU/process-tree, memory, error, media, command and navigation diagnostics.
It observes system behavior; it does not assign resources or override supervision.

## Collected information

| Area | Measurement | Limits of the evidence |
| --- | --- | --- |
| CPU | Five-second `/proc` deltas per process, parent links, PID plus start time, total CPU busy percentage | A process can exceed 100% when using several cores. Total CPU is normalized across cores. Work that starts and exits between samples can be missed. |
| Memory | Total, free, available, total-minus-available used, swap, per-process RSS | RSS is approximate and shared pages can appear in several processes. Do not sum RSS to infer total used RAM. |
| Process tree | Stable instance identifiers and parent links in each snapshot | Reparenting is observed at the next sample. A first observation has unknown CPU rate, not zero. Up to 512 processes; truncation and unreadable/exited processes are counted. |
| Audio | State, playback position, volume, queue time/bytes, queue-underrun count, decoder code, output loss and worker timeout | Queue underruns include startup and transitions; they do not prove audible dropouts or Bluetooth packet loss. No filenames, device addresses or titles are recorded. |
| Video | Boot-animation setup time, first-frame readiness, exit/timeout, frame count, mean/max draw-and-present time, frames exceeding 33.334 ms | Applies to the existing boot renderer. There is no general movie player to instrument yet. Physical display latency, panel defects and perceptual smoothness require hardware observation. |
| Commands | Audio handler duration and audio/Wi-Fi request-to-observed-ack timing | Ack time includes UI polling and does not mean pairing, connection or playback has completed. |
| Navigation | Input-handler time, draw time and earliest handled input to next frame submission | Does not include input-device latency before the shell receives an event or physical display scanout. Coalesced inputs share a frame. |

Timing records aggregate count, mean, maximum and number exceeding 100 ms over
30-second windows. These are investigative thresholds, not final service-level
requirements. No per-key, cursor-position, password or entered-text trace is kept.

## Error vocabulary

Structured codes include `SHELL_ERROR`, `COMMAND_ERROR`, `AUDIO_DECODE_ERROR`,
`AUDIO_WORKER_TIMEOUT`, `AUDIO_OUTPUT_LOST`, `VIDEO_ERROR`, `VIDEO_TIMEOUT`,
and `SYSTEM_ERROR`. Numeric OS errors are accompanied by their errno name,
including common `EIO`, `ENOMEM`, `ENOSPC`, `EACCES`, `ENODEV`, `ETIMEDOUT`,
`EPIPE` and `ECONNRESET`. Decoder codes retain their recognized GStreamer domain
and remain separate from OS errno values.
Unclassified system warnings retain severity/component and, when present, unit
and PID; unknown error numbers are explicitly `UNKNOWN`, not a guessed cause.

The collector follows the current-boot journal, replaying earlier boot records
so animation events are retained even if diagnostics start later. Only recognized
video metrics or warning/error summaries are copied. Raw journal messages are
discarded; original system journals remain available for deeper investigation.
Journal source timestamps and cursors are retained when available; a collector
restart can replay the same source records, so analysis should deduplicate those
cursors. Counters in the live snapshot cover the current collector lifetime.
Local event senders are attributed using kernel-provided socket credentials.
The event socket is a trusted local diagnostic interface, not an application
capability broker or a security audit trail.

## Storage and resource budget

- Current snapshot: `/run/guideos-diagnostics/status.json` (RAM).
- Persistent history: `/data/guideos/diagnostics/diagnostics.jsonl` plus three
  rotated files, each limited to 2 MiB: 8 MiB total. Oldest history is replaced.
- Records include boot ID, monotonic time and wall time. Monotonic time is used
  for intervals because the device clock may not yet be set.
- Writes batch for up to 30 seconds or about 64 KiB and flush at orderly stop.
  Abrupt power loss can lose the latest batch; these are not durable transactions.
- Five-second resource polling, up to 64 accepted events/second, 2 KiB event
  messages, fixed event fields, bounded recent-event list and journal input.
- Background nice level 15, CPU weight 10, quota of 5% of one core, memory high
  watermark 32 MiB and maximum 64 MiB. These are test ceilings, not measured
  requirements. The journal helper is included in this service's limits.
- Sample cost, interval, dropped events, journal liveness and log-write failures
  appear in the current snapshot. A full/unwritable log location discards a batch
  and records a write error instead of accumulating an unbounded queue.

The quota may delay diagnostics during heavy load; actual intervals are recorded.
History duration depends on process count and event rate. Rotated snapshots are
self-contained, so older process metadata is not needed to interpret a newer one.
Sampling does not keep inactive audio hardware or the display running.

## Reading and acceptance

On the Deck, `python3 /usr/lib/guideos/diagnostics/diagnostics_service.py --report`
prints the current snapshot. Returned seed logs live on the data partition at
`guideos/diagnostics/`. No network upload is performed.
`build/summarize-diagnostics.py <log-folder> --output <report.json>` creates an
offline summary of CPU-heavy processes, memory minima, sampling cost, event
counts and response-time aggregates. Keep the raw logs for tree reconstruction.

Software tests cover PID reuse, parent relationships, CPU deltas, memory
definitions, bounded rotation, secret-field rejection, journal summaries, and
timing aggregation. The disposable virtual Deck exercises the actual service,
live process/memory sampling, audio events, timing events and orderly shutdown.
Its exported logs are in `build/debian-audio-0/diagnostics-guest/` after a pass.

Physical acceptance must measure sample cost/CPU on the RG35XX H while idle,
playing audio, using menus, and scanning/connecting Bluetooth. Correlate an
observed fault with its boot ID and approximate time. Compare playback with
diagnostics enabled and disabled before concluding the monitor is sufficiently
lightweight. Stop/disable `guide-diagnostics.service` to turn monitoring off;
clients remain nonblocking and playback/navigation continue.

An unresponsive audio worker receives a bounded stack-dump request before it is
terminated. The Python call location is retained in the original service journal,
while the compact diagnostic log records `AUDIO_WORKER_TIMEOUT`. The dump does
not include local-variable values or media filenames.

References: [Linux process statistics](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html),
[Linux memory statistics](https://man7.org/linux/man-pages/man5/proc_meminfo.5.html).
