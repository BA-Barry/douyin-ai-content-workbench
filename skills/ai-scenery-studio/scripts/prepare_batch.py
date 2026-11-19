"""Prepare immutable prompts and generation-job contracts without generating images."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


REQUIRED_ITEM_FIELDS = (
    "id",
    "series_id",
    "primary_request",
    "static_proof_cue",
    "scene_backdrop",
    "subject",
    "style_medium",
    "composition_framing",
    "lighting_mood",
    "materials_textures",
    "output_intent",
)

PROVIDER_IDENTITY_FIELDS = (
    "provider",
    "provider_mode",
    "model",
    "model_version",
    "model_license_id",
)

VALID_PROVIDER_STATUSES = {"DRAFT", "BLOCKED", "READY", "GENERATED"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes project root: {resolved}")
    return resolved


def require_fields(payload: dict, fields: tuple[str, ...], label: str) -> None:
    missing = [name for name in fields if not str(payload.get(name, "")).strip()]
    if missing:
        raise ValueError(f"{label} missing fields: {', '.join(missing)}")


def require_safe_item_id(item_id: str, label: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", item_id):
        raise ValueError(f"{label} id must be a safe ASCII filename token")
    if item_id.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{label} id uses a reserved Windows filename")


def prompt_text(item: dict, defaults: dict) -> str:
    common_constraints = "; ".join(defaults.get("common_constraints", []))
    avoid = "; ".join(defaults.get("avoid", []))
    return "\n".join(
        (
            "Use case: stylized-concept",
            f"Asset type: {defaults['asset_type']}",
            f"Primary request: {item['primary_request']}",
            f"Static single-frame proof: {item['static_proof_cue']}",
            f"Scene/backdrop: {item['scene_backdrop']}",
            f"Subject: {item['subject']}",
            f"Style/medium: {item['style_medium']}",
            f"Composition/framing: {item['composition_framing']}",
            f"Lighting/mood: {item['lighting_mood']}",
            f"Color palette: {defaults['color_palette']}",
            f"Materials/textures: {item['materials_textures']}",
            f"Constraints: {common_constraints}",
            f"Avoid: {avoid}",
            f"Output intent: {item['output_intent']}",
            "",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    require_fields(
        plan,
        ("schema_version", "batch_id", "project_root", "style_file", "hypothesis", "single_test_variable"),
        "plan",
    )
    root = Path(plan["project_root"]).resolve()
    plan_path = inside(args.plan, root)
    output_dir = inside(args.output_dir, root)
    style_path = inside(Path(plan["style_file"]), root)
    if not style_path.is_file():
        raise FileNotFoundError(style_path)
    provider = plan.get("provider", {})
    require_fields(
        provider,
        PROVIDER_IDENTITY_FIELDS + ("status",),
        "provider",
    )
    provider_status = str(provider["status"])
    if provider_status not in VALID_PROVIDER_STATUSES:
        raise ValueError(f"provider status must be one of: {', '.join(sorted(VALID_PROVIDER_STATUSES))}")
    if any(str(provider[field]).strip().upper() == "PENDING" for field in PROVIDER_IDENTITY_FIELDS):
        if provider_status != "BLOCKED":
            raise ValueError("provider identity contains PENDING fields, so status must be BLOCKED")
    defaults = plan.get("defaults", {})
    require_fields(defaults, ("asset_type", "aspect_ratio", "color_palette"), "defaults")
    items = plan.get("items")
    if not isinstance(items, list) or not 3 <= len(items) <= 6:
        raise ValueError("items must contain 3 to 6 assets")
    for index, item in enumerate(items, start=1):
        require_fields(item, REQUIRED_ITEM_FIELDS, f"item[{index}]")
        require_safe_item_id(str(item["id"]), f"item[{index}]")
    ids = [str(item["id"]) for item in items]
    if len(ids) != len({item_id.casefold() for item_id in ids}):
        raise ValueError("item ids must be unique")

    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty; prepared contracts are immutable: {output_dir}")

    prompt_dir = output_dir / "prompts"
    job_dir = output_dir / "jobs"
    image_dir = output_dir / "images"
    for directory in (prompt_dir, job_dir, image_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_items = []
    for index, item in enumerate(items, start=1):
        prompt_path = prompt_dir / f"{item['id']}.md"
        prompt_path.write_text(prompt_text(item, defaults), encoding="utf-8", newline="\n")
        prompt_hash = sha256(prompt_path)
        output_path = image_dir / f"{item['id']}.png"
        job = {
            "schema_version": "1.0",
            "job_id": f"{plan['batch_id']}-{item['id']}",
            "series_id": item["series_id"],
            "provider": provider["provider"],
            "provider_mode": provider["provider_mode"],
            "model": provider["model"],
            "model_version": provider["model_version"],
            "model_license_id": provider["model_license_id"],
            "prompt_path": str(prompt_path.resolve()),
            "prompt_sha256": prompt_hash,
            "style_path": str(style_path),
            "style_sha256": sha256(style_path),
            "aspect_ratio": defaults["aspect_ratio"],
            "output_path": str(output_path.resolve()),
            "human_review": "PENDING",
            "status": provider["status"],
            "ai_label_required": True,
            "reference_assets": [],
            "budget_approval_path": provider.get("budget_approval_path", ""),
            "seed": provider.get("seed"),
            "notes": provider.get("notes", ""),
        }
        job_path = job_dir / f"{item['id']}.json"
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_items.append(
            {
                "id": item["id"],
                "series_id": item["series_id"],
                "prompt_path": str(prompt_path.resolve()),
                "prompt_sha256": prompt_hash,
                "job_path": str(job_path.resolve()),
                "job_sha256": sha256(job_path),
                "output_path": str(output_path.resolve()),
                "status": provider["status"],
            }
        )

    manifest = {
        "schema_version": "1.0",
        "batch_id": plan["batch_id"],
        "plan_path": str(plan_path),
        "plan_sha256": sha256(plan_path),
        "style_path": str(style_path),
        "style_sha256": sha256(style_path),
        "hypothesis": plan["hypothesis"],
        "single_test_variable": plan["single_test_variable"],
        "provider_status": provider["status"],
        "item_count": len(manifest_items),
        "items": manifest_items,
    }
    manifest_path = output_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "manifest": str(manifest_path), "items": len(items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
