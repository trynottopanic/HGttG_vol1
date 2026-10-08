# Multi-core operation guideline 0

Status: future build guidance; proposal for implementation and measurement, not an accepted device profile or a claim of physical performance.

Target: RG35XX H as the present GuideOS test target. The H700 provides four Cortex-A53 CPU cores, but usable parallelism is limited by memory, storage, thermal headroom and the installed image. Physical evidence must settle those limits.

## Purpose

Use the available cores to improve perceived responsiveness and throughput without making global navigation, lifecycle, capability ownership or recovery more complicated. Keep the foreground interaction path predictable while independent work proceeds in the background.

This supplements `RESOURCE_CONTENTION_0.md`, the common lifecycle contract, IPC Envelope 0 and the media/storage contracts. It does not authorize applications to assign themselves CPU priority or bypass Supervisor policy.

## Core rule

Keep one clear foreground path for input, focus, navigation state and rendering. Send storage, catalog, artwork, provider and maintenance work to a small bounded worker service or to application-owned workers contained by the application lifecycle.

The first implementation should use two workers: catalog/search; and storage/artwork/media preparation. Add a third only after measurement shows useful independent work and no harmful SD-card contention. Do not permanently pin workers to cores until profiling demonstrates a scheduler or affinity problem.

## Work that should be concurrent

### Navigation

Selection changes must read an indexed record and update visible focus without waiting for disk scans, metadata parsing, image decoding or provider calls. Background work may prepare the selected item and one or two adjacent items. The UI must remain usable before a complete external-card scan finishes.

### Catalog and indexing

Use a compact, immediately usable index followed by background enrichment. Directory discovery, record parsing and secondary-index construction may overlap, but canonical catalog writes remain transactional and owned by one component. Avoid several workers performing random reads over the same card.

### Artwork

Decode and scale thumbnails outside the foreground path. Keep a bounded cache for the current, previous and next likely items. Cancel obsolete requests instead of allowing fast navigation to create an unbounded queue.

### Media and provider work

Keep playback/provider processes separate from UI work. Queue artwork, queue construction and catalog requests asynchronously, while control messages remain small and responsive. Preserve the existing storage-owned and media-session boundaries; parallelism must not become a new central bus or authority path.

### Startup

Reach a “ready for navigation” milestone after input, display, minimal catalog and last-known state are available. Validate caches, reconcile the full catalog, discover optional providers and perform cleanup afterward.

## Work that should remain ordered

Keep these operations serial or transactionally coordinated:

- canonical catalog replacement and schema migration;
- provider handoff and capability transitions;
- checkpoint, pause, release, stop and shutdown acknowledgements;
- update activation, rollback and recovery-image operations; and
- seed-preserving, card-writing and physical acceptance workflows.

Parallel reads are not permission for parallel writes. Every stateful operation needs one owner, a durable commit point and a recovery outcome.

## Cancellation and stale-result rule

Every asynchronous request must carry a request ID, target record ID, catalog generation and cancellation state. A result may update the UI or cache only if its generation and target are still current. A late artwork or metadata result must never replace the user's newer selection.

Queues and caches must be bounded. When the user changes direction, discard or cancel work that is no longer useful. Cancellation is a normal lifecycle outcome, not a crash.

## Resource policy

Apply the accepted resource tiers: tier 1 foreground interaction; tier 2 communications; tier 3 background catalog, artwork and download work; and tier 4 spare-capacity maintenance and speculative prefetch.

Workers belong to the owning application or service for lifecycle and resource accounting. CPU time, memory, storage I/O and network capacity must be measured separately. A CPU weight is not a response-time guarantee, and four workers do not imply four useful cores under SD-card or memory pressure.

When playback competes with lower-priority work, preserve playback according to the accepted resource-contention contract. Pause or reduce optional prefetch, indexing and downloads before allowing foreground interaction to degrade.

## First build slice

Implement and measure:

1. remove disk and image work from the input/render path;
2. add two bounded workers with request cancellation;
3. add generation checks to every asynchronous result;
4. add current/adjacent artwork caching;
5. make the minimal catalog usable before full reconciliation; and
6. expose bounded diagnostic counters without recording user content.

## Required evidence

Report source tests, simulated tests, image tests and physical tests separately. On the actual RG35XX H, measure input-to-focus latency; focus-to-artwork latency; time to first usable catalog; full and incremental card-scan time; CPU use per core; I/O wait, memory pressure and queue depth; battery and temperature during background work; and behavior during playback, card removal, cancellation and shutdown.

No numeric worker count, affinity policy, cache size, CPU ceiling or deadline is accepted until supported by target-device evidence. Windows, emulation, source inspection and a successful image build do not establish RG35XX H performance.

## Non-goals

This guideline does not establish a new UI concept, require a radial wheel, replace the IPC or capability contracts, or turn all applications into multi-threaded programs. Parallelism is an implementation tool for measured latency and throughput problems, not a product feature visible as added control surface.