from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
DEPTH_EXTENSIONS = (".npy", ".npz")


@dataclass
class DatasetFrame:
    stem: str
    image_path: str
    depth_path: str | None = None


@dataclass
class DatasetBundle:
    root: str
    dataset_type: str
    dataset_name: str
    frames: list[DatasetFrame]
    pose_path: str | None = None
    gt_cloud_path: str | None = None
    supports_geometry: bool = False

    def summary(self) -> dict:
        return {
            "root": self.root,
            "dataset_type": self.dataset_type,
            "dataset_name": self.dataset_name,
            "pose_path": self.pose_path,
            "gt_cloud_path": self.gt_cloud_path,
            "num_frames": len(self.frames),
            "num_depth_frames": sum(1 for frame in self.frames if frame.depth_path),
            "supports_geometry": self.supports_geometry,
        }


def _sorted_files(root: Path, extensions: Iterable[str]) -> list[Path]:
    allowed = {ext.lower() for ext in extensions}
    return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() in allowed)


def _find_first_dir_with_images(root: Path) -> Path | None:
    candidates = [root]
    candidates.extend(path for path in root.glob("*") if path.is_dir())
    candidates.extend(path for path in root.glob("*/*") if path.is_dir())
    for candidate in candidates:
        if any(any(candidate.glob(f"*{ext}")) for ext in IMAGE_EXTENSIONS):
            return candidate
    return None


def load_odmdata_dataset(dataset_root: str, frame_limit: int | None = None) -> DatasetBundle:
    root = Path(dataset_root)
    image_dir = root / "images"
    if not image_dir.is_dir():
        image_dir = _find_first_dir_with_images(root)
    if image_dir is None or not image_dir.is_dir():
        raise FileNotFoundError(f"Could not locate an image directory under {root}")
    frames = [
        DatasetFrame(stem=image_path.stem, image_path=str(image_path))
        for image_path in _sorted_files(image_dir, IMAGE_EXTENSIONS)
    ]
    if frame_limit is not None:
        frames = frames[:frame_limit]
    return DatasetBundle(
        root=str(root),
        dataset_type="odmdata",
        dataset_name=root.name,
        frames=frames,
        supports_geometry=False,
    )


def load_dronescapes_dataset(dataset_root: str, frame_limit: int | None = None) -> DatasetBundle:
    root = Path(dataset_root)
    rgb_dir = root / "rgb"
    depth_dir = root / "depth"
    if not rgb_dir.is_dir() or not depth_dir.is_dir():
        raise FileNotFoundError(f"Dronescapes export is missing rgb/ or depth/ under {root}")
    depth_map = {path.stem: path for path in _sorted_files(depth_dir, DEPTH_EXTENSIONS)}
    frames = []
    for image_path in _sorted_files(rgb_dir, IMAGE_EXTENSIONS):
        depth_path = depth_map.get(image_path.stem)
        frames.append(
            DatasetFrame(
                stem=image_path.stem,
                image_path=str(image_path),
                depth_path=str(depth_path) if depth_path else None,
            )
        )
    if frame_limit is not None:
        frames = frames[:frame_limit]
    return DatasetBundle(
        root=str(root),
        dataset_type="dronescapes",
        dataset_name=root.name,
        frames=frames,
        supports_geometry=False,
    )


def load_dataset(dataset_kind: str, dataset_root: str, frame_limit: int | None = None) -> DatasetBundle:
    kind = dataset_kind.strip().lower()
    if kind == "odmdata":
        return load_odmdata_dataset(dataset_root, frame_limit=frame_limit)
    if kind == "dronescapes":
        return load_dronescapes_dataset(dataset_root, frame_limit=frame_limit)
    raise ValueError(f"Unsupported dataset kind: {dataset_kind}")


def summarize_dataset(dataset_kind: str, dataset_root: str) -> dict:
    return load_dataset(dataset_kind, dataset_root).summary()


def validate_dataset_root(dataset_kind: str, dataset_root: str) -> dict:
    dataset = load_dataset(dataset_kind, dataset_root)
    summary = dataset.summary()
    return {
        "dataset_kind": dataset_kind,
        "dataset_root": dataset_root,
        "summary": summary,
        "checks": {
            "dataset_exists": Path(dataset_root).is_dir(),
            "num_frames_gt_0": summary["num_frames"] > 0,
            "num_depth_frames_gt_0": summary["num_depth_frames"] > 0,
            "supports_geometry": summary["supports_geometry"],
        },
    }


def load_depth_array(depth_path: str) -> np.ndarray:
    path = Path(depth_path)
    if path.suffix.lower() == ".npy":
        return np.asarray(np.load(path), dtype=np.float32)
    if path.suffix.lower() == ".npz":
        payload = np.load(path)
        if "depth" in payload.files:
            return np.asarray(payload["depth"], dtype=np.float32)
        if payload.files:
            return np.asarray(payload[payload.files[0]], dtype=np.float32)
    raise ValueError(f"Unsupported depth file: {depth_path}")
