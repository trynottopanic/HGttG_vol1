# GuideOS Future Framework 0

Status: design direction, not yet a frozen protocol  
Last reviewed: 2026-09-09

## Purpose

GuideOS should let a small Deck present useful information and controls without
requiring every service or application to run on the Deck itself. The RG35XX H
prototype should eventually be able to:

- read Wikipedia as a properly structured, pleasant document, online or from a
  local library;
- show selected communications from services such as Discord and Steam without
  handing account credentials to the Deck;
- play simple local games and control games streamed from a trusted Node;
- use Android applications through the best execution route available;
- accept understandable, inspectable `.guide` packages made by people who do
  not have computer-science training.

The framework must not pretend that all of these jobs are technically the same.
It should give them the same navigation, permission, packaging, and trust model
while retaining the most suitable delivery method for each one.

## The central decision: one application contract, three surfaces

A Guide application describes what it offers and what powers it needs. It can
then present one or more of three kinds of **surface**. A surface is simply the
thing the Deck knows how to show and operate.

1. **Guide View** — structured information rendered by the Deck. This is the
   preferred surface for Wikipedia, messages, lists, forms, settings, and
   Recipes. It is small, accessible, cacheable, and works across different Deck
   screens.
2. **Media Surface** — audio or video decoded by the Deck. This is for local
   files, Node libraries, radio-like streams, and passive video.
3. **Remote Application Surface** — a picture and sound rendered on a Node,
   with a limited set of inputs sent back. This is for Magic Arena, the official
   Discord or Steam client, and Android applications that cannot be adapted
   natively.

```text
                       PERSON
                         |
                  Deck shell and input
                         |
                Guide capability broker
                         |
        +----------------+----------------+
        |                |                |
    Guide View       Media Surface    Remote Surface
        |                |                |
  local package or   local file or    approved program
  bounded provider   Node provider     on trusted Node
        +----------------+----------------+
                         |
           local store and event journal
```

The shell remains responsible for global navigation, volume, network state,
battery state, power, accessibility, and emergency exit. No application surface
may trap those controls or keep shutdown waiting indefinitely.

## What runs where

| Function | RG35XX H Deck | Trusted Node | Future stronger Deck |
| --- | --- | --- | --- |
| Guide shell, input, permissions | Always | Owner controls | Always |
| Wikipedia presentation | Yes | Optional library and conversion | Yes |
| Wikipedia search/content fetch | Yes, bounded | Optional proxy/cache | Yes |
| Full English Wikipedia dump | No | Yes | Only with suitable storage |
| Message summaries | Yes | Collects from approved sources | Yes |
| Discord/Steam full official UI | Streamed view | Runs official client | Possibly |
| Simple Guide-native game | Yes | Optional | Yes |
| Demanding game | Decodes and sends controls | Runs and renders | Hardware-dependent |
| Android application | Remote surface | Emulator, native equivalent, or phone bridge | Optional local provider |
| Semiotic Engine | Optional remote service | Preferred prototype location | Optional |

The Semiotic Engine is not required for any row in this table. Search,
rendering, messaging, synchronization, and streaming must remain deterministic
software functions. An Engine may later summarize or help construct a Recipe,
but it receives only separately granted capabilities and never becomes the
security boundary.

## Common Guide application contract

The next runtime should extend Cartridge Format 1 rather than replace it. A
future application manifest will need seven plain-language sections:

- **What it is** — name, author, version, kind, source, and license;
- **What it can show** — Guide View, media, remote application, or a combination;
- **What it needs** — narrow capabilities, each with a human explanation;
- **Where it can work** — on this Deck, through a Node, or either;
- **What happens offline** — fully available, cached reading only, queued, or
  unavailable with a stated reason;
- **What it may use** — bounded CPU, memory, storage, network, queue, and device
  needs for each operating mode; and
- **How it yields** — which work may be reduced, paused, cancelled,
  checkpointed, unloaded, or resumed without losing the user's work.

The exact machine-readable names are provisional until the capability broker is
implemented. Candidate capability families include:

```text
knowledge.search              Search a named knowledge source
knowledge.read                Retrieve a selected document
knowledge.save                Save a document locally
communications.observe        See selected incoming communication events
communications.reply          Send a reply through one named provider
media.play                    Play an approved local or remote item
application.session.open      Ask for one remote application session
application.session.input     Send only the session's declared controls
network.outbound              Contact the package's declared services
storage.private               Use the application's private local store
```

A declaration is a request, not permission. The Deck's capability broker grants
a revocable token scoped to one package, one provider, one operation, and a
bounded lifetime. “Network access,” “computer access,” and “account access” are
too broad to be valid user-facing grants.

### Contention and bounded-work contract

Contention management is a system responsibility. A cartridge author describes
the application's needs and interruption behavior in plain language; the Guide
runtime translates the accepted installation agreement into host controls and
provider policy. An application cannot raise its own priority, enlarge its
limits, retain an expired device lease, or bypass the Supervisor because it
believes its work is important.

The governing policy is [Resource Contention Contract 0](RESOURCE_CONTENTION_0.md).
Critical tier 0 protects power management and hardware-immediate work; tier 1 is
foreground interaction, tier 2 communications, tier 3 background work, and tier
4 spare-capacity work. Normal contention preserves bounded progress for admitted
lower tiers. A verified critical deadline may suspend those floors according to
the installed agreement. For simultaneous video playback and file download,
preserve playback and temporarily pause the download when both cannot fit.

Every runtime operation must have an owner, an operating mode, a resource tier,
bounded demand, a cancellation path, and a terminal outcome. Stateful work must
also declare what can be checkpointed, what durability means, and whether it is
safe to unload afterward. Exclusive devices use revocable leases; discovery and
permission do not imply possession. CPU, memory, storage, network bandwidth and
devices remain separate resources with separate evidence.

Implementations should prevent avoidable contention before scheduling it:

- partition private mutable state and use read-only sharing where practical;
- serialize ownership-sensitive hardware through a broker or designated worker;
- keep queues bounded, apply backpressure, and coalesce replaceable work;
- let current pointer, button-release, resize, status and search state supersede
  obsolete queued state;
- perform blocking I/O and expensive preparation outside critical sections;
- use a documented lock order and never wait indefinitely while holding a lock;
- use version checks or transactions when optimistic updates are safe;
- cache immutable results within explicit size, expiry and provenance limits;
- place deadlines on provider operations, not on the user's reading or response;
- make cancellation idempotent and report whether work stopped, saved, failed,
  or is still completing.

The Supervisor first reduces optional consumption, then requests cooperative
yielding, checkpointing and unloading as permitted. Forced termination is a
bounded last resort for an authenticated critical deadline or an unresponsive
component, and must report possible data loss. A pause is not evidence that
memory was reclaimed; a stop acknowledgement is not evidence that capacity is
available; fresh host or provider measurements establish the result. Dependency
holders require handoff or priority inheritance rather than blind termination.

Conformance tests must create real contention and verify user-visible behavior:
Power and input remain responsive; audio/video meet measured continuity targets;
obsolete events do not replay; queues and memory remain bounded; lower-tier work
makes its promised progress or visibly enters a defined deferred state; saved
work survives interruption; and resources are measurably released after exit.
The diagnostic record includes instance identity, agreement revision, tier,
queue depth, high-water marks, requested action, deadline, acknowledgement and
observed release without recording private content unnecessarily.

### Guide View

Guide View is the most important missing abstraction. A provider sends a small
semantic document—meaning it says “this is a heading,” “this is a paragraph,”
or “this is a selectable link,” rather than giving exact pixel coordinates.
The Deck chooses line lengths, fonts, contrast, focus order, and pagination.

The first vocabulary should remain deliberately small:

- screen title and status;
- heading and paragraph;
- numbered or bulleted list;
- link and button;
- compact image with alt text and attribution;
- key/value facts;
- table that can fall back to one record at a time;
- text field and choice field;
- progress, warning, and error;
- media reference and remote-session reference.

Every interactive element has a stable identifier, a short label, and a named
action. Remote HTML, JavaScript, executable markup, custom fonts, and arbitrary
CSS are not part of Guide View. This prevents a document from becoming a hidden
program and lets the same content work on an e-paper screen, a 640×480 Deck, a
phone, or a desktop.

The first revision should use bounded UTF-8 JSON because the existing project
already has safe JSON parsers and tests. A friendlier Recipe editor can hide the
JSON completely. Later encodings may reduce bytes without changing the meaning.

### Providers

A **provider** makes a capability available. It may live on the Deck, a Node,
or a removable cartridge. Wikipedia is a knowledge provider. The Windows media
library is a media provider. A Discord notification listener is a communication
provider. Sunshine, the present application-capture code, or an Android emulator
can be remote-application providers.

All providers must report:

- a stable type and protocol version;
- a human name and the device on which they run;
- availability and an understandable reason when unavailable;
- the capabilities and limits they actually support;
- whether they require the internet, a local Node, an account, or owner approval;
- their privacy and retention behavior.

The Deck asks for behavior, not an implementation. Replacing one streaming
transport or Wikipedia parser should not require redesigning the home menu.

### Events and intermittent connection

GuideOS needs one bounded event journal for messages, downloads, Node changes,
Recipe triggers, and application-session state. Each event has a source, type,
creation time, sequence number, privacy label, and optional expiry. Important
events are acknowledged; transient state such as pointer motion, progress, and
presence is coalesced so old updates are discarded rather than replayed.

When a link disappears, the Deck must show the last known information as stale,
offline, or queued. It must never imply that a reply was sent or an article was
updated until the provider acknowledges it. Reconnection resumes from the last
acknowledged sequence instead of downloading an unlimited history.

This journal generalizes the movement rule already proven by the Windows Node:
the present state supersedes obsolete high-frequency state. It also implements
the project's non-aggression principle by bounding queues, retries, bandwidth,
storage, and work requested from another device.

## Wikipedia path: a document reader using a constrained browser renderer

The present reader has already proven search, result selection, article fetch,
paragraphs, sections, links, and offline saves. Its weakness is that it converts
Wikipedia's parsed page into a mostly linear string. The next reader should
preserve useful structure without attempting to reproduce a desktop webpage.

### Proposed article pipeline

1. Search using Wikimedia's supported API and show real result choices.
2. Fetch the selected page using MediaWiki's current REST HTML endpoint, which
   returns page metadata, license information, revision identity, and structured
   HTML.
3. On the Deck or Node, parse that HTML into a safe **Guide Article Document**.
4. Retain headings, paragraphs, lists, emphasis, links, image references,
   captions, simple tables, quotations, notes, and source attribution.
5. Remove scripts, styles, forms, edit controls, tracking, unsupported embeds,
   and external resource loads.
6. Send or store the Guide Article Document, then let Guide View render it.

The parser must remain a converter with an explicit allow-list. NetSurf may be
used as the lightweight HTML/CSS renderer, but it does not receive arbitrary
remote pages or scripts. Links become typed actions. Internal article links
reopen the Wikipedia provider; citations open a reference card; external links
show their destination and require confirmation. Images are opt-in,
size-bounded, cached with attribution, and decoded to a safe display size before
the Deck renders them.

The result should provide:

- a table of contents and section jump;
- readable paragraphs with emphasis and lists;
- selectable links in place, not only in a detached numbered list;
- citation and image-caption cards;
- history, back, search within article, and reading position;
- visible source, revision date, retrieval date, and license;
- explicit save/remove for offline reading.

### Offline Wikipedia

The full English article dump belongs on a Node, not this Deck. The existing
Node dump manager should become a library provider that can resume, verify, and
index Wikimedia's `pages-articles-multistream` snapshot. The Node exposes search
and article retrieval through the same Guide Article Document contract as the
online provider. The Deck therefore cannot tell the difference in rendering;
it only shows that the source is **Online Wikimedia**, **Home Library**, or a
dated saved copy.

For portable use, a Cartridge Workshop action should make a **reading pack**:
selected articles, their required images, metadata, licenses, and an index in a
bounded `.guide` package. Copying the entire dump to every Deck is neither
necessary nor responsible.

Wikimedia's current REST API provides HTML and metadata, while its usage policy
requires descriptive identification, rate-limit compliance, and license
compliance. Those are permanent requirements of the provider, not optional
polish. See [MediaWiki REST API](https://www.mediawiki.org/wiki/API%3AREST_API/en),
[REST API reference](https://www.mediawiki.org/wiki/API%3AREST_API/Reference/en),
and [Wikimedia API Usage Guidelines](https://foundation.wikimedia.org/wiki/Policy%3AWikimedia_Foundation_API_Usage_Guidelines).

## Communications path: observe first, reply deliberately

“Discord support” or “Steam support” must not imply that GuideOS will imitate
their private clients, scrape credentials, or evade platform rules. A
communications provider has three progressively richer modes:

1. **Notification mirror** — the user explicitly permits the Windows Node to
   read notifications from selected applications. The Deck sees source, sender,
   safe preview, and time. This is the first practical Discord and Steam step.
2. **Official integration** — a bot or application uses a service's documented
   API in spaces where it has legitimately been installed and granted access.
3. **Official client surface** — the Node streams the selected Discord or Steam
   window. This is the fallback for complete account functionality. Inputs are
   explicit session controls, not background automation.

Windows provides a user-permissioned notification-listener API specifically for
companion-device and notification-sync scenarios. It requires an appropriately
packaged Windows component and remains revocable in Windows settings. See
[Microsoft's notification listener documentation](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener).

Discord forbids automating an ordinary user account as a self-bot. Its supported
Gateway is for apps and bots, and message content is permission-sensitive. The
project must therefore never request or reuse a person's Discord user token.
See [Discord's self-bot policy](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots)
and [Gateway intents](https://docs.discord.com/developers/events/gateway).

Steam's documented public and partner Web APIs cover selected Steamworks
features, but do not establish a general personal-chat client contract. The
initial Steam path should therefore be notification mirroring plus a streamed
official client, not an undocumented login. See the
[Steamworks Web API overview](https://partner.steamgames.com/doc/webapi_overview?language=english).

### Normalized communication card

The Deck should not need a different entire interface for every service. A
provider converts permitted information into a communication card containing:

- service and account label;
- conversation and sender label;
- timestamp and unread/mention state;
- bounded text preview;
- attachment types without automatic download;
- available actions such as dismiss, open official client, or reply.

Cards are ephemeral by default. Saving history, showing message bodies on a lock
screen, downloading attachments, and sending replies are separate permissions.
A notification preview must never be presented as a complete conversation.

The first release is read-only. Reply support comes only where an official API
or an approved interactive client session can perform it, and the Deck always
shows the service and destination before sending.

## Game and application streaming path

The existing Application Streaming 0 work has the correct control boundary but
its FFmpeg-over-HTTP proof is not the final interactive transport. It currently
demonstrates registration, local approval, window capture, ownership, and
expiry. The next transport must be designed around latency, synchronized audio,
controller input, loss recovery, and immediate revocation.

### Two kinds of game

- **Guide-native game:** a small open game packaged with portable assets and a
  restricted runtime. It runs offline on the Deck and uses semantic controller
  events, audio, a bounded save store, and either a simple 2D canvas or a later
  audited graphics capability.
- **Node game:** the official desktop or Android application runs on the Node.
  The Deck receives a remote surface and sends only the chosen game profile's
  controls.

For the Node path, evaluate a Guide adapter around Sunshine/Moonlight before
building a complete streaming protocol from scratch. Sunshine is a self-hosted
host designed for low-latency streaming and supports hardware encoding on AMD,
Intel, and Nvidia hardware. GuideOS would still own discovery, user approval,
application profiles, capability grants, and emergency exit; the adapter would
use the mature media transport. See [Sunshine's official documentation](https://docs.lizardbyte.dev/projects/sunshine/latest/).

The evaluation must prove that a compatible client can use the RG35XX H's actual
video decoder and input devices. If it cannot, the provider contract permits a
different transport without changing the user interface.

### Streaming safety rules

- The Node owner registers a specific application, not “the whole computer.”
- The Node shows the requesting Deck and waits for local approval unless a
  narrowly remembered trust rule exists.
- Only the chosen window, its audio, and its declared input profile enter the
  session.
- Clipboard, files, microphone, camera, keyboard, shell, and arbitrary mouse
  access are absent unless independently granted.
- Home, Power, and a documented button chord always close the remote surface.
- Button releases and current pointer position supersede queued input.
- Closing either side revokes session keys and stops capture within a bounded
  deadline.
- Streaming failure returns to the shell; it never blocks safe shutdown.

Initial physical targets should be 640×480, 30 frames per second, synchronized
stereo audio, and measured rather than assumed input latency. The first useful
game test should be mechanically simple and tolerant of latency. Arena should
follow only after pointer mapping, audio/video synchronization, and emergency
exit are proven.

## Android path: adaptation profiles, not magical APK conversion

The RG35XX H is not a suitable general local Android machine. Its one gigabyte
of memory and current graphics/kernel path do not satisfy the requirements of
modern heavyweight applications. Android compatibility must therefore have
three tiers:

1. **Guide-native adaptation.** An open application, protocol, or file format is
   represented directly as a Guide application. This produces the best small
   interface but is application-specific.
2. **Node-hosted Android provider.** A Windows or Linux Node runs a
   hardware-accelerated Android virtual device, or bridges a user-owned Android
   phone. The Deck uses a remote application surface.
3. **Future local Android provider.** A more capable Deck may run an isolated
   Android environment when its kernel, CPU architecture, graphics, memory,
   audio, and security isolation pass conformance tests.

Android's official emulator relies on graphics and virtual-machine acceleration
for useful performance; CPU architecture and system-image compatibility matter.
That supports the Node-first decision. See
[Android emulator acceleration](https://developer.android.com/studio/run/emulator-acceleration).

### Making adaptation easy

The layperson-facing unit should be an **Application Profile Cartridge**, not a
modified APK. The Workshop asks ordinary questions:

- What application should the Node open?
- Should it use the native desktop version, an Android emulator, or a phone?
- Which window belongs to it?
- Which Deck buttons should perform which allowed actions?
- Is text entry needed?
- What picture shape and orientation does it expect?
- May it use sound, microphone, clipboard, or files?
- Should a session require approval every time?

The Workshop then writes an inspectable profile containing launch identity,
surface requirements, input mapping, permission requests, and health checks.
It contains no account password, user token, proprietary program, or hidden
script. A more advanced author can inspect and edit the exact manifest.

This can make *connecting* Android applications routine. It cannot guarantee
that every APK will run: CPU-native libraries, Google Play dependencies, DRM,
anti-cheat systems, licensing, unusual input, and background-service assumptions
remain properties of each application. GuideOS must report these constraints
plainly instead of disguising failure as user error.

## Runtime and package architecture

The future runtime should be split into replaceable, testable components:

- **Guide Shell** — global navigation, focus, status, power, and accessibility;
- **Guide View Renderer** — turns safe semantic documents into this Deck's UI;
- **Capability Broker** — explains, grants, expires, logs, and revokes powers;
- **Provider Registry** — discovers local, Node, and cartridge providers and
  reports honest availability;
- **Resource Supervisor** — admits work, applies installed limits and priorities,
  coordinates yielding/checkpointing, and verifies that resources were released;
- **Event Journal** — bounded delivery, acknowledgement, offline queueing, and
  stale-state labeling;
- **Private Store** — per-application settings, cache, saves, and quotas;
- **Media Controller** — exclusive, supervised audio/video ownership;
- **Remote Session Controller** — capture transport, control mapping, health,
  and emergency exit;
- **Cartridge Installer** — verification, compatibility check, staged install,
  rollback, and human-readable change report;
- **Recipe Runtime** — a later, friendly way to join events, conditions, and
  actions without exposing operating-system internals;
- **Deck Simulator** — a desktop window with the RG35XX H screen, controls,
  memory limits, network faults, and permission prompts for author testing.

Applications do not launch arbitrary operating-system commands. A package
selects documented runtime operations. Native code, if later allowed at all,
requires a separate expert package class, explicit provenance, stronger
isolation, architecture declarations, and a warning that it is not universally
portable.

## Compatibility without fragmentation

Every protocol and package declares a major and minor version. A Deck ignores
unknown optional fields, rejects unknown required behavior, and explains which
component is too old. Providers advertise capabilities rather than relying on a
brand or hardware model. The project publishes conformance fixtures: known
Guide Views, event sequences, permission cases, hostile packages, interrupted
installs, and provider failures that every implementation must pass.

Core terms, capability meanings, and Guide View elements belong to the public
protocol. A company or community may add a provider, theme, or device adapter,
but cannot silently redefine a standard capability and remain conformant. This
is the practical safeguard against incompatible branded splinters.

## Security, autonomy, and non-aggression

Owner clarification, 22 September 2026: the original social "cyberspace"
principles do not impose anonymity, absolute isolation or zero communication
risk throughout GuideOS. Apply protections according to the deployment's actual
exposure and data. The following describe security expectations to scope to that
deployment; they are not a blanket gate on all local development or functionality.
Explicit owner decisions remain requirements. Added restrictions need a concrete
engineering justification and a proportionate cost.

- credentials stay with the service's official client or the Node's protected
  credential store; they are never placed in a cartridge;
- Node traffic moves to mutually authenticated encryption before use on an
  untrusted network;
- provider access is limited according to its role and trust context; logical
  separation does not require a separate sandbox for every trusted component;
- all remote content is parsed through size, type, nesting, time, and memory
  limits before display;
- packages are inspectable, hashed, signed in a later format, and installed
  through staging with rollback;
- trust is reciprocal, visible, limited, and revocable on both devices;
- network discovery discloses only enough information to offer a connection;
- retries use backoff, provider rate limits are honored, and broadcast traffic
  has strict ceilings;
- logs explain actions without retaining passwords, tokens, private message
  bodies, or private filenames unnecessarily;
- global exit and safe shutdown remain outside application control;
- public-network security claims require evidence appropriate to the exposure;
  use established security mechanisms and focus additional review and adversarial
  testing on the threats and mechanisms the implementation actually introduces.

## Proposed resource budgets for the RG35XX H

These are engineering targets to validate on hardware, not claims already met:

- one foreground application surface at a time;
- no unbounded background application execution;
- Guide View response: 512 KiB maximum, normally tens of KiB;
- individual text chunk: 64 KiB maximum;
- remote image decoded only after dimensions and memory cost are bounded;
- event journal: bounded by record count and bytes, with explicit expiry;
- network requests: one foreground content request per provider initially;
- streaming target: 640×480 at 30 fps before attempting higher rates;
- shell and core services remain responsive under artificial provider stalls;
- every provider operation has cancellation and a visible timeout;
- Power response and input release obey the existing platform safety standards.

Performance diagnostics should measure frame delivery, decode time, audio/video
offset, input-to-picture latency, dropped events, memory high-water mark, queue
depth, reconnect time, and shutdown cleanup. A successful picture alone is not a
successful interactive session.

## Ordered roadmap

### Gate 0 — stabilize the current physical baseline

1. Retain the now-verified persistent Power menu and safe power-off behavior;
   retest subtitle selection after the acknowledged-pause repair.
2. Verify safe exit from playback, Bluetooth audio, Node loss, malformed
   subtitle data, and repeated suspend/seek operations.
3. Capture a known-good seed image and diagnostics after success.

Exit condition: the latest build boots, plays local and Node media, selects and
closes subtitles, returns to navigation, and powers down without a hard cycle.

### Gate 1 — define and prove Guide View 1

1. Write the bounded Guide View schema and capability vocabulary.
2. Build a platform-independent parser, validator, focus model, and paginator.
3. Render the same fixtures in a desktop Deck Simulator and the framebuffer
   shell.
4. Add hostile-input, oversize, unknown-element, cancellation, and recovery
   tests.
5. Package one offline demonstration application using only Guide View.

Exit condition: one `.guide` application renders and behaves identically in the
simulator and on the Deck without arbitrary code execution.

### Gate 2 — Wikipedia Reader 1

1. Replace linear text output with the Guide Article Document converter.
2. Implement sections, in-place links, reference cards, tables, image opt-in,
   reading position, and search within article.
3. Keep the current limited online provider as a fallback during migration.
4. Give the Node dump library a searchable index and Article Document output.
5. Add reading-pack creation to the Cartridge Workshop.

Exit condition: the same article can be read from live Wikipedia, a home Node,
and an offline cartridge with recognizably equivalent structure and attribution.

### Gate 3 — Provider and event foundation

1. Replace development HTTP with mutually authenticated encrypted sessions.
2. Add provider registration, version negotiation, health, quotas, and explicit
   unavailable reasons.
3. Add the bounded event journal and reconnection/resume behavior.
4. Move media and application sessions behind the same provider registry.
5. Add owner-visible audit and revocation screens to Node and Deck.

Exit condition: a provider may disconnect, restart, or be revoked without stale
success claims, unbounded work, or loss of shell control.

### Gate 4 — Read-only communications companion

1. Build a user-permissioned Windows notification-listener helper.
2. Let the Node owner select allowed source applications and preview exactly
   which fields will be shared.
3. Normalize notifications into expiring communication cards.
4. Add a Deck inbox with service filters, unread state, privacy mode, and an
   **Open official client** action.
5. Test Discord and Steam notifications without account tokens or scraping.

Exit condition: selected notifications appear once, in order, with correct
source and staleness state, and disappear from the Deck immediately when access
is revoked.

### Gate 5 — Remote Application Surface 1

1. Finish the physical test of the current approved application session.
2. Evaluate Sunshine/Moonlight on the exact Deck kernel and hardware decoder.
3. Add synchronized audio, a bounded input profile, on-screen connection health,
   and a global emergency exit.
4. Measure LAN latency and loss under realistic Wi-Fi interference.
5. Test a simple desktop game, then the Discord client, before attempting Arena.

Exit condition: a registered application can be approved, controlled, and
closed reliably without exposing the desktop or disrupting power/navigation.

### Gate 6 — Android Provider 1

1. Detect Android emulator, virtualization, image architecture, and graphics
   acceleration without starting anything.
2. Add Node-owner-confirmed AVD start, application list, launch, stop, and
   session close.
3. Route the emulator window through Remote Application Surface 1.
4. Build the Application Profile Workshop and one legally user-supplied test
   profile.
5. Compare emulator, native Windows application, and owned-phone bridge routes.

Exit condition: the Deck opens one approved Android application without
receiving Android credentials, ADB, shell access, or unrelated phone/Node data.

### Gate 7 — Guide Recipes and creator experience

1. Define ordinary-language event, condition, information, device, and action
   blocks on top of the proven capability and event contracts.
2. Build a guided Workshop with live simulation and plain-language errors.
3. Export an inspectable, deterministic `.guide` package.
4. Add permission explanation, resource estimate, compatibility report, and
   one-action share to cartridge or trusted Node.
5. Publish exact technical documentation immediately beneath the friendly guide.

Exit condition: a regular computer user can build and exchange a small program
without learning Linux administration, while an expert can audit every exact
operation it performs.

## Work to avoid for now

- Installing a full Chromium-class browser on the RG35XX H;
- treating parsed article text as the permanent Wikipedia representation;
- using a Discord user token, self-bot, or undocumented Steam chat protocol;
- promising arbitrary APK conversion;
- building a custom low-latency network codec before evaluating a mature open
  transport behind the Guide provider boundary;
- allowing a streamed application to become unrestricted remote desktop;
- freezing Cartridge Format 2 before Guide View and capability-broker tests
  reveal what the manifest actually needs;
- placing the Semiotic Engine in the path of input, permissions, networking,
  shutdown, or deterministic application behavior.

## Immediate next design artifacts

No physical Deck intervention is needed to prepare these:

1. `GUIDE_VIEW_1_DRAFT.md` — semantic elements, actions, limits, and examples
   (initial draft now present);
2. `CAPABILITY_BROKER_0.md` — grant lifecycle and human permission language;
3. `PROVIDER_PROTOCOL_1_DRAFT.md` — discovery, health, versioning, and events;
4. `WIKIPEDIA_ARTICLE_DOCUMENT_1.md` — safe Wikimedia-to-Guide conversion;
5. `COMMUNICATIONS_COMPANION_0.md` — notification source and retention rules;
6. `REMOTE_SURFACE_1.md` — transport selection and measurable acceptance tests;
7. `APPLICATION_PROFILE_0.md` — friendly Android/desktop adaptation package;
8. a desktop Deck Simulator scaffold and conformance-fixture directory.

The recommended implementation order is Guide View, Wikipedia, provider/event
foundation, notifications, remote streaming, Android provider, then Recipes.
That order delivers visible value early while ensuring that each later feature
uses a security and interface layer already proven by a simpler one.
