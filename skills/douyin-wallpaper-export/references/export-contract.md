# Export contract and checklist

## Required records

For each asset retain: source path/hash/dimensions, final path/hash/dimensions, colour mode, export quality and chroma setting, and whether the source was natively large enough.

## Visual quality gate

1. Full-size: no broken faces/hands, duplicate objects, invented words, brands, logos, watermarks, banding, or smeared detail.
2. 360×640: subject reads at first glance; controlled text remains readable; copy has sufficient contrast; important content is not against the bottom UI zone or right-side interaction area.
3. Sequence: filename order matches the intended reading order; first image works as a cover; no near-duplicate scene appears adjacent unless intentional.
4. Upload form: confirm the displayed image count, title, caption, visibility, and any AI-content declaration. Stop before the Publish button unless the user gives a separate immediate confirmation.

## Suggested Pillow export

```python
image.convert("RGB").resize((2160, 3840), Image.Resampling.LANCZOS).save(
    target, "JPEG", quality=96, subsampling=0, optimize=True, progressive=True
)
```

This is a processing recipe, not proof that a low-resolution or soft source has become genuinely high-detail.
