---
name: douyin-media-orchestrator
description: Automatically select and coordinate the relevant image, video, motion, voice, caption, QA, and export Skills for a Douyin content project. Use for route planning or executing an approved production request; do not require the user to pick individual Skills.
license: Project-authored orchestration guidance; component licenses remain separate.
---

# Douyin media orchestrator

Act as the production router for `.`. The user chooses the content goal and approves the brief; select every relevant Skill automatically. Never call every installed Skill indiscriminately.

This Skill runs inside a Codex task. The local web workbench can create plans and queues but cannot itself execute instruction-only Skills.

## Start from project truth

Read `workflow/MASTER_WORKFLOW.md`, `workflow/TASK_HANDOFF_PROTOCOL.md`, `data/content_registry.csv`, the selected project's approved `brief.md`, and its current production evidence. Determine the route from the registry and brief. If they conflict, stop and request a route decision.

## Plan before execution

Write `content/<video_id>/production/skill_plan.json` using [references/skill-plan-schema.md](references/skill-plan-schema.md). The plan must show:

- selected route and why;
- ordered phases and Skills;
- inputs, outputs, required approvals, cost/network/upload boundaries;
- optional steps that were deliberately omitted;
- current executor status: `PLANNED`, `READY_FOR_CODEX`, `BLOCKED`, or `COMPLETE`.

Use [references/routing-matrix.md](references/routing-matrix.md) to select capabilities. A style Skill is selected from the brief's visual language, not from a manual picker.

## Execution rules

- `IMAGE_CAROUSEL`: use Codex image generation plus exactly one primary visual-style Skill and `douyin-wallpaper-export`; add a secondary style Skill only when the brief explicitly mixes systems.
- `ATMOSPHERE_VIDEO`: use Seedance prompt planning for generated shots, then motion language, Remotion/video-use post-production, technical QA, and optional caption/audio steps.
- `NARRATED_EXPLAINER`: require fact/script evidence, voice sample approval, caption pipeline, compositing, and audio/video QA.
- Record each actual Skill invocation and artifact. If a planned Skill is unavailable, replace it only with an approved equivalent and update the plan.
- Do not mark a Skill complete merely because its instructions are installed.
- Paid APIs, private-media uploads, voice cloning, platform upload, and publishing retain their existing human gates.
- The workbench may plan, queue, display, and audit. Actual Skill execution requires a Codex task or scheduled task with access to the project.

Finish only when project artifacts prove each completed step and the workflow audit passes.
