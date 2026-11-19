# Provider compilers

## IMAGEGEN

Use for `IMAGE_STILL` or `IMAGE_SERIES`.

Compile each image as a self-contained prompt in this order:

1. aspect ratio and decisive narrative instant;
2. subject and exact blocking;
3. primary geometry, anchors, eye path, foreground/midground/background;
4. camera position, one exact focal length, perspective, and focus;
5. motivated light, palette distribution, materials, and capture texture;
6. emotional temperature, series invariants, item-specific variation;
7. negative constraints, especially unwanted typography, borders, watermarks, duplicated objects, plastic skin, and generic AI glow.

Default to native 9:16. Avoid asking the model to render long exact typography; add precise text in a deterministic layout pass when legibility matters.

## SEEDANCE_2_0

Use `seedance-prompt-zh` as the provider compiler. The installed Skill is third-party and useful for syntax, not an authoritative source for current product limits.

Compiler rules:

- Label every input by role, for example `@Image1` as the first-frame identity anchor, `@Video1` only for camera motion, and `@Audio1` only for rhythm or sound reference.
- State what to preserve and what to change. Never attach an unscoped reference.
- Use explicit timed segments for multi-shot work and describe natural-language camera motion, action, emotion, and transition per segment.
- Separate visual action, dialogue, ambience/effects, and music.
- Preserve exact dialogue and visible text in the original language.
- Mark current upload-count, duration, resolution, and realism constraints as `VERIFY_AT_SUBMISSION` unless verified from the live official interface for that run.
- Output a prepare-only task package. Generation submission remains a separate user approval.

## MINIMAX_H3

Use the official `h3-prompt-writing` Skill. Choose one official mode:

- `T2VA`: text to video with audio.
- `I2VA`: image-led first-frame generation.
- `FL2VA`: first and last frame control.
- `L2VA`: last-frame target.
- `Ref2VA`: multimodal reference generation.

For `T2VA`, `I2VA`, `FL2VA`, or `L2VA`, compile exactly three top-level fields:

1. `integrated_multimodal_description`
2. `overall_soundscape`
3. `non_diegetic_music`

Shot 1 starts without a timestamp. Every later cut begins with a timestamped marker such as `[Shot 2] At 00:03.500...`. Use stable speaker IDs such as `(S1)` and preserve exact dialogue inside the provider's dialogue markup.

For `Ref2VA`, compile exactly six sections:

1. `subject_definitions`
2. `summary`
3. `retention_analysis`
4. `detailed_description`
5. `overall_soundscape`
6. `non_diegetic_music`

Reference roles:

- `<Subject N>`: reusable identity or object.
- `<Picture N>`: a concrete frame or shot-planning anchor.
- `<Video N>`: temporal structure, continuation, editing, or motion reference.
- `<Audio N>`: a copied or referenced audio signal.

Use the official retention vocabulary in `retention_analysis`. Write provider control sections in English when the official Skill requires it, while preserving dialogue and visible text in their original language.

Official current repository documentation lists 4–15 seconds, 9:16 support, 24 fps, native stereo audio, and an up-to-2K regeneration path. Recheck live limits and cost before submission.

## FLOVA

Use the project-private **抖音导演提示词编译器** through the installed `flova` Skill when a workflow has explicitly selected Flova as its video execution environment.

Compile the approved director layer, rather than copying an existing Seedance or H3 provider prompt. The handoff must contain:

1. `generation_mode`: `TextToVideo`, `FirstFrameToVideo`, `ImagesToVideo`, `VideoInterp`, or `MultiModalToVideo`, selected from the approved asset roles.
2. `model_proposal`: preserve an explicitly selected model. Otherwise propose Seedance 2.5 for quality-oriented multimodal shots; propose MiniMax H3 only when explicitly selected or when its 2K/768p trade-off is the actual reason for the route.
3. `format`: default `9:16`; duration and resolution must be within the selected model's currently verified limits. Treat membership, credits, and live availability as `VERIFY_AT_SUBMISSION`.
4. `reference_manifest`: every runtime asset has exactly one role and uses Flova syntax: `<<<image_N>>>`, `<<<video_N>>>`, or `<<<audio_N>>>`.
5. `flova_prompt`: camera, subject, space, and sound are separated in natural language. Preserve exact dialogue and visible text in their original language.
6. `preflight_confirmation`: mode, model, duration, resolution, references, number of shots/runs, and the fact that credits may be consumed. Stop here until the user confirms.

Do not create a Flova project, upload a reference, start a run, export, or publish from this compiler step. Generation and export have separate user gates.

## PROMPT_ONLY

Keep the director package provider-neutral. Do not invent provider syntax or imply that media has been generated.
