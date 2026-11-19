---
name: ai-scenery-studio
description: Plan, prompt, generate, and quality-gate original vertical AI scenery batches for short-video traffic tests. Use for AI landscapes, impossible worlds, adult emotional habitats, or parallel-world choices; do not use for copying an artist/IP, bypassing model licenses, publishing, or paid generation without approval.
---

# AI Scenery Studio

Produce small, comparable batches of original 9:16 scenery assets and preserve every prompt, provider decision, output hash, and review result for reuse.

## Required project inputs

When used inside `G:\抖音视频`, read these first:

- `workflow/MASTER_WORKFLOW.md`
- `workflow/ACCOUNT_POSITIONING_CARD.md`
- the current content's approved `brief.md`, `hypothesis_card.md`, `production/route_plan.json`, and `production/shot_list.csv`
- `workflow/styles/ai-scenery-v1.visual-style.md`
- `research/account_reset/ai_scenery_positioning/AESTHETIC_EVAL_PROTOCOL.md`
- `workflow/AI_SCENERY_TOOLCHAIN.md`
- `config/project-env.ps1` before any command that can download a package, model, browser, or dependency

For another project, obtain equivalent style, storage, provider-rights, and QA rules instead of assuming these paths.

## Workflow

1. Define one batch hypothesis and the single comparison variable. Prefer 3–6 assets; do not call a large uncontrolled gallery a test.
2. Create a batch-plan JSON following [the prompt and batch schema](references/prompt-framework.md).
3. Run `scripts/prepare_batch.py` to produce immutable prompt files, generation-job contracts, hashes, and a batch manifest.
4. Select a provider using [provider routing](references/provider-routing.md). A provider/model/weight without a verified license remains `BLOCKED`.
5. Generate one technical image first. Only expand the batch after the provider, disk path, and output format pass.
6. Save project images under the batch workspace; never leave project assets only in a tool default directory or system drive.
7. Apply [quality gates](references/quality-gates.md). Machine QA does not approve aesthetics, world-rule clarity, similarity, or publication.
8. Record rejected outputs and reasons. Do not silently replace failed generations and report only the winner.

Inside `G:\抖音视频`, the account-level route contract overrides the generic batch size: `IMAGE_CAROUSEL` requires exactly six approved 1080×1920 final images. Do not begin generation while the registry has not reached `BRIEF_APPROVED`, and do not change the frozen hypothesis, route, shot order, or acceptance sentence during production. Return a route-aware `production_manifest.json`; do not invent a video compatibility field for a carousel.

For Codex-native scenery generation and rapid first-post work, read [Codex scenery recipes](references/codex-scenery-recipes.md). Use the proven `baoyu-image-gen / codex-cli` route when the direct in-thread image tool returns a transport error and the project preference explicitly pins `codex-cli`.

When the user wants a repeatable multi-image series rather than a one-off landscape, read [series seed library](references/series-seed-library.md). Treat its entries as recombinable world-rule patterns, not fixed subjects to clone.

For romance, reunion, long-distance relationships, Qixi, graduation, or homecoming themes, read [distance-disappears festival series](references/distance-disappears-festival-series.md). Use it to translate a relationship into visible spatial evidence without relying on characters, hearts, red thread, or festival-poster clichés.

For photoreal impossible-world batches and seasonal romantic landscapes, read [realistic impossible-world and festival modes](references/realistic-impossible-world-and-festival-modes.md). Use this when the scene must first read as a place a tired adult could enter, then reveal one clear physical exception; use the seasonal mode for atmosphere and paired life traces without showing couples.

## Fast first-post mode

Outside a project with a frozen route contract, a user may explicitly approve a one-image fast test. Inside `G:\抖音视频`, do not use this shortcut for the current six-image account experiment; finish six approved images or stop the batch. This mode never grants permission to upload or click Publish.

## Prompt invariant

Each image starts from believable geography, material, weather, and human scale, then adds exactly one visible impossible rule. A viewer should be able to say both “where this is” and “what rule governs it” in one sentence.

For any rule involving movement, appearance, disappearance, time, threshold, or transformation, define one `static_proof_cue`: a physical trace, boundary, before/after residue, continuous path, or mid-transformation state that makes the rule visible in a single frame. Do not rely on a caption, prompt explanation, or later animation to prove the still image's rule. If a clean single-frame proof cannot be designed, reframe the rule before generation.

Generated images contain no text, logo, watermark, named artist imitation, existing character, celebrity likeness, or recognizable franchise design. Add titles and AI disclosure later in deterministic post-production.

## Batch stopping rules

- Stop before download when cache/model/temp paths are not demonstrably on the approved project drive.
- Stop before generation when model/weight license, provider cost, or reference-image rights are unclear.
- Stop after the first technical image when generation fails, exceeds resource limits, or produces an unusable format.
- Stop before animation when the image lacks separable foreground/middle/background or fails human artifact review.
- Never publish, upload, buy credits, or approve content from this skill.
- For `G:\抖音视频`, preserve prompt files, prompt hashes, provider/model identity, raw outputs, rejects, replacements, normalization report, final hashes, contact sheet, material manifest, and machine QA under `content/<video_id>/production/`.

## Commands

Prepare a batch without generating images:

```powershell
& 'G:\抖音视频\envs\content\Scripts\python.exe' `
  'G:\抖音视频\skills\ai-scenery-studio\scripts\prepare_batch.py' `
  --plan 'G:\抖音视频\workspace\ai_scenery_batch_01_20260818\batch_plan.json' `
  --output-dir 'G:\抖音视频\workspace\ai_scenery_batch_01_20260818\prepared'
```

Then validate each generated job with the project validator before calling a provider.

## Deliverables

Return the batch plan, exact prompt files, generation jobs, provider/model/weight identity, output paths and hashes, rejected-output log, QA results, and human-review status. Clearly distinguish `contract PASS`, `generation PASS`, `machine QA PASS`, and `human review PASS`.
