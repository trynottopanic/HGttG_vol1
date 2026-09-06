# Lightweight Desktop Node 0

The first Desktop Node is one Windows program with a small owner-facing window.
It announces itself only on the local network, shows a temporary pairing code,
and reports a list of named capabilities to a paired Deck. Stopping the program
immediately revokes every Deck session.

## Encounter

1. The computer owner starts `GuideNode.exe`.
2. Windows may ask whether to allow private-network communication. The owner
   permits private networks only.
3. The window says **Ready for a Deck** and displays a six-digit code.
4. The Deck finds the Node by name and asks the user for that code.
5. Once paired, the Deck displays only services the Node actually has.
6. The owner can create a new code or stop the Node at any time.

## Protocol shape

The discovery request is `GUIDE-DISCOVER/1` over local UDP. The response
contains a temporary Node identifier, human-readable name, local address,
pairing requirement, and transport-security state. It does not disclose files,
accounts, applications, or personal details.

The versioned service path is `/guide/v1`. The current implementation supports:

- public Node description;
- short-code pairing;
- authenticated status and capability lists;
- an explicit unpair operation;
- an honest "Android provider unavailable" state.

## Prototype limitation

Version 0 uses unencrypted HTTP for a controlled same-network demonstration.
The pairing code prevents casual control but does not defeat a hostile person
who can observe or alter local traffic. Before public-network use, replace this
with authenticated encryption, a persistent owner-verifiable Node identity,
Deck-side identity pinning, and an explicit re-pair/reset procedure.

The implementation is in `node/desktop`. It uses only Python's built-in user
interface and networking libraries at runtime and can be packaged into one
Windows executable.
