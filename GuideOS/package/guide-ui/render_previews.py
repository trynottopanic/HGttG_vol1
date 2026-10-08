from pathlib import Path

from guide_shell_schema_adapter import home_model, status_model
from guide_field_ui import FieldUI


HERE = Path(__file__).resolve().parent
ui = FieldUI(HERE)
preview = HERE.parent / "preview"
preview.mkdir(parents=True, exist_ok=True)

home = home_model(("media", "status", "wifi", "power"),
                  ("Audio", "System Status", "Wi-Fi", "Power Off"), 0, 78)
ui.render(home).image.save(preview / "home-640x480.png", optimize=True)

status = status_model(("Shell: owns display and controls", "Battery: 78%",
                       "Audio: local playback available", "Wi-Fi: connected",
                       "Power key: system-owned", "Build: next-ui-handoff"), 78)
ui.render(status).image.save(preview / "status-640x480.png", optimize=True)
