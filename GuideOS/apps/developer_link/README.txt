GUIDEOS DEVELOPER LINK

Developer Link is included in the base system for diagnostics and supervised
updates on a trusted local network. It remains off after boot until the Deck's
owner explicitly enables it from the local GuideOS interface.

The service accepts key-based authentication only, listens on the Deck's local
Wi-Fi address on port 2222, and can be stopped from the same local interface.
The first start creates a Deck-specific host key in private persistent storage.
