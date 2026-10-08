"""Semantic models shared by the sole installed Guide Field renderer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image


class UIError(ValueError):
    pass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def tuple(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom


@dataclass(frozen=True)
class Region:
    identity: str
    label: str
    rect: Rect
    action: str
    value: Any = None


@dataclass(frozen=True)
class MenuItem:
    identity: str
    label: str
    action: str = "open"
    value: Any = None
    enabled: bool = True
    metadata: str = ""


@dataclass(frozen=True)
class Fact:
    label: str
    value: str
    state: str = "neutral"


@dataclass(frozen=True)
class ActionHint:
    button: str
    label: str
    color: str
    identity: str = ""
    action: str = ""
    value: Any = None


@dataclass(frozen=True)
class ScreenModel:
    pattern: str
    title: str
    identity: str = "The Guide"
    battery_percent: int | None = None
    items: tuple[MenuItem, ...] = ()
    focus_id: str | None = None
    facts: tuple[Fact, ...] = ()
    notice: str = ""
    notice_state: str = "neutral"
    actions: tuple[ActionHint, ...] = ()
    transition: float = 1.0
    content: str = ""
    scroll: int = 0


@dataclass(frozen=True)
class LayoutResult:
    image: Image.Image
    regions: tuple[Region, ...] = field(default_factory=tuple)
    visible_ids: tuple[str, ...] = field(default_factory=tuple)
    # Optional board presentation layers; semantic targets remain identical.
    layers: tuple[Any, ...] = field(default_factory=tuple)
