from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from geo_uav_recon.realdata import (
    export_dronescapes_subset,
    prepare_odm_dataset,
    resolve_dronescapes_benchmark_suite,
    resolve_odm_benchmark_suite,
)


class TestRealDataHelpers(unittest.TestCase):
    def test_resolve_odm_benchmark_suite_alias_and_preset(self) -> None:
        self.assertEqual(
            resolve_odm_benchmark_suite("recommended"),
            ["mygla", "toledo", "shitan_tw", "tuniu_tw_1"],
        )
        self.assertEqual(
            resolve_odm_benchmark_suite("mygla,toledo,shitan,tuniu_tw_1"),
            ["mygla", "toledo", "shitan_tw", "tuniu_tw_1"],
        )

    def test_resolve_dronescapes_benchmark_suite(self) -> None:
        self.assertEqual(
            resolve_dronescapes_benchmark_suite("annotated_only"),
            [
                "train_set_annotated_only",
                "validation_set_annotated_only",
                "semisupervised_set_annotated_only",
                "test_set_annotated_only",
            ],
        )
        self.assertEqual(
            resolve_dronescapes_benchmark_suite("test_set,validation_set"),
            ["test_set", "validation_set"],
        )

    def test_prepare_odm_dataset_from_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_root = root / "archive_src" / "sample" / "images"
            archive_root.mkdir(parents=True)
            Image.new("RGB", (32, 24), color=(10, 20, 30)).save(archive_root / "frame_0001.jpg")
            archive_path = root / "sample.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for path in archive_root.parent.parent.rglob("*"):
                    archive.write(path, arcname=path.relative_to(archive_root.parent.parent))
            output_dir = root / "prepared"
            payload = prepare_odm_dataset(str(output_dir), archive_path=str(archive_path))
            self.assertEqual(payload["dataset_kind"], "odmdata")
            self.assertTrue((output_dir / "prepare_manifest.json").exists())

    def test_export_dronescapes_subset_all_frames_from_local_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_root = root / "dronescapes_local" / "test_set_annotated_only"
            rgb_dir = local_root / "rgb"
            depth_dir = local_root / "depth"
            rgb_dir.mkdir(parents=True)
            depth_dir.mkdir(parents=True)
            for index in range(3):
                stem = f"scene_{index:04d}"
                Image.new("RGB", (32, 24), color=(20 * index, 50, 80)).save(rgb_dir / f"{stem}.png")
                np.savez(depth_dir / f"{stem}.npz", depth=np.ones((24, 32), dtype=np.float32) * (index + 1))
            output_dir = root / "prepared"
            payload = export_dronescapes_subset(str(output_dir), local_root=str(root / "dronescapes_local"), max_frames=0)
            self.assertEqual(payload["selection_mode"], "full_split")
            self.assertEqual(payload["num_frames"], 3)
            self.assertTrue((output_dir / "subset_manifest.json").exists())
