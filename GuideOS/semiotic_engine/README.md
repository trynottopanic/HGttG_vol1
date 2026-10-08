# Guide Semiotic Engine 0

This directory contains the independent reference service for Semiotic Engine
Protocol 0. It uses only Python's standard library and a deterministic text
backend, so protocol tests do not require or download an AI model.

Run `python -m unittest` in this directory to exercise validation, job
isolation, cancellation, and the HTTP boundary. Run
`python guide_se_service.py` to start the loopback service. On first start it
creates a random local connection credential and prints the path of its
connection record, not the credential itself.

The deterministic backend will later be joined by replaceable model adapters.
No adapter may silently add filesystem, network, device, or application access.

## Owner control panel

On Windows, `guide_se_native_gui.py` provides the non-technical control panel.
It starts and stops the model in the background, reports current work and
memory, and repeats the Engine's enforced authority and retention boundaries.
It uses the same display-rate movement governor as the known-good Desktop Node
window.

Run `BUILD_WINDOWS.cmd` to test and produce
`dist/GuideSemioticEngine.exe`. The large `models/` and `runtime/` directories
remain external, replaceable dependencies and are not embedded in the program.

## Real-model adapter

The optional `llama-cpp` backend manages a separate local `llama-server`
process bound to loopback with a temporary private API key. The Engine passes
only the already validated request text to it. Streaming output permits bounded
collection and cooperative cancellation; model output still passes through the
same response contract.

The runtime and GGUF model are deliberately not committed to this repository.
They are selected local dependencies and can be replaced without changing the
Node, Deck, cartridge, or Semiotic Engine protocol.

The current development machine uses the pinned files recorded in
`DEPENDENCIES.lock.json`. When those files are present at the conventional
paths, `START_REAL_ENGINE.cmd` provides a double-clickable developer launcher.
It is not yet the final owner control panel.

### Brief option dictionary

- `--backend` chooses the replaceable computation implementation.
- `--llama-server` identifies the local inference program.
- `--model` identifies the selected local GGUF model data.
- `--gpu-layers` controls how much model work is placed on the graphics card.
- `--connection-file` changes where the private local connector record lives.

## Future research candidate: picoGURU

[picoGURU](https://codeberg.org/BobbyLLM/picoGURU/) is an AGPL-3 local,
evidence-first lookup project. It is recorded here as a possible future
component of, or architectural reference for, the Semiotic Engine: in
particular, a bounded provider for retrieving attributable passages from
owner-selected cheatsheets, local documents, and offline ZIM archives.

It is **not adopted as a GuideOS dependency or protocol component**. Any
evaluation or integration must preserve the Semiotic Engine Protocol boundary:
the provider receives only caller-supplied, bounded input; it receives no
ambient filesystem, network, device, identity, or authority access; its output
remains untrusted data; and every surfaced passage retains inspectable source
provenance. A future evaluation must also resolve its AGPL obligations,
packaging and maintenance state, source-path confinement, LAN authentication,
and compatibility with the GuideOS IPC Envelope before any distribution or
runtime use.
