"""TorchVision detection input contract, preserving original resolution."""

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision.transforms.functional import pil_to_tensor

from .annotations import image_path, load_annotations


class WaldoDataset(Dataset):
    """Return a float RGB image [C,H,W] in [0,1] and detection targets.

    Validation runs at construction. Do not edit images/annotations while using
    the dataset. No resize, normalization, augmentation, or device transfer is
    applied; any future geometric transform must update boxes as well.
    """

    def __init__(self, annotation_file, image_root):
        self.image_root = Path(image_root)
        self.records = load_annotations(annotation_file, self.image_root)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        with Image.open(image_path(self.image_root, record["file_name"])) as image:
            tensor = pil_to_tensor(image.convert("RGB")).to(torch.float32).div_(255)
        boxes = torch.tensor(record["boxes"], dtype=torch.float32).reshape(-1, 4)
        count = len(boxes)
        target = {
            "boxes": boxes,
            "labels": torch.ones(count, dtype=torch.int64),
            "image_id": torch.tensor(index, dtype=torch.int64),
            "area": (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]),
            "iscrowd": torch.zeros(count, dtype=torch.int64),
        }
        return tensor, target


def collate_fn(batch):
    """Keep variable-size images and variable-count targets in separate lists."""
    images, targets = zip(*batch)
    return list(images), list(targets)
