# Adding and labeling scenes

1. Use real scenes you have permission to use. Keep an unchanged backup. Choose
   a stable filename for each and copy it into `data/images/`. PNG and JPEG are
   straightforward choices; use single-frame files. Keep the original resolution.
2. Ensure the saved pixels are upright before labeling. Some files use EXIF
   orientation to rotate their display without rotating their pixels. Normalize
   orientation in an image editor and save, then label that saved file. The
   validator rejects orientation values other than 1 to avoid coordinate drift.
3. Open the saved image in an editor that shows original pixel dimensions and
   selection coordinates. Zoom and draw a rectangle around Waldo. Record the
   edges in original pixels, not the coordinates of the zoomed display. If your
   tool reports `(x, y, width, height)`, convert to
   `[x, y, x + width, y + height]`. Do not use normalized 0–1 coordinates.
4. Add a record with the actual filename, width, height, and measured boxes to
   the manifest. All boxes refer to Waldo; no class field is needed. Keep each
   image in the manifest only once. Unlisted files are excluded from the dataset.
5. Run `waldo-validate`, then `waldo-visualize --index INDEX --show` for every
   new record. Zoom in and compare the red rectangle with the character. Correct
   mistakes in the JSON and repeat. A passing validator cannot judge identity.

## Format (version 1)

The initial file is valid JSON scaffolding, but is intentionally not yet a dataset:

```json
{
  "version": 1,
  "images": []
}
```

Each entry in `images` must have exactly these fields:

| Field | Meaning |
| --- | --- |
| `file_name` | Image path relative to `data/images/` (including subdirectories if used) |
| `width` | Actual saved image width in pixels, a positive integer |
| `height` | Actual saved image height in pixels, a positive integer |
| `boxes` | List of `[xmin, ymin, xmax, ymax]` boxes measured by you |

No example coordinates or labels are supplied: fill them from your real images.
JSON keys and filenames need double quotes; trailing commas and comments are
not allowed. The schema is deliberately strict to catch misspelled fields.

The origin `(0, 0)` is the upper-left image corner. X increases to the right;
Y increases downward. Coordinates describe continuous edges; the right and
bottom boundaries may equal the image width and height. Every box must satisfy:

```text
0 <= xmin < xmax <= width
0 <= ymin < ymax <= height
```

Both integers and finite decimals are accepted. The box area is
`(xmax - xmin) * (ymax - ymin)`. Do not swap X/Y, use center coordinates,
or use a width/height pair in place of the far edges.

## Keep the labeling policy consistent

Enclose the visible Waldo character as tightly as practical, including his hat,
body, and visible limbs. Use the visible extent when he is partly occluded;
do not guess hidden body boundaries. Exclude unrelated characters and detached
props. Label every clearly identifiable occurrence of Waldo in a scene. Similar
striped characters are not Waldo merely because their clothes look alike.

An empty `boxes` list means you carefully verified that Waldo is absent. It is
a **negative example**, not an unfinished annotation. Negative scenes teach a
detector that it should sometimes return no detections. If you have not found
Waldo or are uncertain about identity, leave that entire image out of the
manifest until reviewed. Do not convert uncertainty into a negative label.

Start with a few carefully checked scenes to exercise the workflow; this is not
an assertion that a few images will be enough to train a useful detector. Add
variety in scale, crowd density, colors, and occlusion over time. Keep a separate
source/provenance note so copies and crops of a scene can stay in the same
future train/validation/test split.

If files change resolution, rotation, or crop after labeling, the coordinates
may be invalid even if the JSON still looks plausible. Re-label or explicitly
transform all coordinates, then validate and inspect the overlays again.
