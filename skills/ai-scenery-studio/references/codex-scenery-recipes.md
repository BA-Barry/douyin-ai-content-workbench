# Codex scenery prompt recipes

Read this reference when generating original scenery through Codex or preparing a fast first post.

## Validated route

- Provider: `baoyu-image-gen / codex-cli`
- Authentication: current Codex/ChatGPT login; no `OPENAI_API_KEY`
- Aspect: `9:16`; one image per call; concurrency 1
- Project preferences: `.\.baoyu-skills\baoyu-image-gen\EXTEND.md`
- Runtime: use the configured project cache; on Windows load `config/project-env.ps1` first.
- Pixel dimensions are selected by Codex. Treat `--quality` and `--size` as ignored for this provider; normalize only after human approval.

The direct in-thread image tool returning an immediate HTTP error is a transport failure. Record it, then use this route only when project preferences already authorize `codex-cli`; do not silently switch to an external paid provider.

## Reusable prompt skeleton

Write the actual prompt in English unless the provider demonstrates better Chinese adherence.

```text
Create an original vertical 9:16 cinematic impossible-world landscape for adult short-video viewers.

PRIMARY SCENE
[Recognizable real geography, weather, architecture, and human scale]. Exactly one impossible rule: [one short rule].

STATIC PROOF — MUST BE VISIBLE IN THIS SINGLE FRAME
[One continuous trace, empty former position, threshold, residue, or mid-transformation boundary]. The viewer must understand the rule without captions or animation.

COMPOSITION
One focal landmark. Strong foreground, middle ground, and background. Keep the right interaction rail and upper/lower text-safe zones visually quiet. Use a physically plausible camera and perspective.

LIGHT AND MATERIAL
Naturalistic atmospheric light; mineral charcoal, mist jade, warm stone, pale daylight, and one sparse amber accent. Preserve weathered stone, damp wood, metal, water, vegetation, fog depth, and small imperfections.

MOOD
Adult, contemplative, slightly uncanny, emotionally restorative; never childish, game-like, or generic fantasy wallpaper.

AVOID
No text, letters, symbols, logo, watermark, artist imitation, franchise, celebrity, human face, giant moon, decorative floating island, purple-cyan neon, excessive bloom, random particles, repeated buildings, melted edges, copied textures, impossible perspective, false reflections, or contradictory shadows.

OUTPUT INTENT
The viewer should be able to say both where this is and what impossible rule governs it in one sentence.
```

## Static-proof patterns

Use exactly one pattern per image.

- Migration: empty former foundations aligned with a continuous worn route leading to the current intact settlement.
- Transformation: one material caught halfway across a single continuous boundary; do not show two unrelated objects.
- Appearance: one coherent threshold whose far side is physically empty and near side contains the appearing structure.
- Time split: the same continuous geography and landmark crosses both time states; no graphic split-screen border.
- Noise/notification release: physical traces visibly leave one ordinary interior through a single opening; no readable device UI.
- Choice: both worlds share one continuous route or coastline and remain equally desirable; avoid “good versus apocalypse.”

If a temporal rule cannot be proven in a still image, rewrite the world rule before generation. Do not rely on the caption to repair an ambiguous image.

## Proven A01 pattern

The successful first candidate used a believable Taihang sunset town plus one rule: the intact town follows the last light. The crucial correction was explicit static proof—empty former stone foundations and one worn terrace road aligned behind the town. This made the rule more legible than prompts that only said the town “moves.”

Reuse the structure, not the subject. For a new location, replace geography, settlement materials, rule, and proof cue while retaining the constraint order.

## Fast-post package

For a user-approved single image:

1. Normalize to `1080×1920` after approval without generative alteration.
2. Run machine QA and record hash.
3. Keep the image free of title text for the first scenery test.
4. Use one sentence describing the rule, one low-friction question, and `画面由AI生成` in the post text.
5. Upload only in `prepare-only`; clicking Publish always requires immediate user confirmation.
