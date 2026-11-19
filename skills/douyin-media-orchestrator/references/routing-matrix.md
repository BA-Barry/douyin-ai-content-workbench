# Media Skill routing matrix

## Shared first steps

- `douyin-media-orchestrator`: route, gates, plan, evidence.
- `douyin-prompt-director`: build the provider-neutral visual DNA, shot/series ledger, continuity locks, sound plan, and auditable prompt package before any generator-specific compiler.
- Topic/script research skills or project research files when evidence is required.
- `hyperframes-motion-language`: only for video motion design, not still-image posts.

## IMAGE_CAROUSEL

Select one primary style by intent:

| Intent signals | Primary style Skill |
|---|---|
| impossible world, fantasy scenery, adult emotional habitat | `ai-scenery-studio` |
| warm American road trip, motel, diner, coastal road | `americana-roadtrip-wallpaper` |
| realistic analog scene plus contextual English poetry | `cinematic-memory-wallpaper` |
| handmade vintage stickers, scrapbook, controlled text | `retro-scrapbook-collage` |
| restrained photo-and-paper postcard, negative space | `minimal-postcard-wallpaper` |
| travel cards, zine, weekend collage | `travel-zine-wallpaper` |
| fictional person plus quiet daily fragments | `photo-diary-collage-wallpaper` |

The selected style Skill contributes constraints to `douyin-prompt-director`; it does not replace the common prompt package. Then use `imagegen` for the actual bitmap generation and `douyin-wallpaper-export` for export/QA. Use `cinematic-director-frame` in prompt-only mode only when precise film-frame grammar is needed, adapting its default 2.35:1 frame to 9:16 unless the user explicitly requests scope. Use `baoyu-image-gen` only if the user explicitly chooses an external provider or a required operation is unavailable in built-in image generation.

## ATMOSPHERE_VIDEO

- Choose exactly one provider compiler after `douyin-prompt-director`:
  - `seedance-prompt-zh` for Seedance / 即梦 tasks and scoped `@` references.
  - official `h3-prompt-writing` for MiniMax H3 T2VA, I2VA, FL2VA, L2VA, or Ref2VA.
- Never auto-route both provider compilers for the same generation task.
- `hyperframes-motion-language`: define continuity, camera/motion contract, and cut ledger.
- `remotion-best-practices` plus the focused Remotion skills actually needed: `remotion-create`, `remotion-markup`, `remotion-multimedia`, `remotion-studio`, `remotion-render`.
- `douyin-caption-pipeline` only when dialogue, narration, or evidence text exists.
- `video-use` for editorial assembly, grading, overlays, subtitles, and QA.
- `music` or `sound-effects` only after provider/cost/rights approval; otherwise platform music or cleared local audio.

## NARRATED_EXPLAINER

- Evidence-backed script and storyboard first.
- Choose one provider compiler only: `seedance-prompt-zh` or official `h3-prompt-writing`.
- `text-to-speech` or `voice-changer` only after voice-rights, cost, and sample gates; user voice may be recorded instead.
- `douyin-caption-pipeline` for transcription, captions, and alignment.
- `hyperframes-motion-language`, focused Remotion skills, and `video-use` for assembly.
- `voice-isolator` only when approved source audio actually needs cleanup.
- Finish with media technical QA and independent content QA.

## Do not auto-route

- Patent, spreadsheet, document, presentation, trading, travel-booking, or unrelated application Skills.
- A paid provider merely because its Skill is installed.
- Multiple visual-style Skills when one coherent system is enough.
- Seedance and H3 compilers together for one generation task.
