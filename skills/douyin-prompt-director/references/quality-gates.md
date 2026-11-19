# Prompt quality gates

## Universal

- One audience payoff is clear within the first visual beat.
- Every adjective maps to visible staging, light, material, movement, sound, or text.
- One shot has one principal action; impossible simultaneous actions are removed.
- Time allocations sum to the requested duration and allow the described movement to finish.
- There is no contradiction between lens, camera distance, focus, composition, light, or weather.
- The output contains one provider target and one compiled provider prompt.
- All exact dialogue, quotations, facts, UI labels, and visible text remain exact and sourced.
- References have explicit roles and rights status.
- Avoid lists are scene-specific, not a generic keyword dump.

## Image still or series

- Native aspect ratio is 9:16 unless explicitly overridden.
- The primary subject and focal hierarchy survive mobile thumbnail viewing.
- One exact focal length is used per image.
- Series invariants are stable while scene, crop, camera height, weather, or action varies deliberately.
- No repeated template placement, duplicated sticker set, accidental border, watermark, or illegible model-rendered paragraph.

## Video

- Identity, wardrobe, props, geography, screen direction, and light direction have continuity locks.
- Camera movement has direction, amplitude, speed, and a motivated endpoint.
- Cut points follow state changes, beats, or intentional contrast.
- Dialogue, ambience/effects, and music are separated.
- Lip movement is requested only when exact spoken dialogue exists.
- Reference video is used for an explicit role, not as a vague style sample.

## Failure conditions

Return `FAIL` and revise before approval when:

- the core point or emotional transition is unclear;
- the plan is a slideshow disguised as video;
- there are too many actions, aesthetics, lenses, or color systems in one shot;
- a requested text block cannot remain readable on a phone;
- provider syntax contradicts the selected provider mode;
- an asset's rights or role is unknown and external upload would be required;
- the prompt copies a recognizable protected frame, character, actor, or creator identity.
