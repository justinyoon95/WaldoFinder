# Manual box review and panel exclusions

Review decisions live separately from the immutable imported annotations in
`data/annotations/charlie-db-review.json`. This sidecar is Git-ignored along
with the imported data. The original manifest, original source labels, and
original ground-truth previews remain unchanged.

## Saved decisions

The five-scene pilot review was completed on October 28, 2026. The user
confirmed all 11 box positions and supplied every classification and panel
polygon. Every scene's region review was explicitly confirmed complete.

| Scene | Hidden-scene Waldo | Portrait/guide | Exclusion polygons | Region review |
| --- | ---: | ---: | ---: | --- |
| 1-2-0 | 1 | 1 | 1 | Complete |
| 1-4-0 | 1 | 0 | 0 | Complete, no exclusions |
| 2-1-0 | 1 | 2 | 1 | Complete |
| 3-1-0 | 1 | 1 | 1 | Complete |
| 4-1-0 | 1 | 2 | 1 | Complete |

All six portrait/guide boxes are contained in their manual exclusions, and no
exclusion overlaps any of the five hidden-scene Waldo boxes. These are data
review counts, not model results. No training has been started. Detailed
coordinates and decisions remain in the Git-ignored local sidecar.

For example, these decisions match the numbered labels on the original
`outputs/charlie-db/2-1-0.png` preview, rather than raw YOLO annotation order:

| Preview label | Decision | Location | Original YOLO label line |
| --- | --- | --- | ---: |
| Waldo 1 | portrait_or_guide | Lower-left character guide figure | 3 |
| Waldo 2 | hidden_scene_waldo | Upper-right waterfall area | 5 |
| Waldo 3 | portrait_or_guide | Upper-left portrait above the book | 7 |

No classifications or panel boundaries were inferred. The original imported
annotations and source files remain unchanged.

Each decision records its displayed preview label and original pixel box.
The imported manifest and image SHA-256 hashes bind it to the reviewed source.
The Charlie-DB sidecar also records original source label line numbers and the
original preview hashes. Review validation fails if the manifest or image changes,
or the saved preview-to-box mapping no longer matches. A raw source label line
number is not a preview Waldo number.

## Continue identifying boxes

The Charlie-DB images, imported manifest, and review sidecar are local files
and are not distributed in this repository. The commands below require those
inputs. For another locally prepared dataset, initialize a fresh review with
the API below, then pass its paths to the CLI. Existing review files are never
overwritten by this example:

```python
from pathlib import Path
from waldofinder.annotations import load_annotations
from waldofinder.review import new_review, save_review

annotations = Path("data/annotations/charlie-db.json")
images = Path("data/images")
reviews = Path("data/annotations/charlie-db-review.json")
if reviews.exists():
    raise FileExistsError("Review already exists; use it without reinitializing")
records = load_annotations(annotations, images)
save_review(reviews, new_review(records, annotations, images))
```

Fresh reviews start with every category and position unreviewed, no exclusions,
and region review incomplete. The original data is not modified.

From the project directory, activate the environment and inspect status:

```sh
source .venv/bin/activate
waldo-review status
waldo-review show --scene 2-1-0 --show
```

Continue sending scene IDs and the **original preview's Waldo numbers** in this
chat. You can also save a classification directly from your terminal:

```text
waldo-review classify --scene SCENE_ID --waldo PREVIEW_NUMBER --decision CATEGORY
```

Use `hidden_scene_waldo`, `portrait_or_guide`, or `unreviewed` to explicitly
undo a classification. Classification commands update only the review sidecar.
Review overlays retain the original Waldo numbers: orange is portrait/guide,
green is hidden-scene Waldo, red is unreviewed, and blue shading marks manually
excluded rectangles or polygons. New review previews are written to `outputs/review/`.

## Manually mark whole panels

For tilted panels, use a **four-corner polygon**. To edit the existing exclusion
for scene 1-2-0 while retaining its saved geometry until a replacement is saved:

```sh
waldo-review exclude --scene 1-2-0 --id instruction-panel --shape polygon --replace
```

Click the panel's four corners in perimeter order: **top-left, top-right,
bottom-right, bottom-left**. Reverse order is also accepted. Check the blue
outline, then click **Save polygon**. Clicking four corners alone does not save.
**Undo corner** removes the most recent point; **Reset** clears all four points.
**Cancel** or closing the window preserves the previously saved shape.
The Save button stays disabled for fewer than four corners or a crossed,
concave, or degenerate shape. Do not draw a box around Waldo alone: mark the
whole panel. The tool does not choose any corners automatically.

For a new panel, omit `--replace` and choose a unique ID. Polygon vertices are
saved in the optional `exclusion_polygons` list as four original-pixel
`[x, y]` points. Existing rectangle-only sidecars still work without migration.
The rectangle and polygon ID namespace is shared within each scene. To specify
four manually measured corners from the terminal, use
`--shape polygon --points X1 Y1 X2 Y2 X3 Y3 X4 Y4`.

Replacement happens only after Save, and resets region completion to false.
The tool reloads the sidecar after the drawing window closes so other saved box
decisions are preserved. If the same exclusion was changed while drawing,
replacement fails rather than overwriting that change. Review and confirm the
new polygon overlay before using `finish-regions`.

Axis-aligned rectangles remain available for panels where that is sufficient.
For example, to add a new rectangle exclusion with a new ID in scene 2-1-0:

```sh
waldo-review exclude --scene 2-1-0 --id additional-panel
```

Drag around the **whole instruction panel**, including its text and guide
figures, and press **Save rectangle**. Drag again to redraw before saving.
Cancel or close the window to leave the review unchanged. The window fits the
original image to the screen and converts the drag back to original pixel
coordinates; it does not resize source data. This requires Python with Tk and
a desktop session. If Tk is unavailable, use original pixel coordinates:

```text
waldo-review exclude --scene SCENE_ID --id PANEL_ID --box XMIN YMIN XMAX YMAX
```

Coordinates use the same XYXY convention as annotation boxes. The command
accepts `--reason instruction_panel`, `--reason character_guide`, or
`--reason portrait_panel`. Rectangle IDs must be unique within a scene; use a
different ID to add another panel. Pass `--replace` to correct an existing
region without losing it on Cancel. To remove a saved region explicitly:

```text
waldo-review remove-exclusion --scene SCENE_ID --id PANEL_ID
```

Every exclusion addition, replacement, or removal resets `exclusions_reviewed` to false. Once
you have checked the **whole scene** for panels, explicitly finish that review:

```text
waldo-review finish-regions --scene SCENE_ID
```

This action also records an intentionally empty exclusion list on a scene
without panels. An empty list alone never implies that review is complete.
Confirming regions does not automatically classify any Waldo boxes.

## Pilot tile exclusion rule

The shared `waldofinder.tiling.skip_tile` function skips a tile if its source
rectangle has **any positive-area intersection** with a manually marked panel.
For polygon exclusions, intersection is computed against the actual convex
four-corner shape, not its bounding rectangle. This keeps tiles outside the
tilted panel even when they fall inside the polygon's bounding rectangle.
There is no intersection-over-union threshold. A one-pixel overlap is enough;
touching edges without shared area is allowed. A tile entirely inside a panel
is skipped even if it does not contain a labeled portrait. This avoids training
on panel text or on unlabeled guide characters as if they were background.

`plan_tiles` also requires all box categories to be reviewed and
`exclusions_reviewed` to be explicitly true. Every portrait/guide box must be
contained in a manually marked exclusion rectangle or polygon. If a marked region
intersects a reviewed hidden-scene Waldo, planning fails so the conflict can be
reviewed rather than silently discarding that positive.

After completing a scene's manual review, preview tile coordinates with:

```text
waldo-review plan --scene SCENE_ID --tile-size 512 --stride 256
```

This is a **coordinate plan only**, saved under `outputs/review/`. It records
kept tiles and skipped tiles with the IDs of the rectangles they overlap. It
does not crop images, generate training labels, initialize a model, or start
training. The illustrative tile size and stride are configurable, not a model
or training recommendation. No real-scene tile plan has been run while review
is incomplete.

All commands accept `--annotations`, `--reviews`, and `--images` before the
subcommand for other input paths. The defaults select the Charlie-DB pilot.
If your editable installation predates `waldo-review`, either reinstall with
`python -m pip install --no-deps --no-build-isolation -e .` or replace
`waldo-review` with `python -m waldofinder.review_cli`.
