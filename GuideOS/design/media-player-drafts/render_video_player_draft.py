"""Render Video Player 1 from the reusable Guide Design Schema 0 fixture.

This is a design fixture, not the production framebuffer or media engine.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
SCHEMA_ROOT = HERE.parent / "schema"
sys.path.insert(0, str(SCHEMA_ROOT))

from guide_design import GuideCanvas, SchemaBundle, SchemaError  # noqa: E402


def draw_landscape(canvas: GuideCanvas, placeholder: str) -> None:
    """Draw fixed fixture imagery where a production renderer shows video."""
    if placeholder != "paper-mountains":
        raise SchemaError(f"unsupported video placeholder: {placeholder}")
    draw = canvas.draw
    part = canvas.components["video_viewport"]
    viewport = (part["left"], part["top"], part["right"], part["bottom"])
    draw.rectangle(viewport, fill=canvas.color("video_field"),
                   outline=canvas.color("ink"), width=1)
    draw.ellipse((424, 74, 466, 116), fill=canvas.color("video_sun"))
    draw.polygon([(17, 176), (92, 118), (179, 174), (263, 128),
                  (351, 181), (462, 129), (624, 183), (624, 332), (17, 332)],
                 fill=canvas.color("blue_light"))
    draw.polygon([(17, 223), (116, 160), (206, 229), (304, 177),
                  (415, 235), (528, 167), (624, 218), (624, 332), (17, 332)],
                 fill=canvas.color("blue"))
    draw.polygon([(17, 263), (83, 219), (154, 270), (246, 226),
                  (348, 283), (439, 235), (517, 284), (624, 227),
                  (624, 332), (17, 332)], fill=canvas.color("video_dark"))


def draw_transport(canvas: GuideCanvas, state: dict[str, Any]) -> None:
    draw = canvas.draw
    part = canvas.components["video_transport"]
    draw.rectangle((part["left"], part["top"], part["right"], part["bottom"]),
                   fill=canvas.color("transport"))
    draw.rounded_rectangle((part["button_left"], part["button_top"],
                            part["button_right"], part["button_bottom"]),
                           radius=canvas.bundle.tokens["shape"]["transport_radius"],
                           fill=canvas.color(state["accent"]))
    if state["state"] == "paused":
        draw.rectangle(tuple(part["pause_bar_1"]), fill=canvas.color("white"))
        draw.rectangle(tuple(part["pause_bar_2"]), fill=canvas.color("white"))
    else:
        raise SchemaError(f"unsupported transport state: {state['state']}")
    canvas.text((61, part["baseline_y"]), state["action"], role="body_strong",
                color="white", anchor="lm")
    canvas.text((part["elapsed_x"], part["baseline_y"]), state["elapsed"],
                role="numeric", color="white", anchor="lm")
    bar = (part["progress_left"], part["progress_top"],
           part["progress_right"], part["progress_bottom"])
    radius = canvas.bundle.tokens["shape"]["progress_radius"]
    draw.rounded_rectangle(bar, radius=radius, fill=canvas.color("track"))
    progress_x = round(part["progress_left"] +
                       (part["progress_right"] - part["progress_left"]) * state["progress"])
    draw.rounded_rectangle((part["progress_left"], part["progress_top"],
                            progress_x, part["progress_bottom"]), radius=radius,
                           fill=canvas.color(state["accent"]))
    draw.ellipse((progress_x - 5, part["progress_top"] - 3,
                  progress_x + 6, part["progress_bottom"] + 3),
                 fill=canvas.color("white"), outline=canvas.color("ink"))
    canvas.text((part["duration_x"], part["baseline_y"]), state["duration"],
                role="numeric", color="white", anchor="rm")


def draw_status(canvas: GuideCanvas, items: list[dict[str, Any]]) -> None:
    if len(items) != 3:
        raise SchemaError("Video Player 1 status panel requires three items")
    canvas.panel("status_panel")
    part = canvas.components["status_panel"]
    for x in part["divider_x"]:
        canvas.draw.line((x, part["divider_top"], x, part["divider_bottom"]),
                         fill=canvas.color("blue_light"))
    text_x = part["text_x"]
    for index, item in enumerate(items):
        if item["kind"] == "headphones":
            icon = canvas.components["headphone_icon"]
            color = item.get("color", "ink")
            canvas.draw.arc((icon["left"] + 1, icon["top"],
                             icon["right"] - 1, icon["bottom"]),
                            180, 360, fill=canvas.color(color), width=4)
            canvas.draw.rectangle((icon["left"], icon["top"] + 12,
                                   icon["left"] + 5, icon["bottom"]),
                                  fill=canvas.color(color))
            canvas.draw.rectangle((icon["right"] - 5, icon["top"] + 12,
                                   icon["right"], icon["bottom"]),
                                  fill=canvas.color(color))
            canvas.text((text_x[index], part["baseline_y"]), item["label"],
                        role="body_strong", color=color, anchor="lm")
        elif item["kind"] == "text":
            canvas.text((text_x[index], part["baseline_y"]), item["label"],
                        role="body_strong", anchor="lm")
        else:
            raise SchemaError(f"unsupported status kind: {item['kind']}")


def render(output: Path | None = None) -> Path:
    fixture = SCHEMA_ROOT / "fixtures" / "video-player.toml"
    bundle = SchemaBundle.load(SCHEMA_ROOT, fixture)
    screen = bundle.screen
    canvas = GuideCanvas(bundle)
    canvas.header(screen["header"]["identity"], screen["header"]["title"],
                  screen["header"]["accessory"])
    draw_landscape(canvas, screen["video"]["placeholder"])
    draw_transport(canvas, screen["transport"])
    draw_status(canvas, screen["status"]["items"])
    canvas.footer(screen["footer"]["actions"], screen["footer"]["accessory"])
    target = output or HERE / screen["screen"]["output"]
    canvas.save(target)
    return target


if __name__ == "__main__":
    render()
