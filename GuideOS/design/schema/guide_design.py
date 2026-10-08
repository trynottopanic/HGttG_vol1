"""Bounded Guide Design Schema 0 loader and shared Pillow components.

This module renders deterministic design fixtures. It owns no application state,
input, display device, media engine, network connection, or persistent storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class SchemaError(ValueError):
    """Raised when a design fixture refers to an undeclared or invalid value."""


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as source:
        return tomllib.load(source)


@dataclass(frozen=True)
class SchemaBundle:
    tokens: dict[str, Any]
    components: dict[str, Any]
    screen: dict[str, Any]

    @classmethod
    def load(cls, root: Path, fixture: Path) -> "SchemaBundle":
        bundle = cls(load_toml(root / "tokens.toml"),
                     load_toml(root / "components.toml"),
                     load_toml(fixture))
        bundle.validate()
        return bundle

    def validate(self) -> None:
        profile = self.tokens["display"]["profile"]
        if self.components["schema"]["display_profile"] != profile:
            raise SchemaError("component display profile does not match tokens")
        if self.screen["screen"]["display_profile"] != profile:
            raise SchemaError("screen display profile does not match tokens")
        if self.screen["screen"]["schema_version"] != self.tokens["schema"]["version"]:
            raise SchemaError("screen schema version does not match tokens")
        width = self.tokens["display"]["width"]
        height = self.tokens["display"]["height"]
        if (width, height) != (640, 480):
            raise SchemaError("Schema 0 supports only the deck-640x480 profile")
        pattern = self.screen["screen"]["pattern"]
        if pattern not in ("video-player", "audio-player"):
            raise SchemaError(f"unsupported screen pattern: {pattern}")
        progress = self.screen["transport"]["progress"]
        if not 0.0 <= progress <= 1.0:
            raise SchemaError("transport progress must be between zero and one")
        colors = self.tokens["colors"]
        references = [self.screen["transport"]["accent"]]
        references.extend(accessory.get("color", "ink")
                          for accessory in (self.screen["header"]["accessory"],
                                            self.screen["footer"]["accessory"]))
        references.extend(action["color"]
                          for action in self.screen["footer"]["actions"])
        if pattern == "video-player":
            references.extend(item.get("color", "ink")
                              for item in self.screen["status"]["items"])
        else:
            references.append(self.screen["track"]["output_color"])
        missing = sorted({name for name in references if name not in colors})
        if missing:
            raise SchemaError(f"unknown color tokens: {', '.join(missing)}")
        required = ["application_header", "application_footer", "button_badge"]
        if pattern == "video-player":
            required.extend(("status_panel", "video_viewport", "video_transport"))
        else:
            required.extend(("audio_player", "audio_queue"))
            if not 1 <= len(self.screen["queue"]["items"]) <= 3:
                raise SchemaError("audio-player queue fixture requires one to three items")
        for name in required:
            if name not in self.components:
                raise SchemaError(f"missing component: {name}")


class GuideCanvas:
    """Shared primitives whose geometry and appearance come from the schema."""

    def __init__(self, bundle: SchemaBundle):
        self.bundle = bundle
        self.colors = bundle.tokens["colors"]
        self.components = bundle.components
        width = bundle.tokens["display"]["width"]
        height = bundle.tokens["display"]["height"]
        self.image = Image.new("RGB", (width, height), self.color("paper"))
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {role: self._load_role(spec)
                      for role, spec in bundle.tokens["typography"].items()}

    def color(self, name: str) -> str:
        try:
            return self.colors[name]
        except KeyError as error:
            raise SchemaError(f"unknown color token: {name}") from error

    @staticmethod
    def _font_roots() -> tuple[Path, ...]:
        return (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                Path("/usr/share/fonts/truetype/noto"),
                Path("/usr/share/fonts/truetype/dejavu"))

    def _load_role(self, role: dict[str, Any]) -> ImageFont.ImageFont:
        family = role["family"]
        weight = role["weight"]
        font_spec = self.bundle.tokens["fonts"][family][weight]
        names = font_spec["production"] + font_spec["reduced"] + font_spec["preview"]
        for name in names:
            for root in self._font_roots():
                path = root / name
                if path.is_file():
                    return ImageFont.truetype(str(path), role["size"])
        raise SchemaError(f"no usable font for {family}.{weight}")

    def text(self, xy: tuple[int, int], value: str, *, role: str = "body",
             color: str = "ink", anchor: str | None = None) -> None:
        self.draw.text(xy, value, font=self.fonts[role], fill=self.color(color),
                       anchor=anchor)

    def battery(self, x: int, y: int, width: int, height: int,
                battery_percent: int, *, percentage_x: int,
                baseline_y: int) -> None:
        if not 0 <= battery_percent <= 100:
            raise SchemaError("battery percentage must be between zero and 100")
        self.draw.rectangle((x, y, x + width, y + height),
                            outline=self.color("ink"), width=2)
        self.draw.rectangle((x + width, y + 4, x + width + 3, y + height - 4),
                            fill=self.color("ink"))
        inner = round((width - 7) * battery_percent / 100)
        self.draw.rectangle((x + 3, y + 3, x + 3 + inner, y + height - 3),
                            fill=self.color("green"))
        self.text((percentage_x, baseline_y), f"{battery_percent}%",
                  role="numeric", anchor="rm")

    def header(self, identity: str, title: str,
               accessory: dict[str, Any]) -> None:
        part = self.components["application_header"]
        self.text((part["left"], part["baseline_y"]), identity,
                  role="masthead", anchor="lm")
        if title:
            self.text(((part["left"] + part["right"]) // 2, part["baseline_y"]),
                      title, role="screen_title", anchor="mm")
        kind = accessory["kind"]
        if kind == "battery":
            self.battery(part["battery_x"], part["battery_y"],
                         part["battery_width"], part["battery_height"],
                         accessory["value"], percentage_x=part["right"],
                         baseline_y=part["baseline_y"])
        elif kind == "text":
            self.text((part["accessory_x"], part["baseline_y"]), accessory["value"],
                      role="screen_title", color=accessory.get("color", "ink"),
                      anchor="rm")
        else:
            raise SchemaError(f"unsupported header accessory: {kind}")
        self.draw.line((part["left"], part["rule_y"], part["right"], part["rule_y"]),
                       fill=self.color("ink"))

    def panel(self, component: str) -> None:
        part = self.components[component]
        self.draw.rectangle((part["left"], part["top"], part["right"], part["bottom"]),
                            fill=self.color("panel"), outline=self.color("ink"), width=1)

    def button_badge(self, x: int, y: int, label: str, color: str) -> int:
        part = self.components["button_badge"]
        font = self.fonts["control_strong"]
        width = max(part["minimum_width"],
                    int(self.draw.textlength(label, font=font)) + part["horizontal_padding"])
        height = self.bundle.tokens["shape"]["button_height"]
        radius = self.bundle.tokens["shape"]["button_radius"]
        self.draw.rounded_rectangle((x, y, x + width, y + height), radius=radius,
                                    fill=self.color(color))
        self.text((x + width // 2, y + height // 2), label,
                  role="control_strong", color="white", anchor="mm")
        return width

    def footer(self, actions: list[dict[str, Any]],
               accessory: dict[str, Any]) -> None:
        footer = self.components["application_footer"]
        badge = self.components["button_badge"]
        self.draw.line((footer["left"], footer["rule_y"],
                        footer["right"], footer["rule_y"]), fill=self.color("ink"))
        x = footer["left"]
        for action in actions:
            width = self.button_badge(x, footer["button_top"], action["button"],
                                      action["color"])
            label_x = x + width + badge["label_gap"]
            self.text((label_x, footer["baseline_y"]), action["label"],
                      role="control", anchor="lm")
            label_width = int(self.draw.textlength(action["label"],
                                                   font=self.fonts["control"]))
            x = label_x + label_width + badge["item_gap"]
        kind = accessory["kind"]
        if kind == "text":
            self.text((footer["right"], footer["baseline_y"]), accessory["value"],
                      role="metadata", color=accessory.get("color", "ink"), anchor="rm")
        elif kind == "battery":
            self.battery(footer["battery_x"], footer["battery_y"],
                         footer["battery_width"], footer["battery_height"],
                         accessory["value"], percentage_x=footer["right"],
                         baseline_y=footer["baseline_y"])
        else:
            raise SchemaError(f"unsupported footer accessory: {kind}")

    def save(self, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(output, optimize=True)
