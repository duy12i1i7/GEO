from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from hawkbot_uav_usegeo.dataset import load_dataset


class TestDatasetLoading(unittest.TestCase):
    def test_load_odmdata_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "odmdata"
            image_dir = root / "sample" / "images"
            image_dir.mkdir(parents=True)
            for index in range(3):
                Image.new("RGB", (32, 24), color=(index * 10, 0, 0)).save(image_dir / f"frame_{index:04d}.jpg")
            dataset = load_dataset("odmdata", str(root))
            self.assertEqual(dataset.dataset_type, "odmdata")
            self.assertEqual(len(dataset.frames), 3)

    def test_load_dronescapes_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dronescapes"
            (root / "rgb").mkdir(parents=True)
            (root / "depth").mkdir(parents=True)
            Image.new("RGB", (32, 24), color=(255, 0, 0)).save(root / "rgb" / "scene_0001.png")
            np.savez(root / "depth" / "scene_0001.npz", np.ones((24, 32), dtype=np.float32))
            dataset = load_dataset("dronescapes", str(root))
            self.assertEqual(dataset.dataset_type, "dronescapes")
            self.assertEqual(len(dataset.frames), 1)
            self.assertIsNotNone(dataset.frames[0].depth_path)
