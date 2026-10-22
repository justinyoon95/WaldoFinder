# WaldoFinder

Fine-tune a pretrained object detector to find Waldo in high-resolution scenes.
This first milestone prepares and checks human annotations. It contains no
training loop, downloaded model, web interface, or evaluation results.

## Setup

Run these commands from this project directory. Python 3.10+ is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
waldo-inspect
python -m pytest
```

The [initial compute report](docs/compute.md) confirmed an Apple Silicon Mac
with 8 logical CPUs, 16 GiB RAM, and working MPS tensor operations outside the
sandbox. This is sufficient for the data preparation work here; detector
training requirements remain to be measured.

The dependency ranges live in `pyproject.toml`; pip resolves TorchVision's
matching PyTorch requirement. `requirements-lock.txt` records the versions
actually tested on this Mac. To reproduce those versions on a compatible
Python/platform, install them before the editable package:

```sh
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
```

For a future NVIDIA machine, select the platform-specific PyTorch build using
the [official installer](https://pytorch.org/get-started/locally/).

## Add your first data

Follow [the labeling guide](docs/labeling.md). Start with a few real scenes you
can inspect carefully. Put the original images in `data/images/`, and add their
human-measured boxes to `data/annotations/annotations.json`.

```sh
waldo-validate
waldo-visualize --index 0 --show
# A separate full-resolution PNG is also saved to outputs/ground_truth.png.
waldo-visualize --index 0 --output outputs/scene-0.png
```

`--show` opens the system image viewer. Without it, the command works headlessly
and saves the PNG for inspection. Zoom in to check the edges of each box.
These overlays display annotations, not model predictions.

Both commands also accept `--annotations PATH --images DIRECTORY`. Relative
CLI paths are resolved from the working directory. Each manifest `file_name`
is relative to the image directory. The initial manifest is deliberately empty;
validation exits with status 1 until real labeled images have been added.

```text
data/images/                  Your real images (ignored by Git)
data/annotations/annotations.json  Your human-authored manifest
src/waldofinder/annotations.py Annotation and image validation
src/waldofinder/dataset.py     PyTorch dataset and batching helper
src/waldofinder/cli.py         Validation and box visualization commands
src/waldofinder/compute.py     CPU/GPU and library checks
tests/                        Temporary software fixtures only
docs/                         Labeling guide and compute inspection notes
outputs/                      Generated previews (ignored by Git)
```

The starter manifest is tracked; local images, previews, and checkpoints are
ignored. Back up your source images and annotations together.

## What the loader returns

```python
from torch.utils.data import DataLoader
from waldofinder.dataset import WaldoDataset, collate_fn

dataset = WaldoDataset("data/annotations/annotations.json", "data/images")
loader = DataLoader(dataset, batch_size=1, shuffle=False,
                    num_workers=0, collate_fn=collate_fn)
images, targets = next(iter(loader))
```

Each image is an RGB `float32` tensor of shape `[3, height, width]`, with values
in `[0, 1]`. Its target includes `boxes` (`float32`, `[N, 4]`), `labels`
(`int64`, `[N]`, all `1` for Waldo), a scalar `int64` `image_id` (manifest
index), `area` (`float32`, `[N]`), and `iscrowd` (`int64`, `[N]`, all zero).
A verified negative has boxes shaped `[0, 4]` and empty labels/area/iscrowd.
This follows the [TorchVision detection target contract](https://docs.pytorch.org/tutorials/intermediate/torchvision_tutorial.html).

The loader validates the whole manifest and decodes every referenced image
once at construction, then reads images on demand. Do not change files while
using it. `collate_fn` keeps differently sized images as a list rather than
trying to stack them. Start with batch size 1: a full-resolution RGB float
tensor alone uses roughly `3 × height × width × 4` bytes, before model memory.

## ML concepts and the next milestone

**Object detection** predicts both a category and a bounding box. A box is
supervision: the human-provided target the model will eventually learn to match.
The validator checks geometry and file consistency; only a human can confirm
that the box really encloses Waldo.

**Transfer learning** starts from a detector trained on another dataset, with
useful visual features already learned. **Fine-tuning** adjusts its parameters
using your scenes. A later baseline can adapt a TorchVision Faster R-CNN head
to two classes: background (`0`) and Waldo (`1`). No model is constructed yet.

**Small objects** need care. This loader preserves every source pixel. A future
detector may resize internally, so preserving resolution here does not by itself
solve detection at high resolution. We should inspect Waldo's pixel size before
choosing model resizing or overlapping tiles. Any crop, resize, or flip must
transform its boxes too; do not apply image-only geometric augmentation.

**Generalization** means finding Waldo in unseen scenes, rather than memorizing
one page. Before training, reserve whole scenes for validation and testing.
Keep scans, crops, tiles, and alternate versions of the same scene in one split
to prevent leakage. No splits or accuracy claims exist at this stage.

After labeling and reviewing your first scenes, the next milestone can choose
the split, detector, and high-resolution strategy, then establish a measured
baseline. GPU availability alone does not establish detector operator support,
memory sufficiency, or training speed.
