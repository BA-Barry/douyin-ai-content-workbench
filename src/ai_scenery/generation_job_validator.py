"""Fail-closed validator for an AI scenery generation job."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[2]).expanduser().resolve().resolve()
PROVIDER_MODES = {"LOCAL", "NATIVE_TOOL", "PAID_API"}
JOB_STATUSES = {"DRAFT", "READY", "GENERATED", "BLOCKED"}
HUMAN_REVIEW = {"PENDING", "PASS", "FAIL"}
ALLOWED_REFERENCE_RIGHTS = {"OWNED", "CC0", "PUBLIC_DOMAIN", "LICENSED"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(value: str, field: str, errors: list[dict]) -> Path | None:
    if not value:
        errors.append({"code": "MISSING_PATH", "field": field})
        return None
    path = Path(value)
    if not path.is_absolute():
        errors.append({"code": "PATH_NOT_ABSOLUTE", "field": field, "value": value})
        return None
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        errors.append({"code": "PATH_OUTSIDE_PROJECT", "field": field, "value": str(resolved)})
        return None
    return resolved


def validate(job: dict) -> dict:
    errors: list[dict] = []
    for field in (
        "schema_version", "job_id", "series_id", "provider", "provider_mode",
        "model", "model_version", "model_license_id", "prompt_path",
        "prompt_sha256", "aspect_ratio", "output_path", "human_review", "status",
    ):
        if not str(job.get(field, "")).strip():
            errors.append({"code": "MISSING_VALUE", "field": field})

    provider_mode = job.get("provider_mode")
    if provider_mode not in PROVIDER_MODES:
        errors.append({"code": "INVALID_PROVIDER_MODE", "value": provider_mode})
    if job.get("status") not in JOB_STATUSES:
        errors.append({"code": "INVALID_STATUS", "value": job.get("status")})
    if job.get("human_review") not in HUMAN_REVIEW:
        errors.append({"code": "INVALID_HUMAN_REVIEW", "value": job.get("human_review")})
    if job.get("ai_label_required") is not True:
        errors.append({"code": "AI_LABEL_MUST_BE_TRUE"})

    prompt_path = project_path(str(job.get("prompt_path", "")), "prompt_path", errors)
    if prompt_path:
        if not prompt_path.is_file():
            errors.append({"code": "PROMPT_NOT_FOUND", "value": str(prompt_path)})
        elif file_sha256(prompt_path).lower() != str(job.get("prompt_sha256", "")).lower():
            errors.append({"code": "PROMPT_HASH_MISMATCH", "value": str(prompt_path)})

    output_path = project_path(str(job.get("output_path", "")), "output_path", errors)
    if output_path and job.get("status") == "GENERATED" and not output_path.is_file():
        errors.append({"code": "GENERATED_OUTPUT_NOT_FOUND", "value": str(output_path)})

    if provider_mode == "PAID_API":
        approval_path = project_path(str(job.get("budget_approval_path", "")), "budget_approval_path", errors)
        if approval_path and not approval_path.is_file():
            errors.append({"code": "BUDGET_APPROVAL_NOT_FOUND", "value": str(approval_path)})

    references = job.get("reference_assets", [])
    if not isinstance(references, list):
        errors.append({"code": "REFERENCES_NOT_LIST"})
    else:
        for index, reference in enumerate(references):
            if not isinstance(reference, dict):
                errors.append({"code": "REFERENCE_NOT_OBJECT", "index": index})
                continue
            rights = reference.get("rights_status")
            if rights not in ALLOWED_REFERENCE_RIGHTS:
                errors.append({"code": "REFERENCE_RIGHTS_BLOCKED", "index": index, "value": rights})
            local_path = project_path(str(reference.get("local_path", "")), f"reference_assets[{index}].local_path", errors)
            if local_path and not local_path.is_file():
                errors.append({"code": "REFERENCE_NOT_FOUND", "index": index, "value": str(local_path)})

    return {
        "schema_version": "1.0",
        "job_id": job.get("job_id"),
        "job_status": job.get("status"),
        "scope_note": "PASS means the job contract is valid; it does not override a BLOCKED job status.",
        "error_count": len(errors),
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    result = validate(job)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
