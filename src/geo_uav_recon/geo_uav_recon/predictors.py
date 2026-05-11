from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .dataset import load_dataset


def _load_frame_subset(dataset_kind: str, dataset_root: str, frame_list: str | None = None):
    dataset = load_dataset(dataset_kind, dataset_root)
    selected = None
    if frame_list:
        selected = {line.strip() for line in Path(frame_list).read_text(encoding="utf-8").splitlines() if line.strip()}
    frames = [frame for frame in dataset.frames if selected is None or frame.stem in selected]
    return dataset, frames


def _predict_depths(model_kind: str, model_name: str, frames, all_frames, image_size: int, device: str, batch_size: int):
    if model_kind == "dust3r":
        from dust3r.inference import inference
        from dust3r.model import AsymmetricCroCo3DStereo as ModelClass
        from dust3r.utils.image import load_images
    elif model_kind == "mast3r":
        from dust3r.inference import inference
        from dust3r.utils.image import load_images
        from mast3r.model import AsymmetricMASt3R as ModelClass
    else:
        raise ValueError(f"Unsupported model kind: {model_kind}")

    index_of = {frame.stem: idx for idx, frame in enumerate(all_frames)}
    model = ModelClass.from_pretrained(model_name).to(device)
    model.eval()

    outputs: dict[str, np.ndarray] = {}
    for frame in frames:
        idx = index_of[frame.stem]
        if len(all_frames) == 1:
            partner = all_frames[0]
        elif idx < len(all_frames) - 1:
            partner = all_frames[idx + 1]
        else:
            partner = all_frames[idx - 1]
        images = load_images([frame.image_path, partner.image_path], size=image_size)
        prediction = inference([tuple(images)], model, device, batch_size=batch_size, verbose=False)
        depth = prediction["pred1"]["pts3d"][0, :, :, 2].detach().cpu().numpy().astype(np.float32)
        conf = prediction["pred1"].get("conf")
        if conf is not None:
            confidence = conf[0].detach().cpu().numpy().astype(np.float32)
            depth = np.where(confidence > np.quantile(confidence, 0.1), depth, np.nan)
        depth = np.where(np.isfinite(depth) & (depth > 0), depth, np.nan)
        outputs[frame.stem] = depth
    return outputs


def export_model_depths(
    model_kind: str,
    dataset_kind: str,
    dataset_root: str,
    output_dir: str,
    model_name: str,
    image_size: int,
    device: str,
    window_size: int = 2,
    batch_size: int = 1,
    frame_list: str | None = None,
) -> dict:
    dataset, frames = _load_frame_subset(dataset_kind, dataset_root, frame_list=frame_list)
    outdir = Path(output_dir)
    depth_dir = outdir / "depth"
    depth_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    predictions = _predict_depths(model_kind, model_name, frames, dataset.frames, image_size, device, batch_size)
    runtime_sec = time.perf_counter() - start

    for stem, depth in predictions.items():
        np.save(depth_dir / f"{stem}.npy", depth)

    payload = {
        "depth_dir": str(depth_dir),
        "point_cloud_path": None,
        "runtime_sec": runtime_sec,
        "source_format": "auto",
        "array_key": "depth",
        "component": "auto",
        "metadata": {
            "dataset_kind": dataset_kind,
            "dataset_root": dataset_root,
            "method": model_kind,
            "model_name": model_name,
            "image_size": image_size,
            "window_size": window_size,
            "batch_size": batch_size,
            "frame_list_path": frame_list,
        },
    }
    (outdir / "external_outputs.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
