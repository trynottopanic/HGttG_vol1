"""Allowlisted diagnostic command catalog for the minimal Desktop Node profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DiagnosticCommand:
    command_id: str
    label: str
    category: str
    operation: str
    state_changing: bool = False
    owner_confirmation: bool = False
    timeout_seconds: float = 30.0


READ_ONLY_COMMANDS: tuple[DiagnosticCommand, ...] = (
    DiagnosticCommand("deck.identity", "Deck identity", "identity", "status"),
    DiagnosticCommand("deck.health", "Deck health", "health", "health"),
    DiagnosticCommand("deck.report", "Diagnostic report", "diagnostics", "report"),
    DiagnosticCommand("deck.inspect", "System inspection", "diagnostics", "inspect"),
    DiagnosticCommand("deck.full_capture", "Full Deck diagnostic capture", "diagnostics", "capture",
                      timeout_seconds=240.0),
    DiagnosticCommand("deck.audio_path", "Audio path", "audio", "audio-path"),
    DiagnosticCommand("deck.process_snapshot", "Process snapshot", "system", "health"),
    DiagnosticCommand("deck.service_snapshot", "Service snapshot", "system", "inspect"),
    DiagnosticCommand("deck.storage_snapshot", "Storage snapshot", "system", "inspect"),
    DiagnosticCommand("deck.link_snapshot", "Link snapshot", "connection", "health"),
)


class DiagnosticCatalog:
    """Immutable command registry; no shell or caller-selected paths are accepted."""

    def __init__(self, commands: tuple[DiagnosticCommand, ...] = READ_ONLY_COMMANDS) -> None:
        ids = [item.command_id for item in commands]
        if len(ids) != len(set(ids)):
            raise ValueError("diagnostic command IDs must be unique")
        if any(item.state_changing for item in commands):
            raise ValueError("state-changing commands are not allowed in the default catalog")
        self._commands = tuple(commands)
        self._by_id = {item.command_id: item for item in self._commands}

    def list(self) -> list[dict[str, object]]:
        return [self._public(item) for item in self._commands]

    def resolve(self, command_id: str, parameters: Mapping[str, object] | None = None) -> DiagnosticCommand:
        if not isinstance(command_id, str) or command_id not in self._by_id:
            raise KeyError("diagnostic command is not registered")
        if parameters not in (None, {}):
            raise ValueError("this diagnostic command accepts no parameters")
        return self._by_id[command_id]

    @staticmethod
    def _public(item: DiagnosticCommand) -> dict[str, object]:
        return {"id": item.command_id, "label": item.label, "category": item.category,
                "operation": item.operation, "state_changing": item.state_changing,
                "owner_confirmation": item.owner_confirmation,
                "timeout_seconds": item.timeout_seconds}
