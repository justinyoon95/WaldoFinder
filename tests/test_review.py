"""Human review identity and exclusion behavior on temporary geometric fixtures."""

import copy
import json

import pytest
from PIL import Image

from waldofinder.annotations import AnnotationError, load_annotations
from waldofinder.review import load_review, new_review, save_review, validate_review
from waldofinder.review_cli import display_rectangle, main
from waldofinder.tiling import overlaps, plan_tiles, skip_tile


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "images"
    root.mkdir()
    Image.new("RGB", (100, 80), "white").save(root / "fixture.png")
    record = {"file_name": "fixture.png", "width": 100, "height": 80,
              "boxes": [[5, 5, 10, 10], [85, 65, 95, 75]]}
    manifest = tmp_path / "annotations.json"
    manifest.write_text(json.dumps({"version": 1, "images": [record]}))
    records = load_annotations(manifest, root)
    review = new_review(records, manifest, root)
    path = tmp_path / "reviews.json"
    save_review(path, review)
    return root, manifest, path, records, review


def test_review_roundtrip_preserves_numbered_geometry_and_sources(reviewed):
    root, manifest, path, records, review = reviewed
    before = manifest.read_bytes()
    review["images"][0]["boxes"][1]["decision"] = "hidden_scene_waldo"
    save_review(path, review)
    result = load_review(path, records, manifest, root)
    box = result["images"][0]["boxes"][1]
    assert box["preview_label"] == "Waldo 2"
    assert box["bbox"] == [85, 65, 95, 75]
    assert manifest.read_bytes() == before
    assert result["images"][0]["boxes"][0]["decision"] == "unreviewed"
    assert result["images"][0]["exclusions_reviewed"] is False


def test_manifest_reordering_cannot_silently_reassign_review(reviewed):
    root, manifest, path, records, review = reviewed
    records[0]["boxes"].reverse()
    manifest.write_text(json.dumps({"version": 1, "images": records}))
    with pytest.raises(AnnotationError, match="manifest changed"):
        load_review(path, records, manifest, root)


def test_changed_image_rejected(reviewed):
    root, manifest, path, records, review = reviewed
    Image.new("RGB", (100, 80), "black").save(root / "fixture.png")
    with pytest.raises(AnnotationError, match="Image changed"):
        load_review(path, records, manifest, root)


@pytest.mark.parametrize("mutation", ["label", "geometry", "decision", "duplicate", "rectangle"])
def test_invalid_review_rejected(reviewed, mutation):
    root, manifest, path, records, review = reviewed
    scene = review["images"][0]
    if mutation == "label":
        scene["boxes"][0]["preview_label"] = "Waldo 2"
    elif mutation == "geometry":
        scene["boxes"][0]["bbox"] = [1, 1, 2, 2]
    elif mutation == "decision":
        scene["boxes"][0]["decision"] = "automatically_guessed"
    elif mutation == "duplicate":
        review["images"].append(copy.deepcopy(scene))
    else:
        scene["exclusion_rectangles"] = [{"id": "bad", "bbox": [0, 0, 101, 80], "reason": "instruction_panel"}]
    with pytest.raises(AnnotationError):
        validate_review(review, records, manifest, root)


def test_any_positive_area_panel_overlap_is_excluded():
    rectangles = [{"id": "whole-panel", "bbox": [10, 10, 60, 70]}]
    assert skip_tile([0, 0, 11, 11], rectangles)  # One pixel of intersection.
    assert skip_tile([20, 20, 30, 30], rectangles)  # No Waldo box is needed.
    assert skip_tile([0, 0, 100, 80], rectangles)
    assert not skip_tile([0, 0, 10, 10], rectangles)  # Edge/corner touch only.
    assert not overlaps([60, 10, 80, 20], rectangles[0]["bbox"])


def test_plan_waits_for_explicit_classification_and_region_review(reviewed):
    root, manifest, path, records, review = reviewed
    scene = review["images"][0]
    with pytest.raises(AnnotationError, match="Finish"):
        plan_tiles(records[0], scene)
    for box in scene["boxes"]:
        box["decision"] = "hidden_scene_waldo"
    with pytest.raises(AnnotationError, match="Finish"):
        plan_tiles(records[0], scene)
    scene["exclusions_reviewed"] = True
    assert plan_tiles(records[0], scene, 200, 100)["kept"] == [[0, 0, 100, 80]]


def test_plan_skips_whole_panels_and_preserves_right_bottom_coverage(reviewed):
    root, manifest, path, records, review = reviewed
    scene = review["images"][0]
    scene["boxes"][0]["decision"] = "portrait_or_guide"
    scene["boxes"][1]["decision"] = "hidden_scene_waldo"
    scene["exclusions_reviewed"] = True
    with pytest.raises(AnnotationError, match="containing manual panel"):
        plan_tiles(records[0], scene)
    scene["exclusion_rectangles"] = [{"id": "left-panel", "bbox": [0, 0, 40, 80]}]
    plan = plan_tiles(records[0], scene, 40, 30)
    assert len(plan["kept"]) == 3
    assert len(plan["skipped"]) == 6
    assert [60, 40, 100, 80] in plan["kept"]
    assert all(not skip_tile(tile, scene["exclusion_rectangles"]) for tile in plan["kept"])
    assert all(tile["exclusion_ids"] == ["left-panel"] for tile in plan["skipped"])
    scene["exclusion_rectangles"][0]["bbox"] = [0, 0, 100, 80]
    with pytest.raises(AnnotationError, match="overlaps hidden positive"):
        plan_tiles(records[0], scene)


@pytest.mark.parametrize("size,stride", [(0, 1), (10, 11), (True, 1), (10, -1)])
def test_invalid_tile_settings_rejected(reviewed, size, stride):
    scene = reviewed[4]["images"][0]
    with pytest.raises(AnnotationError, match="positive integer"):
        plan_tiles(reviewed[3][0], scene, size, stride)


def test_drag_maps_to_original_pixels_without_assuming_uniform_scale():
    assert display_rectangle((80, 30), (10, 5), (100, 40), (1000, 401)) == [100, 50, 800, 301]
    assert display_rectangle((-2, -3), (105, 45), (100, 40), (1000, 401)) == [0, 0, 1000, 401]
    with pytest.raises(AnnotationError, match="positive"):
        display_rectangle((0, 1), (0, 2), (100, 40), (1000, 400))


def test_cli_manual_rectangle_classification_and_preview(reviewed):
    root, manifest, path, records, review = reviewed
    common = ["--annotations", str(manifest), "--images", str(root), "--reviews", str(path)]
    before = manifest.read_bytes()
    main([*common, "classify", "--scene", "fixture", "--waldo", "2", "--decision", "hidden_scene_waldo"])
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--box", "0", "0", "40", "80"])
    result = load_review(path, records, manifest, root)
    assert result["images"][0]["boxes"][1]["decision"] == "hidden_scene_waldo"
    assert result["images"][0]["boxes"][0]["decision"] == "unreviewed"
    assert result["images"][0]["exclusion_rectangles"][0]["bbox"] == [0, 0, 40, 80]
    main([*common, "show", "--scene", "fixture"])
    assert (path.parent / "outputs/review/00-fixture.png").is_file()
    with pytest.raises(SystemExit):
        main([*common, "plan", "--scene", "fixture"])
    main([*common, "finish-regions", "--scene", "fixture"])
    main([*common, "remove-exclusion", "--scene", "fixture", "--id", "panel"])
    assert not load_review(path, records, manifest, root)["images"][0]["exclusions_reviewed"]
    assert manifest.read_bytes() == before


def test_canceling_native_marking_leaves_sidecar_unchanged(reviewed, monkeypatch):
    root, manifest, path, records, review = reviewed
    before = path.read_bytes()
    monkeypatch.setattr("waldofinder.review_cli.draw_rectangle", lambda image: None)
    main(["--annotations", str(manifest), "--images", str(root), "--reviews", str(path),
          "exclude", "--scene", "fixture", "--id", "canceled"])
    assert path.read_bytes() == before


def test_convex_polygon_uses_shape_instead_of_bounding_rectangle():
    from waldofinder.geometry import region_contains_box, valid_polygon
    points = [[50, 0], [100, 40], [50, 80], [0, 40]]
    assert valid_polygon(points, 100, 80)
    assert valid_polygon(points[::-1], 100, 80)
    region = {"id": "diamond", "points": points}
    assert skip_tile([40, 30, 60, 50], [region])
    assert skip_tile([0, 0, 100, 80], [region])
    assert not skip_tile([0, 0, 10, 10], [region])  # Inside bounding box, outside polygon.
    assert not skip_tile([100, 30, 110, 50], [region])  # Single shared point.
    assert region_contains_box(region, [40, 30, 60, 50])
    assert not region_contains_box(region, [0, 0, 10, 10])
    # Diagonal shared edge with no area; shifting by a fraction creates overlap.
    triangle_side = {"points": [[0, 0], [40, 40], [0, 80], [-40, 40]]}
    assert not skip_tile([20, 0, 30, 20], [triangle_side])
    assert skip_tile([20, 0, 30, 20.01], [triangle_side])


@pytest.mark.parametrize("points", [
    [[0, 0], [10, 10], [0, 10], [10, 0]],  # Crossed edges.
    [[0, 0], [10, 0], [2, 2], [0, 10]],  # Concave.
    [[0, 0], [5, 0], [10, 0], [0, 10]],  # Collinear corner.
    [[0, 0], [10, 0], [10, 0], [0, 10]],  # Duplicate.
    [[0, 0], [101, 0], [100, 80], [0, 80]],
    [[False, 0], [10, 0], [10, 10], [0, 10]],
    [[0, 0], [10, 0], [10, float("nan")], [0, 10]],
    [[0, 0], [10, 0], [10, float("inf")], [0, 10]],
    [[0, 0], [10, 0], [0, 10]],
])
def test_invalid_polygon_rejected(reviewed, points):
    from waldofinder.geometry import valid_polygon
    root, manifest, path, records, review = reviewed
    assert not valid_polygon(points, 100, 80)
    review["images"][0]["exclusion_polygons"] = [{"id": "panel", "points": points, "reason": "instruction_panel"}]
    with pytest.raises(AnnotationError, match="four-corner"):
        validate_review(review, records, manifest, root)


def test_old_rectangle_sidecars_still_load(reviewed):
    root, manifest, path, records, review = reviewed
    del review["images"][0]["exclusion_polygons"]
    save_review(path, review)
    assert load_review(path, records, manifest, root)["images"][0]["exclusion_rectangles"] == []


def test_polygon_cli_replace_save_and_cancel_preserve_decisions(reviewed, monkeypatch):
    root, manifest, path, records, review = reviewed
    common = ["--annotations", str(manifest), "--images", str(root), "--reviews", str(path)]
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--box", "0", "0", "40", "80"])
    before = path.read_bytes()
    source_before = manifest.read_bytes()
    monkeypatch.setattr("waldofinder.review_cli.draw_polygon", lambda image: None)
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--shape", "polygon", "--replace"])
    assert path.read_bytes() == before

    points = [[0, 0], [40, 0], [35, 80], [0, 80]]

    def draw_with_concurrent_classification(image):
        updated = load_review(path, records, manifest, root)
        updated["images"][0]["boxes"][1]["decision"] = "hidden_scene_waldo"
        save_review(path, updated)
        return points

    monkeypatch.setattr("waldofinder.review_cli.draw_polygon", draw_with_concurrent_classification)
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--shape", "polygon", "--replace"])
    result = load_review(path, records, manifest, root)["images"][0]
    assert result["exclusion_rectangles"] == []
    assert result["exclusion_polygons"][0]["points"] == points
    assert result["boxes"][1]["decision"] == "hidden_scene_waldo"
    assert result["boxes"][0]["decision"] == "unreviewed"
    assert not result["exclusions_reviewed"]
    assert manifest.read_bytes() == source_before
    main([*common, "show", "--scene", "fixture"])
    main([*common, "remove-exclusion", "--scene", "fixture", "--id", "panel"])
    assert load_review(path, records, manifest, root)["images"][0]["exclusion_polygons"] == []


def test_polygon_plan_requires_actual_containment(reviewed):
    root, manifest, path, records, review = reviewed
    scene = review["images"][0]
    scene["boxes"][0]["decision"] = "portrait_or_guide"
    scene["boxes"][1]["decision"] = "hidden_scene_waldo"
    scene["exclusions_reviewed"] = True
    scene["exclusion_polygons"] = [{"id": "diamond", "points": [[50, 0], [100, 40], [50, 80], [0, 40]]}]
    with pytest.raises(AnnotationError, match="containing manual panel"):
        plan_tiles(records[0], scene)
    scene["exclusion_polygons"] = [{"id": "left-panel", "points": [[0, 0], [40, 0], [35, 80], [0, 80]]}]
    result = plan_tiles(records[0], scene, 40, 30)
    assert len(result["kept"]) == 3
    assert len(result["skipped"]) == 6


def test_duplicate_region_ids_rejected_across_shape_types(reviewed):
    root, manifest, path, records, review = reviewed
    scene = review["images"][0]
    scene["exclusion_rectangles"] = [{"id": "panel", "bbox": [0, 0, 40, 80], "reason": "instruction_panel"}]
    scene["exclusion_polygons"] = [{"id": "panel", "points": [[0, 0], [40, 0], [35, 80], [0, 80]], "reason": "instruction_panel"}]
    with pytest.raises(AnnotationError, match="unique across"):
        validate_review(review, records, manifest, root)


def test_explicit_polygon_points_and_display_scaling(reviewed):
    from waldofinder.review_cli import display_point
    root, manifest, path, records, review = reviewed
    assert display_point([25, 20], [100, 40], [1000, 401]) == [250, 200.5]
    assert display_point([-1, 41], [100, 40], [1000, 401]) == [0, 401]
    common = ["--annotations", str(manifest), "--images", str(root), "--reviews", str(path)]
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--shape", "polygon",
          "--points", "0", "0", "40", "0", "35", "80", "0", "80"])
    scene = load_review(path, records, manifest, root)["images"][0]
    assert len(scene["exclusion_polygons"]) == 1


def test_replacement_rejects_concurrent_change_to_same_region(reviewed, monkeypatch):
    root, manifest, path, records, review = reviewed
    common = ["--annotations", str(manifest), "--images", str(root), "--reviews", str(path)]
    main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--box", "0", "0", "40", "80"])

    def change_same_region(image):
        updated = load_review(path, records, manifest, root)
        updated["images"][0]["exclusion_rectangles"][0]["bbox"] = [0, 0, 30, 80]
        save_review(path, updated)
        return [[0, 0], [40, 0], [35, 80], [0, 80]]

    monkeypatch.setattr("waldofinder.review_cli.draw_polygon", change_same_region)
    with pytest.raises(SystemExit):
        main([*common, "exclude", "--scene", "fixture", "--id", "panel", "--shape", "polygon", "--replace"])
    assert load_review(path, records, manifest, root)["images"][0]["exclusion_rectangles"][0]["bbox"] == [0, 0, 30, 80]
