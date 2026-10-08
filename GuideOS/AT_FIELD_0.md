# AT Field setting 0

Owner-approved behavior, 22 September 2026. AT Field describes how approachable
the user's device is. It combines communication defaults in one ordinary setting.
It does not promise anonymity, perfect protection or isolation from all peers.

The first Windows build exposed a temporary text-buffer lifetime bug in the
selector. It is corrected; the labels remain Closed, Familiar and Open.

| Setting | New interaction |
| --- | --- |
| Closed | No unsolicited discovery or contact. User-initiated connections remain available. |
| Familiar | Known peers can reconnect within existing access. New contacts need acceptance. |
| Open | Advertise availability and accept introductions or invitations. Resource access still follows permissions. |

Changing a preset preserves named exceptions. Details may expose those exceptions
and the underlying choices. The setting does not independently grant files,
media, device control or processing capacity. It does not switch off networking.

Before a change interrupts existing connections, explain the effects. The first
implementation applies changes to future connections and leaves current sessions
and their permissions intact. Its preview says this explicitly. Ending current
sessions remains a separate action; selecting Closed is not a disconnect-all action.

## First implementation: desktop Node

The reusable decision model is [at_field.py](node/desktop/at_field.py). The Node
stores the selected preset and connection exceptions in its existing settings.
The native Windows panel and retained Tk panel offer Closed, Familiar and Open,
with a preview before applying the selection. Exceptions currently have a local
settings API; a graphical exception editor remains future interface work.

- Open answers the existing discovery request. Familiar and Closed do not answer
  anonymous discovery broadcasts; known peers use their saved Node address.
- Familiar permits credential-checked reconnection. Supplying the owner-shared
  pairing code is the existing acceptance path for new peers.
- Closed refuses new incoming pairing and reconnection except for explicitly
  allowed, credential-checked peers. The Node currently has no outgoing connection
  UI; the shared model permits explicit user-initiated connections in every mode.
- An allow exception permits connection, not additional permissions or bypassing
  credentials. A decline exception prevents automatic trusted reconnection.
  The existing owner-mediated pairing path remains a separate acceptance action.
- Existing sessions, media tickets and application permissions remain unchanged.
- Direct access to the existing minimal about endpoint is retained for connection
  setup. This is a discoverability preference, not network invisibility or a firewall.

As an implementation compatibility choice, settings without an AT Field entry
retain the prototype's Open discovery behavior. This is not a selected universal
default for future GuideOS installations. Invalid saved modes produce a settings
error rather than being silently converted to Open. A failed save leaves the
previous effective setting in place.

## Evidence and remaining integration

Tests cover the preset decisions, local initiation, exceptions, unchanged access,
persistence, failed saves, actual UDP discovery changes and HTTP pairing/session
behavior. All 45 desktop Node tests passed on Windows. A separate executable is
built at `build/node-at-field/dist/GuideNode-ATField.exe`; its actual Windows
accessibility text confirms the corrected English selection label. A separate
`--config` path permits interface testing without changing the usual Node profile.
It is not yet integrated into the Deck shell or installed on the seed.
Screen capture failed with `SetIsBorderRequired: No such interface supported
(0x80004002)` and click targeting lacked geometry. Full visual layout and manual
selection/cancel/apply interaction required owner inspection. The owner subsequently
confirmed that the selector is fine; Windows selector acceptance is complete.
Discovery mechanisms for private recognition and
community membership can be added when those providers exist; the setting does
not invent them.
