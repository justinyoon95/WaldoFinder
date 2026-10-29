"""Planning only: no crops, detector, weights, or training."""

from .annotations import AnnotationError
from .geometry import all_exclusions, region_contains_box, region_overlaps_box


def overlaps(a, b):
    """Positive-area overlap; touching edges alone do not overlap."""
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def skip_tile(tile, exclusion_rectangles):
    """Skip on ANY rectangle/polygon intersection, regardless of Waldo boxes."""
    return any(region_overlaps_box(r, tile) for r in exclusion_rectangles)


def _starts(length, tile_size, stride):
    last = max(0, length - tile_size)
    starts = list(range(0, last + 1, stride))
    if starts[-1] != last:
        starts.append(last)
    return starts


def plan_tiles(record, scene_review, tile_size=512, stride=256):
    """Require complete human review, then plan kept/skipped source rectangles.

    Every portrait/guide label must be contained in a manually drawn exclusion
    region. This prevents silently turning those positives into negatives.
    A region that overlaps a hidden-scene positive needs explicit correction.
    Call load_review first to verify the sidecar against the source data.
    """
    if any(type(n) is not int or n <= 0 for n in (tile_size, stride)) or stride > tile_size:
        raise AnnotationError("Require positive integer stride <= tile_size")
    if scene_review["file_name"] != record["file_name"]:
        raise AnnotationError("Tile record and review image do not match")
    boxes = scene_review["boxes"]
    if not scene_review["exclusions_reviewed"] or any(b["decision"] == "unreviewed" for b in boxes):
        raise AnnotationError("Finish box classifications and explicitly confirm panel-region review before tiling")
    rectangles = all_exclusions(scene_review)
    for box in boxes:
        bbox = box["bbox"]
        if box["decision"] == "portrait_or_guide":
            if not any(region_contains_box(r, bbox) for r in rectangles):
                raise AnnotationError(f"{box['preview_label']} needs a containing manual panel exclusion")
        elif box["decision"] == "hidden_scene_waldo" and skip_tile(bbox, rectangles):
            raise AnnotationError(f"Exclusion region overlaps hidden positive {box['preview_label']}")
    kept, skipped = [], []
    for y in _starts(record["height"], tile_size, stride):
        for x in _starts(record["width"], tile_size, stride):
            tile = [x, y, min(x + tile_size, record["width"]), min(y + tile_size, record["height"])]
            hits = [r["id"] for r in rectangles if region_overlaps_box(r, tile)]
            if hits:
                skipped.append({"bbox": tile, "exclusion_ids": hits})
            else:
                kept.append(tile)
    return {"file_name": record["file_name"], "tile_size": tile_size, "stride": stride,
            "kept": kept, "skipped": skipped}
