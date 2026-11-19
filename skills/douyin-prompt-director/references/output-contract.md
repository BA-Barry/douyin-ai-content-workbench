# Prompt package output contract

Write both files inside the selected content project:

- `production/prompt_package.md`: readable brief, visual DNA, shot/series ledger, provider prompt, avoid list, QA result, and approval status.
- `production/prompt_package.json`: the machine-readable source of truth.

Minimum JSON shape:

```json
{
  "schema_version": "1.0",
  "video_id": "<project id>",
  "media_kind": "IMAGE|VIDEO",
  "output_mode": "IMAGE_STILL|IMAGE_SERIES|VIDEO_SINGLE_SHOT|VIDEO_MULTI_SHOT|VIDEO_REFERENCE_EDIT|EXPLAINER_PACKAGE",
  "aspect_ratio": "9:16",
  "duration_seconds": 0,
  "item_count": 1,
  "creative_intent": "",
  "audience_payoff": "",
  "visual_dna": {
    "composition_blocking": "",
    "camera_lens_focus": "",
    "motivated_light": "",
    "palette_texture": "",
    "production_design": "",
    "movement_rhythm": "",
    "emotional_distance": ""
  },
  "asset_roles": [
    {
      "id": "Image1",
      "type": "image|video|audio",
      "role": "identity|first_frame|last_frame|camera_reference|motion_reference|audio_copy|style_reference",
      "rights_status": "user_owned|licensed|public_critique_only|blocked|unknown",
      "retention": "full|partial|attribute|weak",
      "path_or_label": ""
    }
  ],
  "continuity_locks": [""],
  "shots": [
    {
      "shot_id": "S01",
      "start_s": 0.0,
      "end_s": 4.0,
      "purpose": "",
      "subject_action": "",
      "composition": "",
      "camera": "",
      "lens_focus": "",
      "lighting": "",
      "palette_material": "",
      "dialogue_visible_text": "",
      "soundscape": "",
      "transition": "",
      "reference_ids": [],
      "avoid": []
    }
  ],
  "provider_target": "IMAGEGEN|SEEDANCE_2_0|MINIMAX_H3|FLOVA|PROMPT_ONLY",
  "provider_mode": "",
  "provider_prompt": "",
  "negative_constraints": [],
  "qa_gates": {
    "contradiction": "PASS|FAIL",
    "continuity": "PASS|FAIL|NA",
    "timing": "PASS|FAIL|NA",
    "reference_roles": "PASS|FAIL|NA",
    "exact_text": "PASS|FAIL|NA",
    "mobile_readability": "PASS|FAIL|NA"
  },
  "approvals_required": ["prompt_package_approval"],
  "status": "WAITING_PROMPT_APPROVAL"
}
```

Rules:

- `duration_seconds` is `0` for still images.
- `shots` may represent items in an image series; use one row per deliverable image.
- Preserve exact dialogue and visible text. Do not silently translate them.
- `provider_prompt` contains only the selected compiler output, never multiple competing prompts.
- Record unknown rights as `unknown` and block external upload until resolved.
- With `FLOVA`, `provider_prompt` is a prepare-only Flova handoff. It must name the proposed generation mode, model, duration, resolution, each `<<<image_N>>>` / `<<<video_N>>>` / `<<<audio_N>>>` role, and the exact pre-generation user confirmation required. It is not a submitted Flova run.
