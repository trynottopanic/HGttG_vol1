"""Validate the handoff without installing or touching a device."""

from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from guide_shell_schema_adapter import home_model, status_model
from guide_field_ui import FieldUI


HERE = Path(__file__).resolve().parent


def main() -> None:
    for path in (HERE / "guide_ui_model.py", HERE / "guide_field_ui.py", HERE / "guide_shell_schema_adapter.py",
                 HERE / "render_previews.py", HERE / "test_guide_ui.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_guide_ui.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    ui = FieldUI(HERE)
    models = (
        home_model(("media", "status", "wifi", "power"),
                   ("Audio", "System Status", "Wi-Fi", "Power Off"), 0, 78),
        status_model(("Shell: owns display and controls", "Battery: 78%"), 78),
    )
    with tempfile.TemporaryDirectory() as folder:
        for index, model in enumerate(models):
            path = Path(folder) / f"screen-{index}.png"
            ui.render(model).image.save(path)
            with Image.open(path) as image:
                if image.size != (640, 480) or image.mode != "RGB":
                    raise SystemExit("invalid rendered image")
    print("GUIDE_UI_HANDOFF_VALID")


if __name__ == "__main__":
    main()
