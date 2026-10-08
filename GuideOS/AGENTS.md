# GuideOS working instructions

## Standing owner direction

On 7 October the owner requested preparation for the public
`trynottopanic/HGttG_vol1` repository and explicitly excluded Planegotchi files.
Keep its source, tests, assets, tools, data and dedicated documents local.
Preserve the working checkout and its release/private state. The public shell
must handle the absent application and artwork. Follow `../PUBLICATION.md`;
publication preparation does not itself authorize pushing to GitHub.

On 6 October the owner selected `0.4.4.xx` for the combined pending-change
release series, with `xx` the two-digit revision and first revision `0.4.4.01`.
Reconcile verified handoffs and this chat's video-options/NDI changes before
finalizing that build. The owner subsequently authorized the Wi-Fi repair,
combined build and Seed write. The final 0.4.4.01 input is preparation-05,
signed sequence 73 based on a fresh returned-Seed capture of sequence 72.
Record physical write/readback and Deck acceptance separately. Preserve
historical `0.4.3.xx` identities;
do not rewrite the immutable .08 image or its deployment receipts.

The subsequent loading repair is `0.4.4.02`, sequence 74, based on the latest
returned .01 root captured for the Planegotchi diagnosis. It retains the installed
simulation and saved-world formats. Loading fixes have six focused frozen-source
regressions and service validation; consult `build/release-0.4.4.02/installation.json`
for completed Seed write/readback evidence. Deck responsiveness remains a retest.

The owner then approved Wi-Fi survey, Bluetooth explorer and signal watch,
and requested Nmap and other network investigation tools. That combined follow-on
is `0.4.4.03`, signed sequence 75 based on verified .02 sequence 74, retaining
.02 as the only rollback. Read `docs/NEARBY_AND_NETWORK_TOOLS_0.md` for ownership,
bounds and evidence. Sixteen focused checks and native ARM tool/cancellation
fixtures pass. Consult `build/release-0.4.4.03/installation.json` for completed
Seed write/readback; the image or source alone does not establish card deployment
or physical radio/UI acceptance. Preserve the installed world format and exclude
unrelated ongoing simulation/accounting/history changes from this frozen release.

Later on 6 October the owner explicitly requested lighter verification for this
hobby project and stopped the remaining full-data preservation scan after the
0.4.4.01 root write/readback. Use proportionate focused checks. Retain basic
device identity, correct partition bounds and owner-data preservation in the
implementation; do not repeat exhaustive whole-card hashes or broad test sweeps
as a default. Physical Deck testing can establish actual behavior. Record checks
that were skipped without turning them into another approval requirement.

Release naming: on 2 October the owner selected `0.4.3.xx` for the Planegotchi
integration and pending repairs. Its first revision is `0.4.3.01`; subsequent
revisions use sequential two-digit suffixes. Preserve historical `0.4.2.xx`
and `home-v3-rN` identities and the signed sequence history.
Keep the release manifest, visible System Info, and `VERSION` aligned.

On 3 October 2026 the owner paused web browsing and requested removal of its
active integration and exclusive dependencies, retaining source for a later
engine. The owner also directed use of the full functional Seed capacity and
rolling update cleanup: retain the active release and exactly one previous
rollback release. After a successful update, replace the previous rollback and
delete older releases and completed receive/staging files. Do not prune the
active or rollback release to bypass an update's free-space checks. Preserve
owner files, settings, keys and signed history during storage maintenance.

On 22 September 2026 the owner directed: "From this prompt, now, and forward, we
are focused on creating GuideOS as it is outlined in our many, many documents."

Develop the documented GuideOS system. Carry earlier requirements into each
task; a request for a feature or diagnostic does not silently replace them.
Current explicit user instructions take precedence over these notes and older
documents. This file is a working index and implementation discipline, not a new
architecture or a replacement for the source documents.

The owner also requested active design oversight: anticipate downstream
consequences, identify conflicts and missing decisions, and provide caution
before an expedient change undermines the intended system. Apply the oversight
section below throughout implementation, not only when asked to review a failure.

### Scope of philosophical guidance

Owner clarification, 22 September 2026: some early guidance about individual
choice, separation and total safety described a social digital "cyberspace".
It does not transfer wholesale into GuideOS engineering. Intercommunication can
carry acceptable risk. Anonymity, absolute isolation and unrestricted use are
not universal architectural requirements or prerequisites for implementation.

Distinguish explicit functional requirements, philosophical guidance and agent
implementation choices. Choose security measures proportionate to actual access,
data and deployment exposure, balancing usefulness, performance and complexity.
Justify a restriction by a concrete need rather than treating philosophy as an
automatic prohibition. Trusted local components may share an implementation or
communicate directly where appropriate. This clarification does not erase the
owner's explicit device-control, update, resource or data-preservation decisions.
Routine engineering tradeoffs do not require a new approval ceremony.

The owner approved the AT Field communication setting: Closed, Familiar and Open.
Follow `AT_FIELD_0.md`. It controls approachability and communication defaults;
resource permissions remain distinct. Preserve existing connections by default,
and explain any proposed interruption before applying it.

## Read the relevant design before changing its implementation

| Source | Role |
| --- | --- |
| `../HHG_Foundation/02_GUIDE_AND_PROTOTYPE_DEFINITION.txt` | Person-owned Deck, devices and Nodes; capability enforcement; portable data; prototype purpose and continuity acceptance tests. |
| `../HHG_Foundation/03_DESIGN_PHILOSOPHY.txt` | Human agency, accessibility, local usefulness, understandable behavior, adaptable methods and honest evidence. |
| `FUTURE_FRAMEWORK_0.md` | Common application contract; Guide View, Media and Remote Application surfaces; shell/global controls; replaceable runtime components; bounded events and work. |
| `MODERN_FOUNDATION_0.md` | Owner-selected minimal Debian direction; separate board profiles; portable application/service/job, resource, lifecycle and recovery contracts. |
| `LIVE_CAPABILITY_REGISTRY_0.md` | Separate discovery, authorization and resource assignment; provider evidence; feature requirements; acquire/watch/release and revocation. |
| `GUIDE_VIEW_1_DRAFT.md` | Semantic presentation, predictable focus/actions, accessibility, failure behavior and conformance fixtures. |
| `CARTRIDGE_FORMAT_1.md` | Packaging/integrity; declarations request authority without granting it. |
| `IPC_ENVELOPE_0.md` | Bounded authenticated local message transport, framing, profile, identity binding, outcomes and evidence boundary. |
| `SUPERVISOR_CAPABILITY_FOUNDATION_0_PROPOSAL.md` | Approved lifecycle, Supervisor, capability-broker, proof, verification and installation-gate architecture; historical filename retains PROPOSAL. |
| `docs/DESIGN_ALIGNMENT_0.md` | Reconciled source map, current evidence, unresolved shared contracts and active architectural risks. |
| Feature-specific documents | Read those relevant to the affected application, provider, transport, controls or theme in addition to the shared contracts. |

Honor document status: proposed names, example values and exploratory schemas
are not frozen APIs or measured device capabilities. Preserve their design
requirements while making implementation decisions explicit. Distinguish desired
behavior, current implementation, tested evidence and known limitations.

Older `BASELINE.md`, build instructions and repository summaries describe the
Buildroot-era prototype. The owner subsequently selected minimal Debian. Older
claims of working features are historical evidence, not proof that those features
exist in the Debian implementation. Reconcile a material conflict using the
owner's decisions and the applicable documents; do not silently choose whichever
description fits existing code.

Respect publication boundaries when consulting other project material. Do not
copy or reference private planning documents in the public tree without owner
authorization to change that boundary.

## Active design oversight

- Carry the whole design into each substantial change. Check effects on other
  applications, shared services, permissions, state, global controls, portability
  and recovery before treating a locally working solution as sufficient.
- Give a short pre-change account of the intended outcome, the existing contract
  it serves, the main uncertainty or likely failure, and the evidence needed.
  Scale this to the change; routine corrections do not require a ceremony.
- State material assumptions as assumptions. Look for contradictory documents
  and actual integration constraints before turning an assumption into behavior.
  Distinguish an owner requirement from an implementation choice or proposal.
- Challenge a proposed approach when evidence shows a conflict or substantial
  downstream cost. Explain the concrete consequence and recommend a smaller or
  better-aligned next step. Do not merely agree, silently implement the conflict,
  or blame the owner for failing to repeat existing requirements.
- Treat prototypes as bounded experiments with an explicit question and evidence
  limit. Do not promote their shortcuts into shared policy by accumulation.
  Reassess the owning component before adding another workaround.
- Keep material unresolved architectural risks in the alignment record, with
  the affected contract and evidence needed to close them. Update existing
  entries; do not create a new checklist for every task or mark risk resolved
  because code was written.
- Review the finished change against the original user-visible criteria,
  including failure and interruption. Test an actual integration boundary when
  the claim depends on it. Separate simulated, source, image and physical evidence.
- Resolve ordinary reversible details autonomously. Raise consequential product
  choices or unresolved conflicts early and continue independent useful work.
  This oversight request does not impose approval for every step. If a choice
  needs the owner's decision, present the concrete alternatives and consequences.

## Carry these requirements through the work

- For the Debian implementation, systemd is PID 1. The owner accepted this
  arrangement after reviewing its conflict with the earlier Guide-as-PID-1
  implementation. Guide Supervisor runs above systemd and coordinates whole
  applications, lifecycle, capability authorization and resource policy through
  the relevant Guide components. Use systemd for underlying process/service
  operations. Do not reinstate the old custom init arrangement implicitly.
  Keep this host integration behind the portable Guide contract; see
  `MODERN_FOUNDATION_0.md` for the accepted boundary and remaining design work.
- GuideOS mediates between complete applications and variable hardware. Model
  application-owned helpers, services, jobs and resources explicitly. Keep
  system-owned responsibilities distinct from an individual application.
- Apply the accepted personal-computer hobbyist experience: understandable
  owner-controlled Decks, inspectable/exchangeable cartridges and recognizable
  peer/Node services. Preserve useful local operation and communication across
  unlike hardware. Discovery does not grant access or automatically pool
  resources. Carry forward the installation-time footprint agreement; executions
  use it without requesting the footprint again. The design philosophy and
  modern foundation record this direction separately from open allocation policy.
- Preserve a low hardware floor. RG35XX H is the present test target, and Pi Zero
  2 W is a future portability target, including headless use. Neither fixes the
  universal hardware requirements. Optional functionality requires an actually
  implemented compatible provider and application path.
- Keep discovery, permission and resource ownership distinct. A connected device
  does not imply access, an exclusive lease, or successful operation. Registry,
  broker and supervisor responsibilities may share a lightweight implementation
  without losing those distinctions.
- Preserve owner policy and control. Applications and agents cannot authorize
  themselves. Updates and system actions must follow the owner's choices.
- Apply the accepted resource priority order: critical tier 0 is highest,
  including power management and hardware-immediate work; increasing numbers
  mean lower priority. The owner accepted 1 foreground interaction,
  2 communications, 3 background work and 4 spare-capacity work, with lower-tier
  progress preserved during normal contention. For the first stream/download
  scenario, preserve playback and temporarily pause download if both cannot fit.
  Follow `RESOURCE_CONTENTION_0.md` for the accepted escalation policy and
  remaining integration work. Applications cannot self-assign critical authority;
  priority does not replace the installation-time footprint.
- Keep global navigation, input focus, display ownership, cancellation and power
  coordination in the system's control. Applications request services through
  defined contracts. Board bring-up probes may access devices directly within
  their stated scope; that exception is not the production application design.
- Treat pause/resume, checkpoint, release, exit and shutdown as real lifecycle
  behavior. Preserve work where possible, acknowledge durable saves, and expose
  failure. Stopping UI progress alone does not establish application suspension.
- Use the documented semantic control model. Do not silently overload ordinary
  input with a new global gesture or let a diagnostic's navigation invalidate
  the observations it is supposed to collect.
- Reading and responding do not acquire arbitrary session deadlines. Bounded
  provider operations, resource limits and recovery deadlines remain separate
  concerns, with visible status and cancellation as specified.
- Preserve the existing exclusion of Start, Power and Reset from the physical
  diagnostic exercises until the owner changes it. That test exclusion does not
  remove the finished OS's global-control requirements.
- Keep core operation deterministic and useful offline. A Semiotic Engine is an
  optional, permission-scoped provider, not the input, security or lifecycle
  authority. Ordinary use and creation remain understandable without specialist
  knowledge.

## Before implementing a change

Identify the source requirement, the responsible component, its ownership and
lifecycle effects, and the observable acceptance condition. Record that mapping
with the work. Resolve routine details within existing authorization; raise
materially unresolved behavior or conflicting requirements explicitly rather
than embedding an undocumented policy in code. Do not introduce a blanket
approval step for ordinary implementation work.

The architecture already defines component responsibilities, and service-specific
contracts define parts of lifecycle behavior. The shared application/service/job
contract still needs complete transitions, acknowledgments and enforcement to be
specified and integrated. Detailed grant interfaces and registry schemas are
also provisional. Derive those details from the existing design; label new
proposals as proposals rather than attributing invented rules to the owner.

Validation must test the user-visible contract and actual integration boundary.
Report source checks, simulated tests, image verification and physical behavior
separately. Tests that replace display or system services cannot validate real
terminal ownership or shutdown. Never rewrite expected behavior just to match a
workaround that passes its own tests.

`docs/LIQUID_SNAKE_FAILURE_AUDIT.md` records why GuideOS 0.3's diagnostic handler
is not a reliable architectural baseline: shared console ownership, test input
diverted into navigation, cleanup blocking shutdown and inconsistent final
reporting. Preserve its evidence and the recovery images. Diagnostics should
verify the developing GuideOS contracts; they are not the destination product.
