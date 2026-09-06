# Guide Node Link

This is the first Deck-side half of the lightweight Desktop Node link. It can:

- look for Guide Nodes on the current local network;
- reject malformed, public-Internet, or unsupported announcements;
- pair with the six-digit code shown by the computer owner;
- read the Node's status, available capabilities, and Android-provider state;
- explicitly end the session.

The library does not persist its session token across a Deck restart. It
uses the development-only unencrypted local protocol, so it must not be treated
as production security. Its purpose is to let us verify discovery and pairing
before adding the controller-driven Deck screen and encrypted identity layer.

`guide_node_bridge.py` supplies the narrow line-oriented boundary needed by the
current framebuffer shell. Candidate Nodes and a successful session are stored
only under `/run`, which disappears at shutdown. The bridge never prints a
Node address or session token into the shell protocol.

There is intentionally no general command, file-browser, or Android-debug
method in this client.
