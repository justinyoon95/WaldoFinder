"""Temporary geometric fixtures test software only, never Waldo training data."""

import json

import pytest
import torch
from PIL import Image
from torch.utils.data import DataLoader

from waldofinder.annotations import AnnotationError, load_annotations
from waldofinder.cli import render_record, validate_main, visualize_main
from waldofinder.dataset import WaldoDataset, collate_fn


@pytest.fixture
def sample(tmp_path):
    # Generated only in pytest's temporary directory; no claim of Waldo identity.
    root = tmp_path / "images"
    root.mkdir()
    Image.new("RGB", (40, 30), "white").save(root / "fixture.png")
    manifest = tmp_path / "annotations.json"
    record = {"file_name": "fixture.png", "width": 40, "height": 30,
              "boxes": [[5, 6, 20, 25]]}
    return root, manifest, record


def write(manifest, records):
    manifest.write_text(json.dumps({"version": 1, "images": records}))


def test_dataset_contract_and_variable_batch(sample):
    root, manifest, record = sample
    Image.new("L", (15, 10), 128).save(root / "negative.png")
    negative = {"file_name": "negative.png", "width": 15, "height": 10, "boxes": []}
    write(manifest, [record, negative])
    dataset = WaldoDataset(manifest, root)
    images, targets = next(iter(DataLoader(dataset, batch_size=2, collate_fn=collate_fn)))
    assert [tuple(image.shape) for image in images] == [(3, 30, 40), (3, 10, 15)]
    assert images[0].dtype == torch.float32
    assert images[0].min() >= 0 and images[0].max() <= 1
    assert targets[0]["boxes"].dtype == torch.float32
    assert targets[0]["boxes"].tolist() == record["boxes"]
    assert targets[0]["labels"].dtype == torch.int64
    assert targets[0]["labels"].tolist() == [1]
    assert targets[0]["area"].tolist() == [285]
    assert targets[0]["iscrowd"].tolist() == [0]
    assert targets[1]["image_id"].item() == 1
    assert targets[1]["boxes"].shape == (0, 4)
    assert targets[1]["labels"].shape == (0,)
    assert targets[1]["area"].shape == (0,)


@pytest.mark.parametrize("boxes", [
    [[-1, 0, 10, 10]], [[0, 0, 41, 10]], [[0, 0, 10, 31]],
    [[5, 0, 5, 10]], [[10, 0, 5, 10]], [[0, 0, float("nan"), 10]],
    [[0, 0, float("inf"), 10]], [[False, 0, 10, 10]], [[0, 0, 10]], "unfinished",
])
def test_reject_bad_boxes(sample, boxes):
    root, manifest, record = sample
    record["boxes"] = boxes
    write(manifest, [record])
    with pytest.raises(AnnotationError, match="boxes"):
        load_annotations(manifest, root)


@pytest.mark.parametrize("field,value,match", [
    ("width", 41, "actual"), ("height", True, "positive integers"),
    ("file_name", "missing.png", "images\\[0\\]"),
    ("file_name", "../outside.png", "inside"),
    ("file_name", "/tmp/outside.png", "relative"),
    ("extra_field", 1, "exactly"),
])
def test_reject_bad_records(sample, field, value, match):
    root, manifest, record = sample
    record[field] = value
    write(manifest, [record])
    with pytest.raises(AnnotationError, match=match):
        load_annotations(manifest, root)


def test_duplicate_and_empty_manifest(sample):
    root, manifest, record = sample
    write(manifest, [record, record])
    with pytest.raises(AnnotationError, match="duplicate"):
        load_annotations(manifest, root)
    write(manifest, [])
    with pytest.raises(AnnotationError, match="nonempty"):
        load_annotations(manifest, root)
    manifest.write_text("{broken")
    with pytest.raises(AnnotationError, match="JSON"):
        load_annotations(manifest, root)


def test_corrupt_image_and_orientation(sample):
    root, manifest, record = sample
    write(manifest, [record])
    (root / "fixture.png").write_bytes(b"not an image")
    with pytest.raises(AnnotationError):
        load_annotations(manifest, root)
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 30)).save(root / "fixture.png", exif=exif)
    with pytest.raises(AnnotationError, match="orientation"):
        load_annotations(manifest, root)


def test_boundary_boxes_and_overlay_do_not_change_source(sample):
    root, manifest, record = sample
    record["boxes"] = [[0, 0, 40, 30]]
    write(manifest, [record])
    load_annotations(manifest, root)
    before = (root / "fixture.png").read_bytes()
    overlay = render_record(record, root)
    assert overlay.size == (40, 30)
    assert overlay.getpixel((0, 29)) == (255, 0, 0)
    assert (root / "fixture.png").read_bytes() == before


def test_fractional_box_at_image_edge(sample):
    root, manifest, record = sample
    record["boxes"] = [[39.8, 29.8, 40, 30]]
    write(manifest, [record])
    load_annotations(manifest, root)
    assert render_record(record, root).getpixel((39, 29)) == (255, 0, 0)


def test_cli_validation_and_visualization(sample, monkeypatch, capsys):
    root, manifest, record = sample
    write(manifest, [record])
    common = ["--annotations", str(manifest), "--images", str(root)]
    monkeypatch.setattr("sys.argv", ["waldo-validate", *common])
    validate_main()
    assert "1 Waldo boxes" in capsys.readouterr().out
    output = manifest.parent / "preview.png"
    monkeypatch.setattr("sys.argv", ["waldo-visualize", *common, "--output", str(output)])
    visualize_main()
    with Image.open(output) as image:
        assert image.size == (40, 30)
    monkeypatch.setattr("sys.argv", ["waldo-visualize", *common, "--output", str(root / "fixture.png")])
    with pytest.raises(SystemExit) as exc:
        visualize_main()
    assert exc.value.code == 2
