# Skill plan schema

Minimum shape:

```json
{
  "schema_version": "1.1",
  "video_id": "<id>",
  "route": "IMAGE_CAROUSEL",
  "created_at": "ISO-8601",
  "planner": "douyin-media-orchestrator",
  "status": "READY_FOR_CODEX",
  "provider_target": "IMAGEGEN",
  "provider_mode": "IMAGE",
  "prompt_compiler": "imagegen",
  "provider_selection_reason": "approved route and brief signals",
  "selected_visual_skill": "ai-scenery-studio",
  "selection_reason": "brief signals",
  "steps": [
    {
      "sequence": 1,
      "phase": "visual_contract",
      "skill": "ai-scenery-studio",
      "purpose": "define prompts and acceptance rules",
      "required": true,
      "execution": "codex_skill",
      "gate": "brief_approved",
      "inputs": ["brief.md"],
      "outputs": ["production/route_plan.json"],
      "status": "PLANNED"
    }
  ],
  "omitted": [],
  "human_gates": [],
  "autonomy_boundary": "The workbench plans and queues; a Codex task executes Skills."
}
```

Each step status must reflect evidence: `PLANNED`, `BLOCKED`, `RUNNING`, `COMPLETE`, or `SKIPPED`. A file path alone is not proof unless its expected schema/hash passes the relevant gate.
