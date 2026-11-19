---
name: "Americana Retro Road Wallpaper"
version: "1.0"
tags:
  - americana
  - road trip
  - vintage editorial
  - mobile wallpaper
author: "抖音视频项目"
source_url: ""
created: "2026-08-19"

style_prompt_short: >
  真实美式公路摄影作为主体，以六套不重复的复古旅行贴纸和准确英文短句建立系列识别；
  暖褪色胶片、少量纸张颗粒、克制排版，仍然首先是一张可以保存的手机壁纸。

style_prompt_full: >
  Use an existing photorealistic vertical American road-trip landscape as the untouched photographic base.
  Add exactly three deterministic vector travel ephemera overlays per image, each with accurately typeset English:
  one primary phrase, one location/mood label, and one short supporting phrase. Use a restrained palette of
  postcard cream #E8D8B6, faded brick red #A73B2B, highway navy #17365D, muted mustard #C89B48, and road charcoal #272624.
  Typography uses Rockwell or Georgia Bold for the primary phrase, Arial Narrow Bold for condensed labels,
  and Courier New for small ticket details. Each image must use a different sticker family and different wording;
  no repeated blank shields, no repeated layouts, and no generic empty badges. Total overlay area stays below 15 percent
  of the frame. Preserve the photographic subject, road, horizon, buildings, people state, color grade, perspective,
  and all underlying pixels except where the overlays are intentionally composited. Keep the center focal subject and
  lock-screen reading area clear. Use subtle paper grain, 1–3 degree rotation, thin outlines, and print wear without
  making text unreadable. No logos, trademarks, real route numbers, brand names, watermarks, neon colors, scrapbook clutter,
  fake handwriting, AI-generated lettering, or more than three overlays.

colors:
  primary:
    - name: "Postcard Cream"
      hex: "#E8D8B6"
      role: "paper fields and light sticker grounds"
    - name: "Highway Navy"
      hex: "#17365D"
      role: "outlines, condensed labels and quiet contrast"
  accent:
    - name: "Faded Brick Red"
      hex: "#A73B2B"
      role: "primary phrase, postmarks and arrows"
    - name: "Muted Mustard"
      hex: "#C89B48"
      role: "small stars and print-wear accents"
  neutral:
    - name: "Road Charcoal"
      hex: "#272624"
      role: "small ticket details and dark text"

typography:
  display:
    family: "Rockwell; fallback Georgia"
    weight: "bold"
    style: "uppercase, compact, lightly weathered but fully readable"
  body:
    family: "Arial Narrow"
    weight: "bold"
    style: "uppercase condensed travel labels"
  caption:
    family: "Courier New"
    weight: "regular"
    style: "small ticket details; never smaller than legibility threshold"
  rules:
    - "All wording is rendered deterministically after image generation"
    - "No phrase repeats across the six-image batch"
    - "Primary phrase is 2–4 words; secondary labels are 1–3 words"
    - "No fake route numbers, brands, real venue names or model-generated lettering"

layout:
  grid: "1080×1920; critical photographic subject remains unobstructed"
  alignment: "asymmetric corner anchoring; never three identical corners across adjacent images"
  aspect_ratio: "9:16"
  notes:
    - "Exactly three overlays per image"
    - "Combined overlay area below 15 percent"
    - "Use six different sticker families: motel tag, coastal postcard, fuel receipt, park permit, camp label, morning paper"
    - "Keep phone clock and central focal region visually clear"

motion:
  transitions:
    - "none for still wallpaper"
  animation_style: "Static deterministic editorial overlay. No generated motion."
  pacing: "not applicable"
  audio_cues: []

mood:
  keywords:
    - "nostalgic"
    - "open-road"
    - "quiet"
    - "collectible"
  era: "mid-century American travel ephemera interpreted for a modern phone wallpaper"
  cultural_reference: "generic roadside postcards, motel key tags, paper tickets and park permits; no specific brand or artist imitation"
  avoid:
    - "repeated blank highway shields"
    - "dense scrapbook collage"
    - "neon retro-futurism"
    - "unreadable distressed type"
    - "logos, brands and real route numbers"

assets:
  reference_images: []
  gsep_elements: []
  html_snippets: []
  color_palette_image:
    url: ""

x_douyin_wallpaper:
  canvas: "1080x1920"
  overlay_count_per_image: 3
  max_overlay_area_percent: 15
---

## Design Principles

The photograph remains the product; the editorial layer only gives it a collectible identity. Every sticker must carry information, every phrase must be readable, and every image must have a distinct travel-object metaphor. Repetition comes from palette and type hierarchy, not from copying the same empty badge.

## Deterministic phrase map

| Image | Sticker family | Primary phrase | Label | Supporting phrase |
|---|---|---|---|---|
| P01 | motel key tag + postmark + ticket | TAKE THE LONG WAY | DESERT MOTEL | WESTBOUND |
| P02 | coastal postcard + wave seal + torn ticket | KEEP DRIVING | COASTLINE | SALT AIR |
| P03 | fuel receipt + star patch + oval badge | LAST STOP | HIGH PLAINS | OPEN ROAD |
| P04 | park permit + compass seal + pennant | OFF THE MAP | PINE COUNTRY | SLOW MILES |
| P05 | camp tag + lake seal + paper tape | STAY AWHILE | LAKESIDE | NO RUSH |
| P06 | morning paper + civic seal + luggage label | MORNING, SOMEWHERE | SMALL TOWN | TAKE IT SLOW |

## Application Notes

- Render overlays as deterministic SVG/HTML or equivalent vector layers, then composite once over the frozen PNG.
- Keep an untouched copy of every source image and record before/after hashes.
- Do not ask an image model to regenerate or spell the English text.
- Run full-size and 360×640 readability checks before independent QA.
