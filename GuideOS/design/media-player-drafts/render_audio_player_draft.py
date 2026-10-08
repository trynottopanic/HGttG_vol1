"""Render Audio Player 1 from the reusable Guide Design Schema 0 fixture.

This is a design fixture, not the production framebuffer or audio engine.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
SCHEMA_ROOT = HERE.parent / "schema"
sys.path.insert(0, str(SCHEMA_ROOT))

from guide_design import GuideCanvas, SchemaBundle, SchemaError  # noqa: E402


def draw_artwork(canvas: GuideCanvas, artwork: str) -> None:
    if artwork != "guide-sprig":
        raise SchemaError(f"unsupported artwork fixture: {artwork}")
    part = canvas.components["audio_player"]
    box = (part["art_left"], part["art_top"],
           part["art_right"], part["art_bottom"])
    canvas.draw.rectangle(box, fill=canvas.color("video_field"),
                          outline=canvas.color("ink"), width=1)
    stem_x = (part["art_left"] + part["art_right"]) // 2
    canvas.draw.line((stem_x, 158, stem_x, 99), fill=canvas.color("ink"), width=2)
    canvas.draw.line((stem_x, 132, 62, 112), fill=canvas.color("ink"), width=2)
    canvas.draw.line((stem_x, 120, 105, 96), fill=canvas.color("ink"), width=2)
    canvas.draw.line((stem_x, 145, 106, 129), fill=canvas.color("ink"), width=2)
    for leaf in ((53, 101, 72, 121), (95, 84, 110, 106), (97, 119, 115, 137)):
        canvas.draw.ellipse(leaf, fill=canvas.color("blue"), outline=canvas.color("ink"))


def draw_output_icon(canvas: GuideCanvas, x: int, y: int, color: str) -> None:
    canvas.draw.arc((x, y, x + 25, y + 27), 180, 360,
                    fill=canvas.color(color), width=4)
    canvas.draw.rectangle((x - 1, y + 12, x + 4, y + 27), fill=canvas.color(color))
    canvas.draw.rectangle((x + 22, y + 12, x + 27, y + 27), fill=canvas.color(color))


def draw_transport_button(canvas: GuideCanvas, bounds: list[int], *, selected: bool,
                          icon: str, label: str = "") -> None:
    fill = "rust" if selected else "paper"
    outline = "rust" if selected else "ink"
    canvas.draw.rounded_rectangle(tuple(bounds), radius=3, fill=canvas.color(fill),
                                  outline=canvas.color(outline), width=1)
    center_x = (bounds[0] + bounds[2]) // 2
    center_y = (bounds[1] + bounds[3]) // 2
    icon_color = "white" if selected else "ink"
    if icon == "pause":
        canvas.draw.rectangle((center_x - 8, center_y - 15,
                               center_x - 3, center_y + 3), fill=canvas.color(icon_color))
        canvas.draw.rectangle((center_x + 3, center_y - 15,
                               center_x + 8, center_y + 3), fill=canvas.color(icon_color))
        canvas.text((center_x, center_y + 15), label, role="body",
                    color=icon_color, anchor="mm")
    elif icon in ("previous", "next"):
        direction = -1 if icon == "previous" else 1
        bar_x = center_x + direction * 12
        canvas.draw.rectangle((bar_x - 2, center_y - 11,
                               bar_x + 2, center_y + 11), fill=canvas.color(icon_color))
        points = ((center_x - direction * 8, center_y - 12),
                  (center_x + direction * 10, center_y),
                  (center_x - direction * 8, center_y + 12))
        canvas.draw.polygon(points, fill=canvas.color(icon_color))
    else:
        raise SchemaError(f"unsupported transport icon: {icon}")


def draw_player(canvas: GuideCanvas, track: dict[str, Any],
                transport: dict[str, Any]) -> None:
    part = canvas.components["audio_player"]
    canvas.draw.rectangle((part["panel_left"], part["panel_top"],
                           part["panel_right"], part["panel_bottom"]),
                          outline=canvas.color("ink"), width=1)
    draw_artwork(canvas, track["artwork"])
    canvas.text((part["title_x"], part["title_y"]), track["title"],
                role="masthead", anchor="lm")
    canvas.text((part["title_x"], part["source_y"]), track["source"],
                role="body", color="blue", anchor="lm")
    draw_output_icon(canvas, part["title_x"] + 4, part["output_y"] - 14,
                     track["output_color"])
    canvas.text((part["title_x"] + 55, part["output_y"]), track["output"],
                role="body_strong", color=track["output_color"], anchor="lm")

    canvas.text((part["panel_left"] + 12, part["time_y"]), transport["elapsed"],
                role="numeric", anchor="lm")
    canvas.text((part["panel_right"] - 12, part["time_y"]), transport["duration"],
                role="numeric", anchor="rm")
    bar = (part["progress_left"], part["progress_top"],
           part["progress_right"], part["progress_bottom"])
    canvas.draw.rectangle(bar, fill=canvas.color("track"))
    progress_x = round(part["progress_left"] +
                       (part["progress_right"] - part["progress_left"]) *
                       transport["progress"])
    canvas.draw.rectangle((part["progress_left"], part["progress_top"],
                           progress_x, part["progress_bottom"]),
                          fill=canvas.color("blue"))
    canvas.draw.ellipse((progress_x - 7, part["progress_top"] - 5,
                         progress_x + 7, part["progress_bottom"] + 5),
                        fill=canvas.color("blue"), outline=canvas.color("ink"))

    draw_transport_button(canvas, part["previous_button"], selected=False,
                          icon="previous")
    draw_transport_button(canvas, part["pause_button"], selected=True,
                          icon="pause", label=transport["action"])
    draw_transport_button(canvas, part["next_button"], selected=False,
                          icon="next")


def draw_queue(canvas: GuideCanvas, items: list[dict[str, Any]]) -> None:
    part = canvas.components["audio_queue"]
    canvas.draw.rectangle((part["left"], part["top"], part["right"], part["bottom"]),
                          fill=canvas.color("panel"), outline=canvas.color("ink"), width=1)
    for index, item in enumerate(items):
        top = part["top"] + 7 + index * part["row_height"]
        bottom = top + part["row_height"] - 1
        if item["selected"]:
            canvas.draw.rectangle((part["left"] + 5, top, part["right"] - 5, bottom),
                                  fill=canvas.color("paper"),
                                  outline=canvas.color("rust"), width=2)
            canvas.draw.polygon(((38, top + 10), (38, top + 28), (53, top + 19)),
                                fill=canvas.color("rust"))
        elif index:
            canvas.draw.line((part["left"] + 5, top, part["right"] - 5, top),
                             fill=canvas.color("blue_light"))
        baseline = part["first_baseline_y"] + index * part["row_height"]
        canvas.text((part["label_x"], baseline), item["label"],
                    role="body_strong" if item["selected"] else "body", anchor="lm")
        for offset in (-7, 0, 7):
            canvas.draw.ellipse((part["menu_x"] - 2, baseline + offset - 2,
                                 part["menu_x"] + 2, baseline + offset + 2),
                                fill=canvas.color("blue"))


def render(output: Path | None = None) -> Path:
    fixture = SCHEMA_ROOT / "fixtures" / "audio-player.toml"
    bundle = SchemaBundle.load(SCHEMA_ROOT, fixture)
    screen = bundle.screen
    canvas = GuideCanvas(bundle)
    canvas.header(screen["header"]["identity"], screen["header"]["title"],
                  screen["header"]["accessory"])
    draw_player(canvas, screen["track"], screen["transport"])
    draw_queue(canvas, screen["queue"]["items"])
    canvas.footer(screen["footer"]["actions"], screen["footer"]["accessory"])
    target = output or HERE / screen["screen"]["output"]
    canvas.save(target)
    return target


if __name__ == "__main__":
    render()
