# Provider routing

## Built-in image generation

Use the environment's built-in image-generation tool when available. Save selected project outputs into the G-drive batch workspace. If it fails, record the exact error and stop; do not silently switch to a CLI/API.

## Local model

Use only after an exact model and weight version pass the license gate and a 4GB-VRAM technical smoke test is planned.

Before any download:

1. Load `.\config\project-env.ps1`.
2. Print and verify model, Hugging Face/ModelScope, Torch, pip/uv, temporary, and output paths.
3. Record expected bytes and G-drive free space.
4. Use resumable, bounded downloads.

Store source under `projects/`, environment under `envs/`, weights under `models/`, caches under `cache/`, and outputs under `workspace/`. A code-repository license does not automatically license model weights or commercial outputs.

## Paid or external API

Require explicit user approval immediately before the first potentially charged call, including provider and budget ceiling. Never request a full API key in chat. Record whether prompts or references leave the machine.

## Fail-closed states

- `DRAFT`: batch content is not ready for a provider call.
- `BLOCKED`: required permission, license, provider, model, budget, or path proof is missing.
- `READY`: contract is valid and all external-action prerequisites are satisfied.
- `GENERATED`: output exists and its hash is recorded; this is not an aesthetic approval.
