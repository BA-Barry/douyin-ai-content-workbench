# Prompt and batch framework

## Contents

- Batch-plan fields
- Series modes
- Prompt assembly order
- Controlled comparison

## Batch-plan fields

The plan is UTF-8 JSON with:

- `schema_version`, `batch_id`, `project_root`, `style_file`
- `hypothesis`: one testable sentence
- `single_test_variable`: one primary comparison variable
- `provider`: provider/model/weight contract; unknown fields must say `PENDING`, never be invented
- `defaults`: aspect ratio, palette, common constraints, avoid list
- `items`: 3–6 distinct assets

Each item requires:

- `id`, `series_id`, `primary_request`
- `static_proof_cue`: the one physical detail that proves the impossible rule in a single frame
- `scene_backdrop`, `subject`, `style_medium`
- `composition_framing`, `lighting_mood`, `materials_textures`
- `output_intent`

## Series modes

### nonexistent-china

Use a recognizable Chinese geographic or contemporary living base plus one impossible environmental rule. Cultural details must be coherent rather than decorative.

### adult-habitat

Turn one adult pressure—commuting, notification overload, noise, overtime, lack of privacy—into a spatial answer. The space must communicate the emotion before captions.

### parallel-choice

Offer two equally plausible worlds with a real trade-off. Do not make one side obviously good and the other apocalyptic. Use continuous geography or a motivated reveal rather than a generic split-screen graphic.

## Prompt assembly order

Use labeled sections in this order:

1. Use case and asset type
2. Primary request and the one impossible rule
3. Static single-frame proof
4. Scene/backdrop
5. Subject
6. Style/medium
7. Composition/framing
8. Lighting/mood
9. Color palette
10. Materials/textures
11. Constraints
12. Avoid
13. Output intent

Do not ask the image model to render Chinese titles. Do not add an artist, franchise, brand palette, character, giant moon, floating island, or narrative prop unless the batch plan explicitly requires it and rights are clear.

For a temporal or causal rule, words such as “moves”, “appears”, “only when”, or “turns into” are not sufficient proof. Specify one visually economical trace: for example, an empty former foundation aligned behind the current location, a material caught halfway through transformation, or a continuous boundary shared by two physical states. The proof must not introduce a second impossible rule.

## Controlled comparison

Within one wave, keep provider, model, weight, seed policy, resolution, inference settings, aspect ratio, caption treatment, duration, and audio constant. Change the declared variable only. If generation randomness prevents a clean comparison, record it instead of claiming causality.

For ready-to-use patterns and the validated Codex prompt shape, read [Codex scenery recipes](codex-scenery-recipes.md).
