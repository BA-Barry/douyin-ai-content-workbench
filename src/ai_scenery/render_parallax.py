"""Render a restrained seamless parallax loop from an image and depth map."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from attrs import define
from depthflow.scene import DepthScene


@define
class SubtleSceneryLoop(DepthScene):
    """A loop-safe camera path designed for landscapes, not demo-reel motion."""

    horizontal: float = 0.055
    vertical: float = 0.025
    zoom_amount: float = 0.018

    def update(self) -> None:
        self.state.height = 0.16
        self.state.steady = 0.32
        self.state.focus = 0.28
        self.state.isometric = 0.72
        self.state.offset = (
            self.horizontal * math.sin(self.cycle),
            self.vertical * (1.0 - math.cos(self.cycle)),
        )
        self.state.zoom = 1.0 + self.zoom_amount * (1.0 - math.cos(self.cycle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--depth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=540)
    parser.add_argument("--height", type=int, default=960)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for source in (args.image, args.depth):
        if not source.is_file():
            raise FileNotFoundError(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    scene = SubtleSceneryLoop(backend="headless")
    scene.ffmpeg.h264(preset="veryfast", crf=20)
    scene.input(image=args.image, depth=args.depth)
    scene.main(
        output=args.output,
        time=args.seconds,
        fps=args.fps,
        width=args.width,
        height=args.height,
        ssaa=1.0,
    )

    print(json.dumps({
        "status": "PASS",
        "image": str(args.image.resolve()),
        "depth": str(args.depth.resolve()),
        "output": str(args.output.resolve()),
        "seconds": args.seconds,
        "fps": args.fps,
        "resolution": [args.width, args.height],
        "loop_path": "sin_cos_closed",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
