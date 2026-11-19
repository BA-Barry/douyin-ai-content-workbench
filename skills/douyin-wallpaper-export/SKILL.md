---
name: douyin-wallpaper-export
description: Prepare and quality-check high-resolution vertical wallpaper images for Douyin image posts. Use after an image is approved and before upload; do not use to invent detail, alter content meaning, or publish.
---

# Douyin wallpaper export

Use this as the final technical pass for scenery, collage, or typography wallpaper batches.

## Export contract

- Keep the approved master untouched. Prefer a native 2160×3840 RGB source for upload; also make a 1080×1920 review copy.
- If the source is smaller, a high-quality Lanczos resize can add platform pixel headroom but **does not create detail**. Record this honestly.
- Export JPEG in RGB at high quality (typically 95–96), 4:4:4 chroma, progressive if supported. Avoid repeated re-encoding.
- Keep the aspect ratio at 9:16. Do not crop a composed text safe area merely to hit dimensions.

## Pre-upload checks

Read [the detailed check](references/export-contract.md). At minimum, inspect full size and a 360×640 preview; ensure no accidental text, logos, watermark, banding, blur, unintentional crop, or illegible controlled copy.

For a carousel, preserve ordered filenames such as `01_...jpg`, record source/output hashes and dimensions, and create a contact sheet. This skill prepares files only; it does not upload, choose music, or click Publish.
