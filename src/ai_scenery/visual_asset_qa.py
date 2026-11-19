"""Objective smoke checks for generated scenery images and motion loops.

This intentionally does not claim to measure beauty or semantic correctness.
It verifies media integrity, visible variation, and approximate loop closure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(completed.stdout)


def image_metrics(path: Path) -> dict:
    with Image.open(path) as source:
        image = np.asarray(source.convert("RGB"), dtype=np.float32)
        width, height = source.size
    luminance = image.mean(axis=2)
    dx = np.abs(np.diff(luminance, axis=1)).mean()
    dy = np.abs(np.diff(luminance, axis=0)).mean()
    clipped = np.logical_or(image <= 1, image >= 254).mean()
    checks = {
        "portrait": height > width,
        "non_blank": float(image.std()) >= 5.0,
        "not_mostly_clipped": float(clipped) <= 0.50,
    }
    return {
        "kind": "image",
        "width": width,
        "height": height,
        "rgb_std": round(float(image.std()), 4),
        "clipped_fraction": round(float(clipped), 6),
        "edge_energy": round(float((dx + dy) / 2.0), 4),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def video_metrics(path: Path, ffmpeg: Path, ffprobe: Path) -> dict:
    probe = run_json([
        str(ffprobe), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt:format=duration",
        "-of", "json", str(path),
    ])
    stream = probe["streams"][0]
    source_width = int(stream["width"])
    source_height = int(stream["height"])
    sample_width = 135
    sample_height = max(2, round((source_height / source_width) * sample_width / 2) * 2)
    completed = subprocess.run([
        str(ffmpeg), "-v", "error", "-i", str(path),
        "-vf", f"scale={sample_width}:{sample_height}:flags=area",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], check=True, capture_output=True)
    frame_bytes = sample_width * sample_height * 3
    frame_count = len(completed.stdout) // frame_bytes
    if frame_count < 3:
        raise RuntimeError(f"Expected at least 3 decoded frames, found {frame_count}")
    frames = np.frombuffer(completed.stdout[: frame_count * frame_bytes], dtype=np.uint8)
    frames = frames.reshape(frame_count, sample_height, sample_width, 3).astype(np.float32)
    adjacent = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2, 3))
    seam_mad = float(np.abs(frames[0] - frames[-1]).mean())
    excursion = np.abs(frames - frames[0]).mean(axis=(1, 2, 3))
    adjacent_p50 = float(np.median(adjacent))
    seam_limit = max(1.5, adjacent_p50 * 3.0)
    checks = {
        "portrait": source_height > source_width,
        "motion_present": float(excursion.max()) >= 0.05,
        "loop_seam_within_motion_budget": seam_mad <= seam_limit,
        "codec_h264": stream.get("codec_name") == "h264",
        "pixel_format_compatible": stream.get("pix_fmt") in {"yuv420p", "yuvj420p"},
    }
    return {
        "kind": "video",
        "width": source_width,
        "height": source_height,
        "duration_s": float(probe["format"]["duration"]),
        "frame_count_decoded": frame_count,
        "adjacent_mad_p50": round(adjacent_p50, 6),
        "adjacent_mad_max": round(float(adjacent.max()), 6),
        "max_excursion_from_first": round(float(excursion.max()), 6),
        "loop_seam_mad": round(seam_mad, 6),
        "loop_seam_limit": round(seam_limit, 6),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("media", type=Path)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    media = args.media.resolve()
    if not media.is_file():
        raise FileNotFoundError(media)

    if media.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        metrics = image_metrics(media)
    else:
        if not args.ffmpeg or not args.ffprobe:
            parser.error("video inputs require --ffmpeg and --ffprobe")
        metrics = video_metrics(media, args.ffmpeg.resolve(), args.ffprobe.resolve())

    result = {
        "schema_version": "1.0",
        "input_path": str(media),
        "input_sha256": sha256(media),
        "scope_note": "Objective media/motion checks only; aesthetics and semantic artifacts require human review.",
        **metrics,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
