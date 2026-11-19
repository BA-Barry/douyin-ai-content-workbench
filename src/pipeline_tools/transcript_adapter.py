"""Normalize saved FunASR/faster-whisper JSON without invoking or downloading models."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _word(text: str, start: Any, end: Any, *, milliseconds: bool = False) -> dict[str, Any]:
    token = str(text).strip()
    if not token:
        raise ValueError("Empty word/token is not allowed")
    divisor = 1000.0 if milliseconds else 1.0
    start_s = float(start) / divisor
    end_s = float(end) / divisor
    if start_s < 0 or end_s < start_s:
        raise ValueError(f"Invalid word interval: {token!r} {start_s}..{end_s}")
    return {"text": token, "start_s": start_s, "end_s": end_s}


def _validate(words: list[dict[str, Any]], sentences: list[dict[str, Any]], language: str) -> None:
    if not language.strip():
        raise ValueError("Language field is required")
    previous = 0.0
    for word in words:
        if word["start_s"] < previous - 1e-9:
            raise ValueError("Word timestamps must be monotonic and non-overlapping")
        previous = word["end_s"]
    previous = 0.0
    for sentence in sentences:
        if not sentence["text"].strip():
            raise ValueError("Empty sentence is not allowed")
        if sentence["start_s"] < previous - 1e-9 or sentence["end_s"] < sentence["start_s"]:
            raise ValueError("Sentence timestamps must be monotonic and valid")
        previous = sentence["end_s"]


def _from_faster_whisper(data: dict[str, Any]) -> dict[str, Any]:
    language = str(data.get("language") or data.get("language_code") or "").strip()
    words: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []
    for segment in data.get("segments") or []:
        segment_words = [_word(item.get("word", item.get("text", "")), item["start"], item["end"]) for item in (segment.get("words") or [])]
        text = str(segment.get("text") or "").strip()
        if not text and segment_words:
            text = "".join(item["text"] for item in segment_words)
        start_s = float(segment.get("start", segment_words[0]["start_s"] if segment_words else 0))
        end_s = float(segment.get("end", segment_words[-1]["end_s"] if segment_words else start_s))
        sentences.append({"text": text, "start_s": start_s, "end_s": end_s, "words": segment_words})
        words.extend(segment_words)
    _validate(words, sentences, language)
    return {"schema_version": "1.0", "backend": "faster-whisper", "language": language, "sentences": sentences, "words": words}


def _from_funasr(data: dict[str, Any]) -> dict[str, Any]:
    language = str(data.get("language") or data.get("lang") or "").strip()
    raw_text = str(data.get("text") or "").strip()
    timestamps = data.get("timestamp") or data.get("timestamps") or []
    raw_tokens = data.get("tokens") or data.get("words") or []
    if raw_tokens and isinstance(raw_tokens[0], dict):
        words = []
        for item in raw_tokens:
            seconds = "start_s" in item or "end_s" in item
            start = item.get("start_s") if seconds else item.get("start_ms", item.get("start"))
            end = item.get("end_s") if seconds else item.get("end_ms", item.get("end"))
            words.append(_word(item.get("word", item.get("text", "")), start, end, milliseconds=not seconds))
    else:
        tokens = [str(item) for item in raw_tokens] if raw_tokens else _tokenize_funasr(raw_text, len(timestamps))
        if len(tokens) != len(timestamps):
            raise ValueError("FunASR token and timestamp counts differ")
        words = [_word(token, interval[0], interval[1], milliseconds=True) for token, interval in zip(tokens, timestamps)]

    sentences: list[dict[str, Any]] = []
    sentence_info = data.get("sentence_info") or data.get("sentences") or []
    if sentence_info:
        for item in sentence_info:
            seconds = "start_s" in item or "end_s" in item
            start = item.get("start_s") if seconds else item.get("start_ms", item.get("start"))
            end = item.get("end_s") if seconds else item.get("end_ms", item.get("end"))
            divisor = 1.0 if seconds else 1000.0
            sentence_words = [word for word in words if word["start_s"] >= float(start) / divisor - 1e-9 and word["end_s"] <= float(end) / divisor + 1e-9]
            sentences.append({"text": str(item.get("text") or "").strip(), "start_s": float(start) / divisor, "end_s": float(end) / divisor, "words": sentence_words})
    elif words:
        sentences.append({"text": raw_text or "".join(item["text"] for item in words), "start_s": words[0]["start_s"], "end_s": words[-1]["end_s"], "words": words.copy()})
    _validate(words, sentences, language)
    return {"schema_version": "1.0", "backend": "funasr", "language": language, "sentences": sentences, "words": words}


def _tokenize_funasr(text: str, expected: int) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    characters = [character for character in compact if character.strip()]
    if len(characters) == expected:
        return characters
    whitespace = [part for part in text.split() if part]
    return whitespace


def normalize_transcript(data: dict[str, Any] | list[dict[str, Any]], backend: str) -> dict[str, Any]:
    if isinstance(data, list):
        if len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError("Expected one transcript object")
        data = data[0]
    if backend == "funasr":
        return _from_funasr(data)
    if backend == "faster-whisper":
        return _from_faster_whisper(data)
    raise ValueError(f"Unsupported backend: {backend}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize saved FunASR/faster-whisper JSON; does not run or download models.")
    parser.add_argument("input", help="Saved backend JSON")
    parser.add_argument("output", help="Normalized JSON output")
    parser.add_argument("--backend", required=True, choices=("funasr", "faster-whisper"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = normalize_transcript(data, args.backend)
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "output_path": str(output), "word_count": len(result["words"]), "sentence_count": len(result["sentences"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
