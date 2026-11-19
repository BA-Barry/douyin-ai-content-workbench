from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
import os
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
MODES = {"human_recording", "licensed_synthetic", "authorized_self_clone"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_voice_contract(root: Path, contract_path: Path) -> dict[str, Any]:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    mode = data.get("voice_mode")
    if mode not in MODES:
        errors.append(f"unsupported voice_mode: {mode}")
    sample = _path(root, data.get("sample_path"))
    sample_hash = ""
    technical: dict[str, Any] = {}
    if not sample or not sample.exists():
        errors.append("voice sample missing")
    elif sample.suffix.lower() != ".wav":
        errors.append("voice gate currently requires a PCM WAV sample")
    else:
        sample_hash = sha256(sample)
        if data.get("sample_sha256") != sample_hash:
            errors.append("voice sample hash mismatch")
        try:
            with wave.open(str(sample), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
                channels = handle.getnchannels()
                width = handle.getsampwidth()
            duration = frames / rate if rate else 0
            technical = {
                "duration_s": round(duration, 6), "sample_rate_hz": rate,
                "channels": channels, "sample_width_bytes": width,
            }
            if not 8 <= duration <= 15:
                errors.append("voice sample duration must be 8..15 seconds")
            if rate != 48000 or channels != 1:
                errors.append("voice sample must be 48kHz mono")
        except wave.Error as exc:
            errors.append(f"invalid WAV: {exc}")

    rights = _path(root, data.get("rights_evidence_path"))
    if mode in {"licensed_synthetic", "authorized_self_clone"} and (not rights or not rights.exists()):
        errors.append("synthetic voice requires rights evidence")
    consent = _path(root, data.get("consent_evidence_path"))
    if mode == "authorized_self_clone" and (not consent or not consent.exists()):
        errors.append("voice clone requires explicit consent evidence")
    approval = _path(root, data.get("human_approval_path"))
    if not approval or not approval.exists():
        errors.append("explicit user short-sample approval missing")
    else:
        approval_data = json.loads(approval.read_text(encoding="utf-8"))
        if approval_data.get("approved") is not True or approval_data.get("approved_by") != "user":
            errors.append("short-sample approval is not an explicit user approval")
        if approval_data.get("sample_sha256") != sample_hash:
            errors.append("short-sample approval is not bound to current sample hash")
        if approval_data.get("naturalness_accepted") is not True:
            errors.append("user did not accept voice naturalness")
    return {
        "schema_version": "3.0", "contract_path": str(contract_path.resolve()),
        "voice_mode": mode, "sample_sha256": sample_hash, "technical": technical,
        "status": "PASS" if not errors else "BLOCKED", "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the 8-15 second voice sample gate")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_voice_contract(args.root.resolve(), args.contract.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

