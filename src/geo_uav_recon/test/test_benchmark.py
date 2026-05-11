from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from geo_uav_recon.benchmark import run_benchmark


class TestBenchmark(unittest.TestCase):
    def test_run_benchmark_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_root = root / "dronescapes"
            (dataset_root / "rgb").mkdir(parents=True)
            (dataset_root / "depth").mkdir(parents=True)
            for index in range(2):
                stem = f"scene_{index:04d}"
                Image.new("RGB", (16, 12), color=(index * 50, 0, 0)).save(dataset_root / "rgb" / f"{stem}.png")
                np.savez(dataset_root / "depth" / f"{stem}.npz", np.ones((12, 16), dtype=np.float32) * (index + 1))

            command_script = root / "write_manifest.py"
            command_script.write_text(
                textwrap.dedent(
                    """
                    import json
                    import sys
                    from pathlib import Path
                    import numpy as np

                    dataset_root = Path(sys.argv[1])
                    output_dir = Path(sys.argv[2])
                    depth_dir = output_dir / "depth"
                    depth_dir.mkdir(parents=True, exist_ok=True)
                    for index, path in enumerate(sorted((dataset_root / "rgb").glob("*.png"))):
                        np.save(depth_dir / f"{path.stem}.npy", np.ones((12, 16), dtype=np.float32) * (index + 1))
                    payload = {
                        "depth_dir": str(depth_dir),
                        "point_cloud_path": None,
                        "runtime_sec": 0.5,
                        "source_format": "auto",
                        "array_key": "depth",
                        "component": "auto",
                        "metadata": {"dataset_root": str(dataset_root)},
                    }
                    (output_dir / "external_outputs.json").write_text(json.dumps(payload), encoding="utf-8")
                    """
                ),
                encoding="utf-8",
            )

            config = {
                "output_dir": str(root / "benchmark"),
                "datasets": [{"name": "dronescapes_real", "kind": "dronescapes", "root": str(dataset_root)}],
                "methods": [
                    {
                        "name": "toy_method",
                        "kind": "command_external",
                        "command": f"python3 {command_script} {{dataset_root}} {{output_dir}}",
                    }
                ],
            }
            config_path = root / "benchmark.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            summary = run_benchmark(str(config_path), str(root / "benchmark"))
            self.assertEqual(summary["datasets"][0]["methods"][0]["name"], "toy_method")
            self.assertTrue((root / "benchmark" / "benchmark_summary.json").exists())
