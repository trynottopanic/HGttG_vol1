"""Portable AT Field preferences; connection policy, not resource permissions."""
from dataclasses import dataclass
from enum import Enum

class FieldMode(str, Enum):
    CLOSED = "closed"
    FAMILIAR = "familiar"
    OPEN = "open"


DESCRIPTIONS = {
    FieldMode.CLOSED: "Hide from discovery and decline new incoming connections.",
    FieldMode.FAMILIAR: "Hide from public discovery; known peers may reconnect. New peers need acceptance.",
    FieldMode.OPEN: "Be discoverable and accept introductions. Access still follows your permissions.",
}


@dataclass(frozen=True)
class ATField:
    mode: FieldMode
    # Explicit connection exceptions by verified peer identity. No extra access.
    exceptions: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self):
        if not isinstance(self.mode, FieldMode):
            raise ValueError("unknown AT Field mode")
        seen = set()
        for peer, allowed in self.exceptions:
            if not isinstance(peer, str) or not peer or type(allowed) is not bool or peer in seen:
                raise ValueError("invalid or duplicate AT Field exception")
            seen.add(peer)

    @property
    def discoverable(self):
        return self.mode == FieldMode.OPEN

    def connection(self, peer="", *, known=False, initiated_here=False,
                   accepted=False):
        """Return allow, ask or decline; caller supplies verified context.

        An Open introduction still needs independent resource authorization.
        Explicit action here can initiate a connection even while Closed.
        A peer-specific decline can be overridden by a new explicit local action.
        """
        if initiated_here:
            return "allow"
        exceptions = dict(self.exceptions)
        if peer and peer in exceptions:
            return "allow" if exceptions[peer] else "decline"
        if self.mode == FieldMode.CLOSED:
            return "decline"
        if known or accepted or self.mode == FieldMode.OPEN:
            return "allow"
        return "ask"

    def with_mode(self, mode):
        return ATField(FieldMode(mode), self.exceptions)

    def to_dict(self):
        return {"version": 1, "mode": self.mode.value,
                "exceptions": dict(self.exceptions)}

    @classmethod
    def from_dict(cls, value):
        if (not isinstance(value, dict) or value.get("version") != 1
                or not isinstance(value.get("exceptions", {}), dict)):
            raise ValueError("unsupported AT Field settings")
        return cls(FieldMode(value.get("mode")), tuple(value.get("exceptions", {}).items()))

    def preview(self, active_connections=0):
        return (f"AT Field: {self.mode.value.title()}\n\n{DESCRIPTIONS[self.mode]}\n\n"
                f"Existing connections stay connected ({active_connections} active). "
                "Their current permissions do not change.\n"
                f"Connection exceptions retained: {len(self.exceptions)}.\n"
                "You can still initiate a connection yourself.")
