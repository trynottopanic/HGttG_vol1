#!/usr/bin/env python3
"""Convert an authored GIF into GuideOS's fixed RGB565 boot stream."""

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageSequence


MAGIC = b"GOSANIM1"
HEADER = struct.Struct("<8s6I")
WIDTH = 640
HEIGHT = 480


def rgb565(image):
    pixels = image.convert("RGB").tobytes()
    output = bytearray(WIDTH * HEIGHT * 2)
    for source, target in zip(range(0, len(pixels), 3), range(0, len(output), 2)):
        red, green, blue = pixels[source:source + 3]
        value = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        output[target] = value & 255
        output[target + 1] = value >> 8
    return output


def convert(source, destination):
    with Image.open(source) as animation:
        frames = [frame.copy().convert("RGB") for frame in ImageSequence.Iterator(animation)]
        durations = [frame.info.get("duration", animation.info.get("duration", 0))
                     for frame in ImageSequence.Iterator(animation)]
    if not frames or any(frame.size != (WIDTH, HEIGHT) for frame in frames):
        raise SystemExit("animation must contain 640x480 frames")
    if not durations or any(duration != durations[0] for duration in durations):
        raise SystemExit("animation must use one fixed frame duration")
    duration = durations[0]
    if duration <= 0 or 1000 % duration:
        raise SystemExit("frame duration must divide one second exactly")
    fps = 1000 // duration
    if len(frames) * duration != 7500:
        raise SystemExit("animation must last exactly 7.5 seconds")
    frame_bytes = WIDTH * HEIGHT * 2
    header = HEADER.pack(MAGIC, WIDTH, HEIGHT, len(frames), fps, 1, frame_bytes)
    with destination.open("wb") as stream:
        stream.write(header)
        for frame in frames:
            stream.write(rgb565(frame))
    expected = HEADER.size + len(frames) * frame_bytes
    if destination.stat().st_size != expected:
        raise SystemExit("output size verification failed")
    print(f"GUIDE_PREBAKED_ANIMATION_BUILT frames={len(frames)} fps={fps} bytes={expected}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    convert(arguments.source, arguments.destination)


if __name__ == "__main__":
    main()
