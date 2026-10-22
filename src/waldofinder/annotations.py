"""Strict annotation and image validation, independent of PyTorch."""

import json
import math
from pathlib import Path

from PIL import Image


class AnnotationError(ValueError):
    """The manifest or an associated image is invalid."""


def image_path(root: Path, file_name: str) -> Path:
    path = (root / file_name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise AnnotationError("file_name must stay inside the image directory")
    return path


def load_annotations(annotation_file, image_root) -> list[dict]:
    """Validate the complete manifest and decode images; return image records.

    Empty boxes mean a human verified the scene contains no Waldo. An empty
    manifest is rejected so an unpopulated project cannot look training-ready.
    """
    root = Path(image_root)
    try:
        manifest = json.loads(Path(annotation_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnnotationError(f"Cannot read annotation JSON: {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"version", "images"}:
        raise AnnotationError("Manifest must contain exactly version and images")
    if type(manifest["version"]) is not int or manifest["version"] != 1:
        raise AnnotationError("version must be the integer 1")
    records = manifest["images"]
    if not isinstance(records, list) or not records:
        raise AnnotationError("images must be a nonempty list; add real labeled images first")

    errors, seen = [], set()
    for index, record in enumerate(records):
        prefix = f"images[{index}]"
        try:
            if not isinstance(record, dict) or set(record) != {"file_name", "width", "height", "boxes"}:
                raise AnnotationError("expected exactly file_name, width, height, boxes")
            name = record["file_name"]
            if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
                raise AnnotationError("file_name must be a nonempty relative path")
            path = image_path(root, name)
            if path in seen:
                raise AnnotationError(f"duplicate image: {name}")
            seen.add(path)
            width, height = record["width"], record["height"]
            if any(type(n) is not int or n <= 0 for n in (width, height)):
                raise AnnotationError("width and height must be positive integers")
            boxes = record["boxes"]
            if not isinstance(boxes, list):
                raise AnnotationError("boxes must be a list")
            for box_index, box in enumerate(boxes):
                if (not isinstance(box, list) or len(box) != 4
                        or any(type(n) not in (int, float) or not math.isfinite(n) for n in box)):
                    raise AnnotationError(f"boxes[{box_index}] must contain four finite numbers")
                x1, y1, x2, y2 = box
                if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                    raise AnnotationError(f"boxes[{box_index}] must satisfy 0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height")
            with Image.open(path) as image:
                if getattr(image, "n_frames", 1) != 1:
                    raise AnnotationError("use a single-frame image")
                if image.getexif().get(274, 1) != 1:
                    raise AnnotationError("normalize EXIF orientation before labeling")
                if image.size != (width, height):
                    raise AnnotationError(f"declared size {(width, height)} differs from actual {image.size}")
                image.load()
        except (AnnotationError, OSError, ValueError, Image.DecompressionBombError) as exc:
            errors.append(f"{prefix}: {exc}")
    if errors:
        raise AnnotationError("\n".join(errors))
    return records
