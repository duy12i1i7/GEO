from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from hawkbot_uav_usegeo.benchmark import merge_depths
from hawkbot_uav_usegeo.risk import select_frames


class TestPipeline(unittest.TestCase):
    def _make_odm(self, root: Path) -> None:
        image_dir = root / "images"
        image_dir.mkdir(parents=True)
        for index in range(4):
            Image.new("RGB", (48, 32), color=(index * 20, index * 10, 100)).save(image_dir / f"frame_{index:04d}.jpg")

    def test_selective_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "odm"
            self._make_odm(root)
            outdir = Path(tmp) / "select"
            summary = select_frames("odmdata", str(root), str(outdir), top_k_frames=2)
            self.assertEqual(len(summary["selected_frames"]), 2)
            self.assertTrue((outdir / "selection_summary.json").exists())

    def test_merge_depths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "odm"
            self._make_odm(root)
            source_dir = Path(tmp) / "source"
            refine_dir = Path(tmp) / "refine"
            source_depth = source_dir / "depth"
            refine_depth = refine_dir / "depth"
            source_depth.mkdir(parents=True)
            refine_depth.mkdir(parents=True)
            for index in range(4):
                np.save(source_depth / f"frame_{index:04d}.npy", np.ones((8, 8), dtype=np.float32) * (index + 1))
            np.save(refine_depth / "frame_0001.npy", np.ones((16, 16), dtype=np.float32) * 9)
            frame_list = Path(tmp) / "selected.txt"
            frame_list.write_text("frame_0001\n", encoding="utf-8")
            outdir = Path(tmp) / "merged"
            payload = merge_depths("odmdata", str(root), str(outdir), str(source_depth), str(refine_depth), str(frame_list), 1.23)
            merged = np.load(outdir / "depth" / "frame_0001.npy")
            self.assertEqual(merged.shape, (16, 16))
            self.assertAlmostEqual(float(np.nanmean(merged)), 9.0)
            self.assertTrue(Path(payload["depth_dir"]).exists())
