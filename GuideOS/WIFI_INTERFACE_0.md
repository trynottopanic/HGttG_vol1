# Wi-Fi Interface 0

The first Deck Wi-Fi interface is a local, client-only control panel. It can
scan for nearby access points, distinguish open and password-protected
networks, connect, request an address, disconnect, and forget the saved network.
It does not create a hotspot, expose an inbound service, or repeatedly scan in
the background.

The interface is operated with the D-pad, A, and B. Password entry uses a
four-page on-screen keyboard covering lowercase letters, uppercase letters,
digits, punctuation, symbols, and spaces. `CASE` switches directly between the
true lowercase and uppercase font sets; `MORE` opens the two symbol pages.
Password characters are masked on
screen, never written to the diagnostic log, and never passed as a command-line
argument. A temporary configuration is stored with owner-only permissions and
is retained only after association and address assignment both succeed.

The network list also contains explicit Rescan, Disconnect, and Forget Saved
Network actions. Networks are de-duplicated by name and ordered by strongest
reported signal. Hidden unnamed networks are omitted in this initial interface.

Every Guide screen carries a small top-right `ONLINE` or `OFFLINE` indicator
derived from the wireless link state. When a saved network exists, a bounded
background attempt waits for the delayed RG35XX H radio, associates, requests
an address, and verifies that address before reporting the Deck online.

Safe shutdown stops the Deck-owned Wi-Fi process and releases its address before
the final filesystem sync. The shell requests a read-only root as an additional
precaution, but an older vendor kernel refusing that optional remount no longer
prevents the already-synced kernel power-off request.

This is a prototype usability implementation, not a completed security claim.
Threat modeling, adversarial testing, and independent cryptographic review
remain required under security proofing before the interface can be described
as production-safe.
