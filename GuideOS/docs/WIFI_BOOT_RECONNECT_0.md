# Saved Wi-Fi reconnection at boot

Installed and readback verified on 2026-09-25 at 21:40 UTC with audio-path-7.
All 342 combined ARM userspace tests passed, including 52 connectivity tests.
Boot and user-data partitions were verified unchanged. Physical boot acceptance
is pending.

Physical result: on 2026-09-25 the owner reported "Wifi automatic connection
worked. Wifi connected." The paired link was reachable for the subsequent tone
test without a manually requested connection.

Owner request, 2026-09-25: remember the network and reconnect between boots.
The returned seed already contained one saved NetworkManager profile, hold=false
and an enabled Guide Wi-Fi service. No credentials were printed or changed.
The existing startup policy delayed its first saved-network check by five minutes.

Guide now performs one early scan/connection check once the Wi-Fi device is
available, using only saved profiles and the existing bounded activation flow.
It does not replace an existing connection. Explicit Disconnect still persists
across boots and suppresses automatic reconnection. Manual operations consume
the startup exception, so an unsuccessful manual operation cannot immediately
trigger an extra automatic attempt.

A private runtime marker survives service restarts, but clears on reboot.
Periodic retries retain the five-minute floor, low-battery adjustment and
absence backoff. A missing/unwritable marker does not enable repeated startup
attempts. Unsaved profiles are not sufficient to trigger an early scan.
No general NetworkManager autoconnect policy is enabled; Guide remains the
owner of the explicit Disconnect and retry rules.

Tests cover saved-profile activation without requesting another password,
one check per boot, service restart, persistent Disconnect, delayed device
appearance, unsaved profiles and manual-operation precedence. Physical boot
reconnection remains pending until the installed card boots on the Deck.

This change is combined with audio-path-7 in build/debian-audio-7. The install
preserves saved network files, owner policy, the existing shell release and
the isolated-tone controls. Card readback is recorded in installation.json.
