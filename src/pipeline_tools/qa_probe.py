"""Read-only technical QA probe built around ffprobe and ffmpeg."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _tool(explicit: str | None, environment_name: str, fallback: str) -> str:
    candidate = explicit or os.environ.get(environment_name) or fallback
    return str(Path(candidate)) if Path(candidate).exists() else candidate


def _parse_intervals(text: str, start_key: str, end_key: str) -> list[dict[str, float | None]]:
    starts = [float(value) for value in re.findall(rf"{re.escape(start_key)}:\s*([0-9.]+)", text)]
    ends = [float(value) for value in re.findall(rf"{re.escape(end_key)}:\s*([0-9.]+)", text)]
    intervals: list[dict[str, float | None]] = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else None
        intervals.append({"start_s": start, "end_s": end, "duration_s": None if end is None else end - start})
    return intervals


def _parse_ebur128(text: str) -> dict[str, float | None]:
    summary = text.rsplit("Summary:", 1)[-1]
    integrated = re.search(r"I:\s*(-?(?:inf|[0-9.]+))\s*LUFS", summary, re.IGNORECASE)
    true_peak = re.search(r"Peak:\s*(-?(?:inf|[0-9.]+))\s*dBFS", summary, re.IGNORECASE)

    def number(match: re.Match[str] | None) -> float | None:
        if not match or match.group(1).lower() == "-inf":
            return None
        return float(match.group(1))

    return {"integrated_lufs": number(integrated), "true_peak_dbfs": number(true_peak)}


def probe_media(
    media_path: str | Path,
    *,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
) -> dict[str, Any]:
    """Inspect a media file without modifying it and return JSON-compatible data."""
    path = Path(media_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    ffmpeg_bin = _tool(ffmpeg, "PROJECT_FFMPEG_EXE", "ffmpeg")
    ffprobe_bin = _tool(ffprobe, "PROJECT_FFPROBE_EXE", "ffprobe")
    before = _sha256(path)

    probe = _run([
        ffprobe_bin,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path),
    ])
    if probe.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {probe.stderr.strip()}")
    metadata = json.loads(probe.stdout)

    streams = metadata.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    analyses: dict[str, dict[str, Any]] = {}
    commands = {
        "black": [ffmpeg_bin, "-hide_banner", "-nostdin", "-i", str(path), "-an", "-vf", "blackdetect=d=0.10:pix_th=0.10", "-f", "null", "-"],
        "freeze": [ffmpeg_bin, "-hide_banner", "-nostdin", "-i", str(path), "-an", "-vf", "freezedetect=n=0.003:d=0.50", "-f", "null", "-"],
        "silence": [ffmpeg_bin, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "silencedetect=n=-50dB:d=0.10", "-f", "null", "-"],
        "loudness": [ffmpeg_bin, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
    }
    for name, command in commands.items():
        if name in {"silence", "loudness"} and audio_stream is None:
            analyses[name] = {
                "status": "NOT_APPLICABLE",
                "returncode": None,
                "error": None,
                "reason": "NO_AUDIO_STREAM",
            }
            if name == "silence":
                analyses[name]["intervals"] = []
            else:
                analyses[name].update({"integrated_lufs": None, "true_peak_dbfs": None})
            continue
        completed = _run(command)
        analyses[name] = {
            "status": "PASS" if completed.returncode == 0 else "ERROR",
            "returncode": completed.returncode,
            "error": None if completed.returncode == 0 else completed.stderr[-2000:],
        }
        if name == "black":
            analyses[name]["intervals"] = _parse_intervals(completed.stderr, "black_start", "black_end")
        elif name == "freeze":
            analyses[name]["intervals"] = _parse_intervals(completed.stderr, "freeze_start", "freeze_end")
        elif name == "silence":
            analyses[name]["intervals"] = _parse_intervals(completed.stderr, "silence_start", "silence_end")
        else:
            analyses[name].update(_parse_ebur128(completed.stderr))

    after = _sha256(path)
    result = {
        "schema_version": "1.1",
        "input_path": str(path),
        "input_sha256": before,
        "content_unchanged": before == after,
        "media": {
            "duration_s": _float_or_none(metadata.get("format", {}).get("duration")),
            "format_name": metadata.get("format", {}).get("format_name"),
            "size_bytes": _int_or_none(metadata.get("format", {}).get("size")),
            "video": _stream_summary(video_stream),
            "audio": _stream_summary(audio_stream),
            "stream_count": len(streams),
        },
        "analyses": analyses,
    }
    acceptable_statuses = {"PASS", "NOT_APPLICABLE"}
    result["status"] = "PASS" if result["content_unchanged"] and all(item["status"] in acceptable_statuses for item in analyses.values()) else "FAIL"
    return result


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stream_summary(stream: dict[str, Any] | None) -> dict[str, Any] | None:
    if stream is None:
        return None
    return {
        key: stream.get(key)
        for key in ("codec_name", "codec_long_name", "width", "height", "pix_fmt", "r_frame_rate", "sample_rate", "channels", "channel_layout")
        if stream.get(key) is not None
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only FFmpeg media QA probe; emits structured JSON.")
    parser.add_argument("media", help="Absolute or relative path to the media file")
    parser.add_argument("--output", help="JSON output path; stdout when omitted")
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg executable path")
    parser.add_argument("--ffprobe", help="Explicit ffprobe executable path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = probe_media(args.media, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except Exception as exc:  # CLI boundary
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
