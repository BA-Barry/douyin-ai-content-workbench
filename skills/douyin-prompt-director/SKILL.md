---
name: douyin-prompt-director
description: Build a provider-agnostic, auditable prompt package for Douyin image or video production, then compile it for exactly one target such as Codex imagegen, Seedance 2.0, or MiniMax H3. Use for image prompts, image series, single-shot video, multi-shot video, reference-based video, explainers, and workbench production planning.
---

# Douyin Prompt Director

Create the creative and technical contract before invoking a generation provider. This Skill writes prompts and plans; it does not submit generation jobs, spend credits, upload private assets, or publish.

## Required references

- Read `references/output-contract.md` for every task.
- Read `references/provider-compilers.md` only for the selected provider.
- Read `references/quality-gates.md` before delivery.

## Core rule

Separate two layers:

1. **Director layer** — define what the audience should feel or learn, visual DNA, shot logic, continuity, text, sound, and exclusions.
2. **Provider compiler** — translate the approved director layer into exactly one provider's syntax.

Never concatenate multiple provider Skills. Use Seedance or H3 for one generation task, not both. Other Skills may contribute specialist plans, but one coherent prompt package remains the source of truth.

## Output modes

Choose exactly one:

- `IMAGE_STILL`: one decisive still.
- `IMAGE_SERIES`: a coherent carousel with controlled variation.
- `VIDEO_SINGLE_SHOT`: one continuous movement without hidden cuts.
- `VIDEO_MULTI_SHOT`: a timed sequence with explicit cuts.
- `VIDEO_REFERENCE_EDIT`: reference-led continuation, replacement, transfer, or controlled remix.
- `EXPLAINER_PACKAGE`: evidence-led narration, visual metaphor, captions, and supporting shots.

Default to 9:16 for Douyin. Use 2.35:1 only when the user explicitly requests a cinematic keyframe or film-frame artifact; never force that ratio onto a Douyin post.

## Workflow

1. **Parse the brief**
   - Lock the audience payoff, emotion or learning objective, duration/count, aspect ratio, visible text, dialogue language, facts that must remain exact, and unacceptable outcomes.
   - Ask only when a missing answer changes the concept materially. Otherwise state a reversible assumption.

2. **Choose the output mode**
   - Avoid treating a still-image prompt as a video prompt. Motion requires state change over time.
   - For a series, define one invariant system and a variation axis for every item.

3. **Build the asset-role manifest**
   - Give each reference an ID, type, intended role, rights/status, and required retention strength.
   - Do not upload or submit assets at this stage.

4. **Lock the visual DNA**
   - Composition and blocking.
   - Camera position, one exact full-frame-equivalent focal length per shot, focus, and movement.
   - Motivated light.
   - Palette, contrast, and capture texture.
   - Production design, materials, wardrobe, and controlled wear.
   - Temporal rhythm or series variation rhythm.
   - Emotional distance and performance behavior.
   - Prefer visible, measurable choices over adjectives such as “cinematic masterpiece.”

5. **Write the beat and shot ledger**
   - Every shot has one purpose, one principal action, one emotional or informational change, a start/end time, and an exit condition.
   - Use one primary composition geometry and at most one supporting geometry.
   - Define primary anchor, secondary clue, eye path, negative space, foreground/midground/background jobs, and safe zones.
   - For dialogue, use stable speaker IDs and preserve the requested words exactly.

6. **Lock continuity**
   - Freeze identity, wardrobe, props, geography, time/weather, screen direction, light direction, and scene-specific texture.
   - State which properties may vary. Do not leave a model to guess.

7. **Design sound separately**
   - Separate dialogue, diegetic ambience/effects, and non-diegetic music.
   - Do not describe sound inside the visual paragraph and assume the provider will infer timing.

8. **Select one provider compiler**
   - `IMAGEGEN`: stills and image series using built-in image generation.
   - `SEEDANCE_2_0`: timed multimodal video tasks using explicit `@` reference roles.
   - `MINIMAX_H3`: official H3 base or reference mode formats.
   - `FLOVA`: a prepare-only handoff for the project's private Flova Skill. It translates the approved director package into Flova's model, duration, resolution, and `<<<reference>>>` grammar; it never starts a generation run.
   - `PROMPT_ONLY`: provider-neutral delivery when no generator is chosen.
   - Selection does not authorize paid generation or private-asset upload.

9. **Write both durable outputs**
   - `production/prompt_package.md` for human review.
   - `production/prompt_package.json` for the workbench and downstream agents.
   - Follow the exact contract in `references/output-contract.md`.

10. **Run quality gates**
    - Check contradiction, overload, temporal feasibility, continuity, reference roles, exact text, model syntax, originality, and mobile readability.
    - Stop at `WAITING_PROMPT_APPROVAL` until the user approves the prompt package. Generation is a separate state.

## Specialist Skill routing

- Use `cinematic-director-frame` in prompt-only mode when the request needs strong cinematic frame grammar, precise lens/light/material decisions, or a film-frame keyframe. Translate its seven-axis Director DNA into this package; adapt the ratio to 9:16 unless 2.35:1 is explicitly requested.
- Use a single installed wallpaper/style Skill for an image series when its domain matches. Do not stack multiple visual-style Skills merely because they are installed.
- Use `hyperframes-motion-language` after the shot ledger for motion grammar and cut continuity.
- Use `seedance-prompt-zh` only when `provider_target` is `SEEDANCE_2_0`.
- Use `h3-prompt-writing` only when `provider_target` is `MINIMAX_H3`.
- Use the local `flova` Skill and the private **抖音导演提示词编译器** only when `provider_target` is `FLOVA`. Do not convert a Seedance `@Image` task or an H3 sectioned task by copy-and-paste: compile the director layer again using Flova reference markers.
- Use Remotion, captions, voice, sound, and editing Skills after the provider prompt and assets exist.

## Refusal and safety boundaries

- Do not invent product facts, research findings, quotations, or source provenance.
- Do not clone a person's voice or likeness without authorization.
- Do not recreate recognizable protected characters, signature frames, or a living creator's identity. Translate high-level craft into original visual decisions.
- Do not claim a prompt has generated media.
- Do not submit paid APIs, upload assets, or publish without the relevant approval gate.

## Return format

Return:

1. selected output mode and provider target;
2. a short director rationale;
3. the human-readable prompt package path;
4. the machine-readable prompt package path;
5. unresolved decisions and the next approval gate.
