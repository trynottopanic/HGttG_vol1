#!/usr/bin/env python3
from pathlib import Path
import argparse
import struct

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, help='Validate the installed asset and units in a staged root')
args = parser.parse_args()

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")

asset = HERE / "assets" / "boot-eclipse-v1.rgb565a"
unit = (HERE / "guide-boot-animation.service").read_text(encoding="utf-8")
dropin = (HERE / "15-boot-animation.conf").read_text(encoding="utf-8")
runner = (HERE / "guide_boot_runner.py").read_text(encoding="utf-8")
if args.root:
    asset = args.root / 'usr/share/guideos/boot-animation/boot-eclipse-v1.rgb565a'
    unit = (args.root / 'etc/systemd/system/guide-boot-animation.service').read_text(encoding='utf-8')
    dropin = (args.root / 'etc/systemd/system/guide-shell.service.d/15-boot-animation.conf').read_text(encoding='utf-8')
    runner = (args.root / 'usr/lib/guideos/boot-animation/guide_boot_runner.py').read_text(encoding='utf-8')
source = (HERE / "guide-boot-animation.c").read_text(encoding="utf-8")
data = asset.read_bytes()
magic, width, height, frames, fps_n, fps_d, frame_bytes = struct.unpack("<8s6I", data[:32])

require(magic == b"GOSANIM1", "animation magic")
require((width, height, frames, fps_n, fps_d) == (640, 480, 75, 10, 1),
        "animation dimensions and timing")
require(frame_bytes == width * height * 2, "RGB565 frame size")
require(len(data) == 32 + frames * frame_bytes, "animation file size")
# The effective dependency is owned by the shell drop-in. Type=notify releases
# that dependency at first-frame readiness; Home still waits for DRM release.
require("After=guide-boot-animation.service" in dropin, "shell must wait for boot readiness")
require("Type=notify" in unit and "NotifyAccess=main" in unit, "first-frame startup notification")
require("GUIDE_BOOT_HANDOFF=/run/guideos-boot-animation" in dropin, "shell display handoff")
require("supports_early_home" in runner and "display-released" in runner, "compatible bounded display handoff")
require("TimeoutStartSec=26s" in unit, "unit must have outer cleanup timeout")
require("--initialization 12 --playback 9.5" in unit, "independent phase deadlines")
require("--duration 7.5 --max-runtime 9.5" in unit, "bounded playback duration")
require("guide_boot_dynamic.py" not in unit, "boot must not invoke world generation")
require("Restart=" not in unit, "boot animation must not restart-loop")
require("drmModePageFlip" in source, "KMS page flipping")
require("device_index < 16" in source, "DRM card discovery")
require('open("/dev/dri/card0"' not in source, "must not hard-code DRM card0")
require("gbm_surface_create" in source, "GBM surface")
require("eglCreateContext" in source, "EGL context")
require("boot-eclipse-v1.rgb565a" in source, "prebaked animation asset")
require("glTexSubImage2D" in source, "streamed frame upload")
require("restore_display" in source, "display restoration path")
require("SIGTERM" in source and "SIGINT" in source, "bounded interruption path")

print("GUIDE_BOOT_ANIMATION_SOURCE_VALID")
