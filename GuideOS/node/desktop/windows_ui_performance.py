"""Shared performance safeguards for Guide Windows interfaces."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MovementDecision:
    left: int
    top: int
    pointer_lag_px: float
    governed_lag_px: float
    commit: bool


class MovementGovernor:
    """Collapse high-rate native drag input into display-rate position updates."""

    def __init__(self, refresh_hz: int = 60) -> None:
        self.refresh_hz = min(max(int(refresh_hz or 60), 30), 240)
        self.frame_seconds = 1.0 / self.refresh_hz
        self.last_commit = 0.0
        self.committed = 0
        self.suppressed = 0

    def begin(self, now: float) -> None:
        self.last_commit = now - self.frame_seconds
        self.committed = 0
        self.suppressed = 0

    def decide(
        self,
        *,
        proposed_left: int,
        proposed_top: int,
        current_left: int,
        current_top: int,
        cursor_x: int,
        cursor_y: int,
        offset_x: int,
        offset_y: int,
        now: float,
    ) -> MovementDecision:
        live_left = cursor_x - offset_x
        live_top = cursor_y - offset_y
        lag = math.hypot(live_left - proposed_left, live_top - proposed_top)
        if now - self.last_commit >= self.frame_seconds:
            self.last_commit = now
            self.committed += 1
            return MovementDecision(live_left, live_top, lag, 0.0, True)
        self.suppressed += 1
        governed_lag = math.hypot(
            live_left - current_left, live_top - current_top)
        return MovementDecision(
            current_left, current_top, lag, governed_lag, False)
