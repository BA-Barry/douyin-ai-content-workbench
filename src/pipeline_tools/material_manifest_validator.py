"""Validate the frozen material manifest contract without mutating assets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TEMPLATE = Path(__file__).resolve().parents[2] / "workflow" / "templates" / "MATERIAL_MANIFEST_TEMPLATE.csv"
REQUIRED_COLUMNS = tuple(next(csv.reader(TEMPLATE.open("r", encoding="utf-8-sig", newline=""))))
REQUIRED_VALUES = ("asset_id", "local_path", "sha256", "media_type", "purpose", "ai_generated", "human_review", "status")
TRUE_VALUES = {"1", "true", "yes", "y", "是"}
FALSE_VALUES = {"0", "false", "no", "n", "否"}
APPROVED_VALUES = {"approved", "pass", "passed", "yes", "true", "通过", "已通过"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ai_value(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def validate_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path).resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checked = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        missing_columns = [field for field in REQUIRED_COLUMNS if field not in headers]
        extra_columns = [field for field in headers if field not in REQUIRED_COLUMNS]
        if missing_columns:
            errors.append({"row": 1, "code": "MISSING_COLUMNS", "fields": missing_columns})
        if extra_columns:
            warnings.append({"row": 1, "code": "EXTRA_COLUMNS", "fields": extra_columns})
        for row_number, row in enumerate(reader, start=2):
            checked += 1
            missing_values = [field for field in REQUIRED_VALUES if not (row.get(field) or "").strip()]
            if missing_values:
                errors.append({"row": row_number, "code": "MISSING_VALUES", "fields": missing_values})
            local_text = (row.get("local_path") or "").strip()
            local = Path(local_text) if local_text else None
            if local is not None and not local.is_absolute():
                errors.append({"row": row_number, "code": "PATH_NOT_ABSOLUTE", "field": "local_path", "value": local_text})
            elif local is not None and not local.is_file():
                errors.append({"row": row_number, "code": "FILE_NOT_FOUND", "field": "local_path", "value": local_text})
            elif local is not None:
                expected = (row.get("sha256") or "").strip().lower()
                actual = _sha256(local)
                if expected != actual:
                    errors.append({"row": row_number, "code": "SHA256_MISMATCH", "expected": expected, "actual": actual})

            status = (row.get("status") or "").strip().upper()
            if status == "BLOCKED":
                errors.append({"row": row_number, "code": "RIGHTS_BLOCKED", "field": "status"})
            if not status:
                errors.append({"row": row_number, "code": "RIGHTS_STATUS_MISSING", "field": "status"})

            ai_generated = _ai_value(row.get("ai_generated") or "")
            if ai_generated is None:
                errors.append({"row": row_number, "code": "INVALID_AI_GENERATED", "field": "ai_generated"})
            elif ai_generated:
                ai_missing = [field for field in ("ai_model", "model_version", "prompt_hash") if not (row.get(field) or "").strip()]
                if ai_missing:
                    errors.append({"row": row_number, "code": "AI_PROVENANCE_MISSING", "fields": ai_missing})
                if (row.get("human_review") or "").strip().lower() not in APPROVED_VALUES:
                    errors.append({"row": row_number, "code": "AI_HUMAN_REVIEW_NOT_APPROVED", "field": "human_review"})
            elif any((row.get(field) or "").strip() for field in ("ai_model", "model_version", "prompt_hash")):
                warnings.append({"row": row_number, "code": "AI_FIELDS_PRESENT_WHEN_NOT_GENERATED"})

    return {
        "schema_version": "1.0",
        "manifest_path": str(path),
        "rows_checked": checked,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate material manifest headers, hashes, rights and AI review fields.")
    parser.add_argument("manifest", help="CSV manifest path")
    parser.add_argument("--output", help="Optional validation JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_manifest(args.manifest)
    except Exception as exc:
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
