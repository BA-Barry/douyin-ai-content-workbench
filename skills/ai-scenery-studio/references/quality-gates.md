# Quality gates

## G0 Contract and rights

- Exact provider, model, weight/version, license identifier, prompt hash, output path, AI-label requirement, and reference rights are recorded.
- Any unclear model license, reference right, or cost blocks generation.

## G1 Technical image

- Valid raster image; portrait 9:16 or safely crop-able; production target at least 1080×1920.
- No corruption, blank output, text, watermark, logo, celebrity, existing character, or obvious franchise element.
- Record dimensions, format, SHA-256, generation parameters, runtime, peak VRAM/RAM when available.

## G2 Semantic and artifact review

Human checks:

- One clear focal landmark and one visible world rule.
- Temporal or causal rules have one readable single-frame proof cue; prompt wording or later motion does not count as proof.
- Believable perspective, scale, light, water, reflections, architecture, vegetation, and material continuity.
- No repeated buildings, melted edges, copied textures, false lettering, nonsensical windows, or contradictory shadows.
- Not a generic purple-cyan AI fantasy wallpaper.
- Separable foreground, middle ground, and background if animation is planned.

Reject rather than hide failed outputs. Record reasons in `rejections.jsonl`.

## G3 Blind audience review

Show assets in randomized order without prompt, model, or production-effort context. Collect 1–5 scores for stop power, focal clarity, rule clarity, emotion, distinctiveness, and save/share intent. The creator keeps a veto for rights, low-age tone, values, and brand boundary, but one person's taste does not define traffic potential.

## G4 Platform experiment

After explicit publish approval, compare assets within the same account and wave using visible retention, average watch proportion, saves, shares, comments, and follows per 1,000 views. Do not infer causality from one post or use likes as a substitute for retention.
