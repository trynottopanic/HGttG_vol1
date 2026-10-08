# Semiotic Engine Interface Cartridge 0

Status: verified prototype cartridge and native article-summary views built;
physical Deck acceptance test pending

## Purpose

The Semiotic Engine Interface Cartridge gives a Deck the optional software
needed to consult compatible Semiotic Engines. It installs an interface and a
provider connector, not the Engine's model runtime and not a source of system
authority.

A Deck remains functional without this cartridge or without a reachable
Engine. Removing the cartridge after installation does not remove the installed
connector unless the user chooses to uninstall it.

## Implemented contents

- a versioned Deck-side client for a paired Node's `semiotic.text` capability;
- bounded status, submit, poll, cancellation, timeout, and failure handling;
- a fixed, non-shell command vocabulary;
- exact input and result paths in volatile `/run` storage;
- a transactional RG35XX H installer with package and per-file hashes;
- plain-language purpose, provenance, runtime map, and licensing records.

The first native Guide View begins at a Wikipedia article. X opens a review of
the exact bounded context, A sends it, B cancels without blocking the Deck, and
the result is rendered in paged Deck text. The command-line adapter remains
separate from the existing Node-link program so installing the cartridge is a
real modular addition.

The cartridge must not contain identity secrets, pairing credentials, personal
memory, a mandatory model, or arbitrary installation commands.

## Authority boundary

The connector may submit only context selected and authorized for a particular
request. A Semiotic Engine may interpret that bounded input and return an
answer, transformation, structured extraction, proposed Recipe, request for
more context, or inability report.

The Engine cannot use the connector to browse Deck files, contact the network,
operate devices, install packages, send messages, or execute its own proposed
actions. Those decisions remain with the Deck's Agent Broker and Capability
Broker.

## First acceptance test

1. The user inserts the cartridge and opens it in the Cartridge Browser.
2. GuideOS explains that the package adds an optional Semiotic Engine
   interface and shows its requested capabilities.
3. The user installs it through the normal verified cartridge path.
4. The connector finds a separately running desktop Engine through an
   authorized Node.
5. The user selects one paragraph and requests a summary.
6. The Deck shows exactly what will be supplied before sending it.
7. The Engine returns a bounded structured response.
8. The Deck validates the response and presents it as a Guide View.
9. Cancellation, disconnection, incompatibility, and timeout produce clear
   non-destructive errors.

Success does not require the Engine to access files, tools, personal memory, or
the public internet.

## Interaction safety gate

The first Guide View must launch requests asynchronously. While the Engine is
working, the Deck event loop must continue handling cancellation, Back, the
power menu, battery and network state, and Developer Link diagnostics. A
five-minute request ceiling is not permission to block the interface for five
minutes.

On cancellation or power-off, the Deck asks the Node to cancel the job, waits
only for a short bounded grace period, deletes volatile input/result files, and
continues shutdown even if the Node has disappeared. Late responses from an
abandoned job are ignored by job identity.

## Packaging direction

The prototype uses Guide Cartridge Format 1 with the fixed install action
`application.semiotic-engine.rg35xxh`. The built archive is
`guide.semiotic-engine.interface-0.1.0.guide`; it contains five declared files,
no model, no credentials, and no arbitrary installation command. This remains
a development cartridge: signature and publisher-trust work still belongs to
the future cartridge format/security proofing path.
