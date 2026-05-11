from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image

from .dataset import load_dataset, load_depth_array


def _image_gray(path: str, size: int = 256) -> np.ndarray:
    image = Image.open(path).convert("L")
    image.thumbnail((size, size))
    return np.asarray(image, dtype=np.float32) / 255.0


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return [0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def select_frames(
    dataset_kind: str,
    dataset_root: str,
    output_dir: str,
    top_k_frames: int,
    strategy: str = "risk",
    risk_neighbors: int = 6,
    allow_depth_prior: bool = False,
    random_seed: int = 0,
) -> dict:
    dataset = load_dataset(dataset_kind, dataset_root)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    frames = dataset.frames
    grays = [_image_gray(frame.image_path) for frame in frames]
    texture_raw = [float(np.std(gray)) for gray in grays]
    texture_term = [1.0 - value for value in _minmax(texture_raw)]

    overlap_raw: list[float] = []
    view_raw: list[float] = []
    depth_raw: list[float] = []
    center = max((len(frames) - 1) / 2.0, 1.0)
    for index, gray in enumerate(grays):
        neighbor_scores = []
        radius = max(1, risk_neighbors)
        for offset in range(1, radius + 1):
            for neighbor in (index - offset, index + offset):
                if 0 <= neighbor < len(grays):
                    a = gray.ravel()
                    b = grays[neighbor].ravel()
                    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
                    neighbor_scores.append(float(np.dot(a, b) / denom))
        overlap_raw.append(1.0 - (sum(neighbor_scores) / len(neighbor_scores) if neighbor_scores else 0.0))
        view_raw.append(abs(index - center) / center)
        if allow_depth_prior and frames[index].depth_path:
            depth = load_depth_array(frames[index].depth_path)
            valid = depth[np.isfinite(depth) & (depth > 0)]
            depth_raw.append(float(np.std(valid)) if valid.size else 0.0)
        else:
            depth_raw.append(0.0)

    overlap_term = _minmax(overlap_raw)
    view_term = _minmax(view_raw)
    depth_term = _minmax(depth_raw)
    risk_scores = [
        0.35 * overlap_term[i] + 0.25 * texture_term[i] + 0.20 * depth_term[i] + 0.20 * view_term[i]
        for i in range(len(frames))
    ]

    rows = []
    for index, frame in enumerate(frames):
        rows.append(
            {
                "stem": frame.stem,
                "risk_score": risk_scores[index],
                "texture_term": texture_term[index],
                "overlap_term": overlap_term[index],
                "depth_term": depth_term[index],
                "view_term": view_term[index],
            }
        )

    limit = max(0, min(top_k_frames, len(frames)))
    if strategy == "none":
        selected = []
    elif strategy == "full":
        selected = [frame.stem for frame in frames]
    elif strategy == "random":
        rng = random.Random(random_seed)
        stems = [frame.stem for frame in frames]
        rng.shuffle(stems)
        selected = sorted(stems[:limit])
    else:
        score_key = {
            "texture": "texture_term",
            "overlap": "overlap_term",
            "depth": "depth_term",
            "view": "view_term",
            "risk": "risk_score",
        }.get(strategy, "risk_score")
        selected = [
            row["stem"]
            for row in sorted(rows, key=lambda row: float(row[score_key]), reverse=True)[:limit]
        ]

    selected_set = set(selected)
    csv_path = outdir / "frame_risks.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["stem", "risk_score", "texture_term", "overlap_term", "depth_term", "view_term", "selected"],
        )
        writer.writeheader()
        for row in rows:
            payload = dict(row)
            payload["selected"] = int(row["stem"] in selected_set)
            writer.writerow(payload)

    frame_list_path = outdir / "selected_frames.txt"
    frame_list_path.write_text("\n".join(sorted(selected)), encoding="utf-8")

    summary = {
        "dataset": dataset.summary(),
        "strategy": strategy,
        "top_k_frames": top_k_frames,
        "risk_neighbors": risk_neighbors,
        "selected_frames": sorted(selected),
        "selected_ratio": (len(selected) / len(frames)) if frames else 0.0,
        "frame_list_path": str(frame_list_path),
        "risk_csv": str(csv_path),
    }
    (outdir / "selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
