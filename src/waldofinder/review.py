"""Human review sidecars; source annotations are never edited."""

import hashlib
import json
import math
from pathlib import Path

from .annotations import AnnotationError, image_path
from .geometry import valid_polygon

DECISIONS = {"unreviewed", "hidden_scene_waldo", "portrait_or_guide"}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_review(records, annotation_file, image_root):
    """Snapshot the same box numbering used by cli.render_record.

    Coordinates plus manifest/image hashes bind preview IDs to source geometry;
    preview IDs must never be interpreted as raw YOLO line numbers.
    """
    return {
        "version": 1,
        "annotation_sha256": file_hash(annotation_file),
        "images": [
            {"file_name": r["file_name"], "scene_id": Path(r["file_name"]).stem,
             "image_sha256": file_hash(image_path(Path(image_root), r["file_name"])),
             "boxes": [
                 {"preview_label": f"Waldo {i}", "bbox": list(box),
                  "decision": "unreviewed", "position_review": "unreviewed",
                  "reviewed_by": None}
                 for i, box in enumerate(r["boxes"], 1)
             ],
             "exclusion_rectangles": [], "exclusion_polygons": [], "exclusions_reviewed": False}
            for r in records
        ],
    }


def valid_rectangle(box, width, height):
    return (isinstance(box, list) and len(box) == 4
            and all(type(n) in (int, float) and math.isfinite(n) for n in box)
            and 0 <= box[0] < box[2] <= width
            and 0 <= box[1] < box[3] <= height)


def validate_review(review, records, annotation_file, image_root):
    if not isinstance(review, dict) or type(review.get("version")) is not int or review.get("version") != 1:
        raise AnnotationError("Review version must be 1")
    if review.get("annotation_sha256") != file_hash(annotation_file):
        raise AnnotationError("Annotation manifest changed since review; rematch preview IDs explicitly")
    scenes = review.get("images")
    if not isinstance(scenes, list) or len(scenes) != len(records):
        raise AnnotationError("Review must cover each manifest image exactly once")
    by_name = {r["file_name"]: r for r in records}
    seen, scene_ids = set(), set()
    for scene in scenes:
        if not isinstance(scene, dict):
            raise AnnotationError("Review image must be an object")
        name = scene.get("file_name")
        scene_id = scene.get("scene_id")
        if not isinstance(name, str) or name not in by_name or name in seen:
            raise AnnotationError("Unknown or duplicate review image")
        if not isinstance(scene_id, str) or not scene_id or scene_id in scene_ids:
            raise AnnotationError("Review scene IDs must be unique nonempty strings")
        seen.add(name)
        scene_ids.add(scene_id)
        record = by_name[name]
        if scene.get("image_sha256") != file_hash(image_path(Path(image_root), name)):
            raise AnnotationError(f"Image changed since review: {name}")
        boxes = scene.get("boxes")
        if not isinstance(boxes, list) or len(boxes) != len(record["boxes"]):
            raise AnnotationError(f"Review box count differs: {name}")
        for i, (box, original) in enumerate(zip(boxes, record["boxes"]), 1):
            if (not isinstance(box, dict) or box.get("preview_label") != f"Waldo {i}"
                    or box.get("bbox") != original):
                raise AnnotationError(f"Preview label or geometry mismatch: {name}, Waldo {i}")
            if not isinstance(box.get("decision"), str) or box.get("decision") not in DECISIONS:
                raise AnnotationError(f"Unknown review decision: {name}, Waldo {i}")
            if box.get("position_review") not in {"unreviewed", "accurate"}:
                raise AnnotationError(f"Unknown position review: {name}, Waldo {i}")
        if type(scene.get("exclusions_reviewed")) is not bool:
            raise AnnotationError("exclusions_reviewed must be true or false")
        rectangles = scene.get("exclusion_rectangles")
        if not isinstance(rectangles, list):
            raise AnnotationError("exclusion_rectangles must be a list")
        ids = set()
        for rect in rectangles:
            if not isinstance(rect, dict):
                raise AnnotationError("Exclusion rectangle must be an object")
            rect_id = rect.get("id")
            if not isinstance(rect_id, str) or not rect_id or rect_id in ids:
                raise AnnotationError("Exclusion rectangle IDs must be unique nonempty strings")
            ids.add(rect_id)
            if not valid_rectangle(rect.get("bbox"), record["width"], record["height"]):
                raise AnnotationError(f"Invalid exclusion rectangle: {name}, {rect_id}")
            if rect.get("reason") not in {"instruction_panel", "character_guide", "portrait_panel"}:
                raise AnnotationError("Unknown exclusion rectangle reason")
        polygons = scene.get("exclusion_polygons", [])
        if not isinstance(polygons, list):
            raise AnnotationError("exclusion_polygons must be a list")
        for polygon in polygons:
            if not isinstance(polygon, dict):
                raise AnnotationError("Exclusion polygon must be an object")
            polygon_id = polygon.get("id")
            if not isinstance(polygon_id, str) or not polygon_id or polygon_id in ids:
                raise AnnotationError("Exclusion IDs must be unique across rectangles and polygons")
            ids.add(polygon_id)
            if not valid_polygon(polygon.get("points"), record["width"], record["height"]):
                raise AnnotationError(f"Invalid four-corner polygon: {name}, {polygon_id}; click convex corners in perimeter order")
            if polygon.get("reason") not in {"instruction_panel", "character_guide", "portrait_panel"}:
                raise AnnotationError("Unknown exclusion polygon reason")
    return review


def load_review(path, records, annotation_file, image_root):
    try:
        review = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnnotationError(f"Cannot read review JSON: {exc}") from exc
    return validate_review(review, records, annotation_file, image_root)


def save_review(path, review):
    """Replace only the sidecar, atomically; caller validates before saving."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def find_scene(review, scene_id):
    for scene in review["images"]:
        if scene["scene_id"] == scene_id:
            return scene
    raise AnnotationError(f"Unknown scene: {scene_id}")
