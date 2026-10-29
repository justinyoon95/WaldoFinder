# Charlie-DB inspection and five-scene import

Inspected October 27, 2026. Source: [pekatour/Charlie-DB](https://github.com/pekatour/Charlie-DB),
pinned to commit `e97f7646a2f0e72ddcc02bbb6f7a179dae63e174`.

## Suitability

Suitable for a small local annotation and loader pilot using `original-images/`
with `original-labels/`. This is not yet a curated training or evaluation set.
The source annotations include Waldo portraits in stamps, title panels, and
character guides as well as Waldo hidden in the scene. All existing Waldo boxes
were retained. No missing labels were inferred, and no training was performed.

The original labels follow a visible-character policy: enclose the largest
visible extent, including the body when visible. They are not uniformly full-body
boxes, since characters can be occluded or depicted only as portraits. A separate
`original-labels_only_head/` directory contains deliberately head-only labels;
those were inspected for comparison but were not imported. The authors explain
the distinction in report section 3.2.1 and figure 10.

## Original scene inventory and resolutions

Measured the headers of all 100 files in `original-images/`; all have distinct
Git blob hashes. There are 100 corresponding body-label files and 100 head-label
files. Files are named `book-page-type`, where type 0 is a complete illustration,
types 1 and 2 are halves, and type 3 is a crop, according to the source README.

| File type | Count |
| --- | ---: |
| Full illustration (0) | 43 |
| First half (1) | 26 |
| Second half (2) | 26 |
| Crop (3) | 5 |

Grouping by the first two filename components produces **72 scene identifiers**:
71 numbered book/page groups and the special crop `7-999-3`. This is a filename
inventory, not proof of 72 visually distinct underlying illustrations. In
particular, the relationship of the `999` crop to other scenes is undocumented.
The May 2025 report describes 100 images and 70 complete illustrations; that
description does not exactly match the current filename inventory. The exact
visually deduplicated scene count is therefore unverified. Do not count the 100
files as independent scenes or split halves/crops of the same scene across sets.

The 100 files have **95 unique width/height pairs**. Widths range from 954 to
3591 pixels; heights range from 702 to 2343 pixels. The smallest by pixel area
is `7-4-3.jpg` at 954 x 702; the largest is `2-6-0.jpg` at 3591 x 2244. The
maximum height belongs to a different image. The complete per-file inventory is
saved locally in `data/sources/charlie-db/image-resolutions.json`.

## Annotation format and conversion

Each source `.txt` label matches an image stem. Each line has five values:

```text
class_id center_x center_y box_width box_height
```

Coordinates and dimensions are normalized to the image width and height.
The source `data.yaml` maps classes in order: `0 = Charlie` (Waldo), `1 = Odlaw`,
`2 = Wenda`, `3 = Wizard Whitebeard`. Only source class 0 was imported. Our
dataset loader assigns those boxes class 1; TorchVision reserves class 0 for
background, so copying source class numbers directly would be incorrect.

For actual image dimensions W and H, conversion to our pixel XYXY format is:

```text
xmin = (center_x - box_width / 2) * W
ymin = (center_y - box_height / 2) * H
xmax = (center_x + box_width / 2) * W
ymax = (center_y + box_height / 2) * H
```

No clipping, coordinate rounding, box enlargement, relabeling, or image resizing
was applied. The JPEG files were copied byte-for-byte and original IDs retained.
Other character classes were excluded, rather than converted to Waldo.

## Imported sample and previews

The five full-image files represent five different book/page groups. These are
original repository files, not generated imagettes or source model predictions.

| Source ID | Width x height | Existing Waldo boxes | Full-resolution preview |
| --- | --- | ---: | --- |
| 1-2-0 | 1440 x 900 | 2 | `outputs/charlie-db/1-2-0.png` |
| 1-4-0 | 1280 x 864 | 1 | `outputs/charlie-db/1-4-0.png` |
| 2-1-0 | 1560 x 978 | 3 | `outputs/charlie-db/2-1-0.png` |
| 3-1-0 | 2800 x 1760 | 2 | `outputs/charlie-db/3-1-0.png` |
| 4-1-0 | 3473 x 2175 | 3 | `outputs/charlie-db/4-1-0.png` |

Our validator passed: **5 images, 11 Waldo boxes, 0 verified negative scenes**.
All five full-resolution previews were generated with `waldo-visualize`.
`outputs/charlie-db/box-details.png` shows the local context of all 11 boxes,
labeled with source scene IDs and original label line numbers. Review the
portrait and guide-panel examples before deciding on a future training policy.
The overlays show source ground truth, not predictions or an accuracy result.

Run from the project directory:

```sh
source .venv/bin/activate
waldo-validate --annotations data/annotations/charlie-db.json --images data/images
waldo-visualize --annotations data/annotations/charlie-db.json --images data/images \
  --index 0 --output outputs/charlie-db/1-2-0.png --show
```

The imported manifest is `data/annotations/charlie-db.json`, in our existing
version-1 format; image paths are relative to `data/images/`. The empty tracked
starter manifest remains unchanged. The imported images, converted manifest,
downloaded documentation, original labels, provenance sidecar, and generated
previews are all Git-ignored. No data was committed or pushed.

## Attribution, provenance, and stated terms

The project credits Timothée Klein, Cyrian Ragot, Yannis Rosseel, and Baptiste
Arrix-Pouget. Its [README](https://github.com/pekatour/Charlie-DB/blob/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/README.md)
lists image sources: Hey-Waldo, HereIsWally, Brad Kenstler's article, Kurtis
Brandt's Roboflow dataset, the Random Acts of Amazon subreddit, and the authors'
own book scans. The report describes collaborative annotation with Label Studio
and YOLO export, and scans from a pocket compilation of the first six editions.
It cites Martin Handford's 2010 Gründ compilation. There is no per-image mapping
to the listed upstream sources in the inspected documentation.

The repository [LICENSE](https://github.com/pekatour/Charlie-DB/blob/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/LICENSE)
states MIT, copyright (c) 2025 pekatour, with the requirement to retain its
copyright and permission notices. A verbatim local copy is retained in
`data/sources/charlie-db/LICENSE`. The inspected documentation does not provide
separate, verified permissions for every underlying book image or a clear chain
of rights for the aggregated images. The stated repository license should not
be treated as verification of image redistribution rights. This import is a
local technical pilot; no images are being republished to our public GitHub.

`data/sources/charlie-db/provenance.json` preserves author attribution, repository
and pinned commit, original paths and URLs, scene group identifiers, SHA-256
hashes, each imported source label line, conversion details, and class mapping.
Original downloaded images and both original label variants are retained beside
it. Repository blob hashes were checked when downloading the sample. The full
source report and inventory are retained in the same ignored source directory.

### Source references

- [Original images](https://github.com/pekatour/Charlie-DB/tree/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/original-images)
- [Original visible-character labels](https://github.com/pekatour/Charlie-DB/tree/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/original-labels)
- [Class map](https://github.com/pekatour/Charlie-DB/blob/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/data.yaml)
- [Project report](https://github.com/pekatour/Charlie-DB/blob/e97f7646a2f0e72ddcc02bbb6f7a179dae63e174/Projet_Charlie.pdf), sections 2.1-2.3, 3.2.1, 3.2.3, figure 10, and references.
