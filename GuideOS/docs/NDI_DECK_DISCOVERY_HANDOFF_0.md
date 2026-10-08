# NDI and Deck Nodes screen handoff

Status: implementation handoff for the newest Seed candidate; design accepted for integration planning.

## Deck entry point

Add a small globe icon to the main control wheel. Selecting it opens a `Nodes` screen.

## Nodes screen responsibilities

The screen should let the owner:

- Scan the local network for available Desktop Nodes.
- View discovered Node identity, name, address summary, and available services.
- Select a Node and communicate with it through the existing Node Link protocol.
- Pair with a Node using the existing owner-visible confirmation flow.
- Optionally establish long-term trusted credentials for a known Node.
- Revoke trust and end the current session.
- Show unavailable, rejected, expired, or disconnected states clearly.

## Relationship to diagnostics

The Nodes screen should also support the reverse diagnostic path:

1. The Desktop Node discovers or observes the Deck's diagnostic availability.
2. The Desktop Node offers a diagnostic session.
3. The Deck displays a confirmation request.
4. The owner accepts or rejects the request on the Deck.
5. The Desktop Node uses the existing Guide-Link named diagnostic operations.

The Nodes screen must not replace or merge the existing Guide-Link deployment identity. Keep these authorities distinct:

- Node Link pairing authorizes selected Desktop Node services.
- Guide-Link identity authorizes the paired development PC to use fixed Deck deployment and diagnostic operations.
- Long-term Node trust is optional and revocable; it does not automatically grant deployment authority.

## Initial scope

The first Seed integration should include:

- Globe wheel icon.
- Nodes screen.
- Local discovery.
- One selected Node at a time.
- Pair, reconnect, unpair, and revoke-trust actions.
- Bounded status and capability display.
- Clear placeholder state for Desktop-initiated diagnostic offers.

Do not add general shell access, arbitrary remote commands, or unrestricted filesystem browsing.



## Build 0.4.1 integration status

The initial Seed candidate includes the Nodes wheel entry, local discovery UI, one selected Node at a time, session pairing, capability/status display, and optional trust/revocation through the existing Node Link bridge. Desktop diagnostic discovery continues to use Guide-Link on TCP 2222. The owner-confirmation offer handshake is still a placeholder and must be added before diagnostics can be accepted or rejected on the Deck itself.
