# CONTINUE-ON-DECK-0 system overlay

This overlay is intentionally separate from the baseline image until that
image has built successfully. It creates a private USB network device for the
Windows Node, gives the Deck the fixed address `192.168.77.2`, and starts the
minimal receive-and-play runtime.

The development USB identifiers and fixed prototype serial number are suitable
only for a controlled first test. A distributable device requires properly
assigned identifiers and a unique, persistent device identity.
