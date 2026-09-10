# Application Streaming 0

Application Streaming 0 is the first reusable framework for viewing a program
running on a desktop Node from a Deck. Magic: The Gathering Arena is the first
target example; Discord and other applications use the same session protocol
rather than receiving special access to the Deck.

## Person-visible flow

1. The Node owner chooses a specific Windows `.exe` and identifies its window.
2. A paired Deck can see the application's name, but never its private path.
3. The Deck requests a temporary session.
4. The Node shows which Deck requested which application. Nothing launches
   until the person at the Node approves it.
5. After approval, the Node launches that exact executable without a shell and
   offers a short-lived 640×480 H.264/MPEG-TS view of that window.
6. Either device can close the session. Sessions also expire automatically.

## Present implementation boundary

The control plane, registration, local approval, application launch, session
ownership, expiry, close operation, and Windows FFmpeg capture command are
implemented. The Deck-side protocol can list, request, inspect, display, and
close these sessions. A person-facing Deck menu, a physical low-latency video
test, and a bounded input adapter are the next milestone.

Input is deliberately disabled in this build. A streamed session does not
grant keyboard, mouse, command, filesystem, clipboard, microphone, or general
desktop access. Later input adapters will translate a small, documented Deck
control vocabulary for each application class and will require their own
adversarial tests before activation.

## Why Arena runs on the Node

The RG35XX H cannot practically run the current Android or Windows Arena client
locally: its memory, graphics stack, architecture, and anti-tamper assumptions
do not match that software. Running the official client or an Android emulator
on a sufficiently capable Node and streaming its window lets the Deck remain a
small interface. The same division also makes Discord feasible later while
keeping account credentials and heavyweight processing on hardware selected by
the user.

## Expansion contract

Every provider uses the same capabilities: list applications, request a
session, read its state, receive its media description, submit only supported
input events, and close it. Future transports or codecs may be negotiated
behind that contract without changing what a Deck means or granting a provider
new authority.
