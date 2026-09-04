# The Third Way

The Third Way is an open, local-first personal-computing project. Its goal is
to let people connect information, devices, and services through tools that
serve and protect the person using them while respecting everyone else's
autonomy.

HHGttG remains the protocol and architecture name, and GuideOS remains the
provisional operating-environment name. These technical identifiers are kept
stable while the larger idea is known as the Third Way.

The Third Way does not accept a forced choice between opposing technological
models. It examines both, keeps what serves people from each, rejects what
subordinates or harms them, and builds toward the direction those judgments
indicate.

GuideOS is the Linux-based operating environment being developed for a
person's **Deck**. A Deck is a portable, user-controlled computer that can use
nearby **Nodes** for shared information or processing and can optionally work
with a **Semiotic Engine**, the project's term for language-model assistance.

The project is at an early experimental stage. Nothing in this repository is
currently a bootable release or safe to flash to a device.

## Design goals

- Local usefulness without a mandatory cloud account.
- Open protocols rather than control by one platform or provider.
- Understandable permissions enforced by the system, not entrusted to an AI.
- Interoperability across different Decks, Nodes, interfaces, and hardware.
- Simple creation through readable **Guide Recipes**.
- Portable, inspectable **Guide Packages** built from existing open formats.
- Plain-language interfaces and documentation with exact technical detail
  available to anyone who wants it.
- Reciprocal autonomy: protect the owner without harming or disrupting others.
- Formless methods with a firm purpose: use whatever interoperable tools serve
  the person, without turning a particular technology or school into doctrine.

## First hardware target

The first Deck target is the Anbernic RG35XX H. The initial hardware milestone
is a minimal image that boots, operates the built-in display and controls,
recognizes storage, reports basic system state, and shuts down safely.

The first end-to-end acceptance test is `CONTINUE-ON-DECK-0`: pause an
authorized local video on the desktop Node, connect the Deck by USB, transfer
the video together with its playback position, disconnect, and resume locally
on the Deck at substantially the same moment. This tests a core Third Way idea:
the person's activity can move between devices without an account or cloud
service.

The following network test is `VISITING-SCREEN-1`: with the network owner's
consent, select one movie on the
Deck, let the owner's temporary host discover and control a compatible
television, stream the movie directly from the Deck without an internet upload,
and revoke access afterward. The Windows prototype is in
[`prototypes/visiting_screen_1/`](prototypes/visiting_screen_1/).

A secondary event-routing test is `MESSAGE-CHIME-0`: after the user's phone
receives a text from an explicitly chosen person, it sends a one-time local
event over Wi-Fi and the Deck plays a chosen sound. The event need not disclose
the text itself, and the cell providers do not need to match.

This test keeps rendering and file service on the Deck while placing consent
and destination control with the owner of the visited network. A later native
GuideOS version can replace the temporary Windows Deck program without changing
that boundary.

## Source layout

- `GuideOS/` contains the emerging Buildroot external tree, board material,
  distribution notes, and provisional interface concepts.
- `HHG_Foundation/02_GUIDE_AND_PROTOTYPE_DEFINITION.txt` defines the Third Way,
  its technical architecture, and the current prototype.
- `HHG_Foundation/03_DESIGN_PHILOSOPHY.txt` records the project's public design
  principles.

GuideOS currently uses Buildroot 2025.02.17 as its approved system-building
baseline and intends to begin hardware work on the Linux 6.18.y long-term
kernel line. Exact release inputs will be pinned and hashed before an image is
distributed.

The current workshop setup and its command dictionary are documented in
[`GuideOS/BUILDING.md`](GuideOS/BUILDING.md). Exact approved input revisions are
recorded in [`GuideOS/SOURCES.lock`](GuideOS/SOURCES.lock).

## Accessibility of development

Buildroot and hardware enablement are necessarily technical, but they should
be explained rather than treated as an entrance examination. Instructions will
state what a command accomplishes, define unfamiliar terms, and preserve the
exact detail needed to reproduce the result.

Ordinary Guide programs should not require operating-system development.
Recipes will provide the approachable creation layer, with deterministic tools
for validation, testing, permissions, packaging, and exchange.

## Licensing

Original software and build configuration are licensed under the GNU Affero
General Public License, version 3 or later. Original documentation and visual
design material are licensed under Creative Commons Attribution-ShareAlike 4.0
International. See [LICENSE.md](LICENSE.md) for the precise repository policy
and canonical license texts.

Third-party components retain their own licenses and must be identified before
inclusion. Project names and compatibility descriptions do not grant trademark
rights or imply affiliation with Douglas Adams, his estate, or rights holders
associated with *The Hitchhiker's Guide to the Galaxy*.
