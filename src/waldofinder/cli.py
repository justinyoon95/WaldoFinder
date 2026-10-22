"""Command-line validation and ground-truth visualization."""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .annotations import AnnotationError, image_path, load_annotations


def _parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations/annotations.json"))
    parser.add_argument("--images", type=Path, default=Path("data/images"))
    return parser


def _records(parser, args):
    try:
        return load_annotations(args.annotations, args.images)
    except AnnotationError as exc:
        parser.exit(1, f"Validation failed:\n{exc}\n")


def validate_main():
    parser = _parser("Check annotation structure, boxes, and image files.")
    args = parser.parse_args()
    records = _records(parser, args)
    negatives = sum(not record["boxes"] for record in records)
    print(f"Valid: {len(records)} images, {sum(len(r['boxes']) for r in records)} Waldo boxes, {negatives} verified negative scenes.")
    referenced = {image_path(args.images, r["file_name"]) for r in records}
    unlisted = [p for p in args.images.rglob("*") if p.is_file()
                and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
                and p.resolve() not in referenced]
    if unlisted:
        print(f"Note: {len(unlisted)} image files are unlisted and will not be loaded:")
        for path in sorted(unlisted):
            print(f"  {path}")


def render_record(record, image_root):
    """Draw human annotations at full resolution; never draws predictions."""
    with Image.open(image_path(Path(image_root), record["file_name"])) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    line_width = max(2, min(image.size) // 500)
    for index, box in enumerate(record["boxes"], 1):
        # Annotation coordinates describe continuous edges, including W/H.
        # Raster drawing uses inclusive pixels, so clamp the far edge for display.
        x1, y1, x2, y2 = box
        draw.rectangle((math.floor(x1), math.floor(y1), math.ceil(x2) - 1, math.ceil(y2) - 1),
                       outline="red", width=line_width)
        draw.text((x1, max(0, y1 - 12)), f"Waldo {index} (ground truth)", fill="red", stroke_width=1, stroke_fill="white")
    if not record["boxes"]:
        draw.text((10, 10), "Ground truth: verified no Waldo", fill="red")
    return image


def visualize_main():
    parser = _parser("Save a scene with ground-truth boxes; optionally open it.")
    parser.add_argument("--index", type=int, default=0, help="Zero-based manifest index")
    parser.add_argument("--output", type=Path, default=Path("outputs/ground_truth.png"))
    parser.add_argument("--show", action="store_true", help="Open the saved preview in the system image viewer")
    args = parser.parse_args()
    records = _records(parser, args)
    if not 0 <= args.index < len(records):
        parser.error(f"--index must be between 0 and {len(records) - 1}")
    if args.output.suffix.lower() != ".png":
        parser.error("--output must end in .png")
    if args.output.resolve() in {image_path(args.images, r["file_name"]) for r in records} or args.output.resolve() == args.annotations.resolve():
        parser.error("--output cannot overwrite a source image or the annotation file")
    try:
        image = render_record(records[args.index], args.images)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.output)
    except OSError as exc:
        parser.exit(1, f"Cannot save preview: {exc}\n")
    print(f"Saved ground-truth preview: {args.output.resolve()} ({image.width} x {image.height})")
    if args.show:
        image.show()
