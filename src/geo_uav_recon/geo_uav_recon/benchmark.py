from __future__ import annotations

import csv
import json
import math
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw
from .dataset import DatasetBundle, load_dataset, load_depth_array


def _relative(path: str | None, root: Path) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except Exception:
        return str(Path(path))


def _resize_depth(depth: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    target_h, target_w = shape
    if depth.shape == shape:
        return depth.astype(np.float32)
    finite = np.isfinite(depth)
    fill_value = float(np.nanmedian(depth[finite])) if np.any(finite) else 0.0
    image = Image.fromarray(np.nan_to_num(depth, nan=fill_value).astype(np.float32), mode="F")
    resized = image.resize((target_w, target_h), Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32)


def _compare_depth_dirs(
    dataset: DatasetBundle,
    predicted_depth_dir: Path,
    reference_depth_dir: Path | None = None,
    scale_align: bool = False,
) -> dict[str, float | int | None]:
    abs_errors = []
    sq_errors = []
    abs_rels = []
    num_valid = 0
    total_valid_gt = 0
    for frame in dataset.frames:
        pred_path = predicted_depth_dir / f"{frame.stem}.npy"
        if not pred_path.exists():
            continue
        pred = load_depth_array(str(pred_path))
        if frame.depth_path:
            ref = load_depth_array(frame.depth_path)
        elif reference_depth_dir:
            ref_path = reference_depth_dir / f"{frame.stem}.npy"
            if not ref_path.exists():
                continue
            ref = load_depth_array(str(ref_path))
        else:
            continue
        pred = _resize_depth(pred, ref.shape)
        ref = np.asarray(ref, dtype=np.float32)
        mask = np.isfinite(pred) & np.isfinite(ref) & (pred > 0) & (ref > 0)
        total_valid_gt += int(np.isfinite(ref).sum())
        if not np.any(mask):
            continue
        pred_valid = pred[mask]
        ref_valid = ref[mask]
        if scale_align:
            scale = float(np.median(ref_valid) / max(np.median(pred_valid), 1e-6))
            pred_valid = pred_valid * scale
        diff = np.abs(pred_valid - ref_valid)
        abs_errors.append(diff)
        sq_errors.append(np.square(diff))
        abs_rels.append(diff / np.maximum(np.abs(ref_valid), 1e-6))
        num_valid += diff.size
    if num_valid == 0:
        return {
            "mae": None,
            "rmse": None,
            "abs_rel": None,
            "valid_ratio": 0.0,
            "num_valid": 0,
        }
    abs_error = np.concatenate(abs_errors)
    sq_error = np.concatenate(sq_errors)
    abs_rel = np.concatenate(abs_rels)
    return {
        "mae": float(np.mean(abs_error)),
        "rmse": float(np.sqrt(np.mean(sq_error))),
        "abs_rel": float(np.mean(abs_rel)),
        "valid_ratio": float(num_valid / max(total_valid_gt, 1)),
        "num_valid": int(num_valid),
    }


def _save_depth_preview(depth_dir: Path, output_path: Path, title: str) -> str | None:
    files = sorted(depth_dir.glob("*.npy"))
    if not files:
        return None
    depth = load_depth_array(str(files[0]))
    finite = depth[np.isfinite(depth)]
    if finite.size == 0:
        finite = np.array([0.0], dtype=np.float32)
    low = float(np.nanpercentile(finite, 5))
    high = float(np.nanpercentile(finite, 95))
    scale = max(high - low, 1e-6)
    normalized = np.clip((np.nan_to_num(depth, nan=low) - low) / scale, 0.0, 1.0)
    image = Image.fromarray(np.uint8(normalized * 255), mode="L").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, 20), fill=(0, 0, 0))
    draw.text((6, 4), f"{title}: {files[0].stem}", fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return str(output_path)


def _save_selection_plot(selection_summary_path: Path, output_path: Path, title: str) -> str | None:
    if not selection_summary_path.exists():
        return None
    selection = json.loads(selection_summary_path.read_text(encoding="utf-8"))
    selected = selection.get("selected_frames", [])
    width = 800
    height = 60 + 24 * max(len(selected), 1)
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height),
        '<rect width="100%%" height="100%%" fill="white"/>',
        f'<text x="10" y="20" font-size="14" font-family="monospace">{title} frame selection</text>',
    ]
    for idx, stem in enumerate(selected):
        y = 48 + idx * 22
        lines.append(f'<text x="18" y="{y}" font-size="12" font-family="monospace">{stem}</text>')
    lines.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def _save_point_cloud_plot(point_cloud_path: Path, output_path: Path) -> str | None:
    if not point_cloud_path.exists():
        return None
    count = 0
    with point_cloud_path.open("r", encoding="utf-8") as handle:
        for count, _ in enumerate(handle, start=1):
            pass
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="100">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="10" y="22" font-size="14" font-family="monospace">point cloud: {point_cloud_path.name}</text>',
        f'<text x="10" y="50" font-size="12" font-family="monospace">points={count}</text>',
        "</svg>",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def _read_openmvs_vertices(ply_path: Path) -> np.ndarray:
    import struct

    with ply_path.open("rb") as handle:
        vertex_count = 0
        while True:
            line = handle.readline()
            if not line:
                raise ValueError(f"Unexpected EOF while reading PLY header: {ply_path}")
            text = line.decode("ascii", errors="ignore").strip()
            if text.startswith("element vertex"):
                vertex_count = int(text.split()[-1])
            if text == "end_header":
                break
        vertices = np.empty((vertex_count, 3), dtype=np.float32)
        for index in range(vertex_count):
            xyz = handle.read(12)
            if len(xyz) != 12:
                raise ValueError(f"PLY vertex block ended early at index {index}")
            vertices[index] = struct.unpack("<fff", xyz)
            handle.read(3)  # rgb
            view_indices_count = handle.read(1)
            if not view_indices_count:
                raise ValueError(f"PLY view_indices count ended early at index {index}")
            count_indices = view_indices_count[0]
            handle.read(count_indices * 4)
            view_weights_count = handle.read(1)
            if not view_weights_count:
                raise ValueError(f"PLY view_weights count ended early at index {index}")
            count_weights = view_weights_count[0]
            handle.read(count_weights * 4)
    return vertices


def _bar_chart(rows: list[tuple[str, float]], metric_name: str, output_path: Path) -> str | None:
    finite_rows = [(label, value) for label, value in rows if value is not None and math.isfinite(value)]
    if not finite_rows:
        return None
    max_value = max(value for _, value in finite_rows) or 1.0
    height = 40 + 28 * len(finite_rows)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="10" y="20" font-size="14" font-family="monospace">{metric_name}</text>',
    ]
    for idx, (label, value) in enumerate(finite_rows):
        y = 48 + idx * 28
        bar_width = 480 * (value / max_value)
        lines.append(f'<text x="10" y="{y}" font-size="12" font-family="monospace">{label}</text>')
        lines.append(f'<rect x="420" y="{y-12}" width="{bar_width:.2f}" height="16" fill="#5b8ff9"/>')
        lines.append(f'<text x="{430 + bar_width:.2f}" y="{y}" font-size="12" font-family="monospace">{value:.4f}</text>')
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def _parse_selection(output_dir: Path) -> list[str]:
    summary_path = output_dir / "selection_summary.json"
    if not summary_path.exists():
        return []
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        return list(payload.get("selected_frames", []))
    except Exception:
        return []


def _project_point_cloud_to_depths(colmap_workspace: Path, point_cloud_path: Path, output_depth_dir: Path) -> int:
    text_model = colmap_workspace / "_text_model"
    cameras_path = text_model / "cameras.txt"
    images_path = text_model / "images.txt"
    vertices = np.loadtxt(point_cloud_path, dtype=np.float32)
    if vertices.ndim == 1:
        vertices = vertices.reshape(1, -1)
    if vertices.size == 0:
        return 0

    def qvec_to_rotmat(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
        return np.array(
            [
                [1 - 2 * qy * qy - 2 * qz * qz, 2 * qx * qy - 2 * qz * qw, 2 * qx * qz + 2 * qy * qw],
                [2 * qx * qy + 2 * qz * qw, 1 - 2 * qx * qx - 2 * qz * qz, 2 * qy * qz - 2 * qx * qw],
                [2 * qx * qz - 2 * qy * qw, 2 * qy * qz + 2 * qx * qw, 1 - 2 * qx * qx - 2 * qy * qy],
            ],
            dtype=np.float32,
        )

    written = 0
    output_depth_dir.mkdir(parents=True, exist_ok=True)
    image_entries = []
    if cameras_path.exists() and images_path.exists():
        camera_tokens = None
        for line in cameras_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            camera_tokens = line.split()
            break
        if not camera_tokens:
            return 0
        _, _, width, height, fx, fy, cx, cy = camera_tokens[:8]
        width = int(width)
        height = int(height)
        fx = float(fx)
        fy = float(fy)
        cx = float(cx)
        cy = float(cy)
        lines = [line for line in images_path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
        for idx in range(0, len(lines), 2):
            tokens = lines[idx].split()
            if len(tokens) < 10:
                continue
            _, qw, qx, qy, qz, tx, ty, tz, _, name = tokens[:10]
            rotation = qvec_to_rotmat(float(qw), float(qx), float(qy), float(qz))
            translation = np.array([float(tx), float(ty), float(tz)], dtype=np.float32)
            image_entries.append((name, width, height, fx, fy, cx, cy, rotation, translation))
    else:
        import pycolmap

        reconstruction = pycolmap.Reconstruction(str(colmap_workspace / "sparse"))
        for image in reconstruction.images.values():
            camera = image.camera
            params = list(camera.params)
            if camera.model_name != "PINHOLE" or len(params) < 4:
                continue
            fx, fy, cx, cy = (float(value) for value in params[:4])
            pose = image.cam_from_world()
            rotation = np.asarray(pose.rotation.matrix(), dtype=np.float32)
            translation = np.asarray(pose.translation, dtype=np.float32)
            image_entries.append((image.name, int(camera.width), int(camera.height), fx, fy, cx, cy, rotation, translation))

    for name, width, height, fx, fy, cx, cy, rotation, translation in image_entries:
        camera_points = vertices @ rotation.T + translation
        valid = camera_points[:, 2] > 1e-6
        camera_points = camera_points[valid]
        if camera_points.size == 0:
            continue
        x = camera_points[:, 0] / camera_points[:, 2]
        y = camera_points[:, 1] / camera_points[:, 2]
        finite_xy = np.isfinite(x) & np.isfinite(y)
        x = x[finite_xy]
        y = y[finite_xy]
        camera_points = camera_points[finite_xy]
        if camera_points.size == 0:
            continue
        u_float = fx * x + cx
        v_float = fy * y + cy
        finite_uv = np.isfinite(u_float) & np.isfinite(v_float)
        u_float = u_float[finite_uv]
        v_float = v_float[finite_uv]
        camera_points = camera_points[finite_uv]
        if camera_points.size == 0:
            continue
        int_bounds = np.iinfo(np.int32)
        safe_uv = (
            (u_float >= int_bounds.min)
            & (u_float <= int_bounds.max)
            & (v_float >= int_bounds.min)
            & (v_float <= int_bounds.max)
        )
        u_float = u_float[safe_uv]
        v_float = v_float[safe_uv]
        camera_points = camera_points[safe_uv]
        if camera_points.size == 0:
            continue
        u = np.round(u_float).astype(np.int32)
        v = np.round(v_float).astype(np.int32)
        inside = (u >= 0) & (u < width) & (v >= 0) & (v < height)
        if not np.any(inside):
            continue
        u = u[inside]
        v = v[inside]
        z = camera_points[inside, 2]
        depth = np.full((height, width), np.nan, dtype=np.float32)
        for uu, vv, zz in zip(u, v, z):
            current = depth[vv, uu]
            if not math.isfinite(float(current)) or zz < current:
                depth[vv, uu] = float(zz)
        np.save(output_depth_dir / f"{Path(name).stem}.npy", depth)
        written += 1
    return written


def export_colmap_openmvs(colmap_workspace: str, openmvs_root: str, output_dir: str, dataset_kind: str, dataset_root: str) -> dict:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    openmvs_path = Path(openmvs_root)
    point_cloud_path = outdir / "point_cloud.xyz"
    scene_ply = openmvs_path / "scene_dense.ply"
    if scene_ply.exists():
        vertices = _read_openmvs_vertices(scene_ply)
        np.savetxt(point_cloud_path, vertices, fmt="%.6f")
    depth_dir = outdir / "depth"
    depth_count = _project_point_cloud_to_depths(Path(colmap_workspace), point_cloud_path, depth_dir) if point_cloud_path.exists() else 0
    payload = {
        "depth_dir": str(depth_dir),
        "point_cloud_path": str(point_cloud_path) if point_cloud_path.exists() else None,
        "runtime_sec": 0.0,
        "source_format": "projected_point_cloud",
        "array_key": "depth",
        "component": "auto",
        "metadata": {
            "dataset_kind": dataset_kind,
            "dataset_root": dataset_root,
            "colmap_workspace": colmap_workspace,
            "openmvs_root": openmvs_root,
            "point_cloud_aligned": False,
            "exported_depth_frames": depth_count,
        },
    }
    (outdir / "external_outputs.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def merge_depths(
    dataset_kind: str,
    dataset_root: str,
    output_dir: str,
    source_depth_dir: str,
    refine_depth_dir: str,
    frame_list: str,
    runtime_sec: float,
) -> dict:
    dataset = load_dataset(dataset_kind, dataset_root)
    outdir = Path(output_dir)
    depth_dir = outdir / "depth"
    depth_dir.mkdir(parents=True, exist_ok=True)
    selected = {line.strip() for line in Path(frame_list).read_text(encoding="utf-8").splitlines() if line.strip()}
    for frame in dataset.frames:
        source = Path(refine_depth_dir) / f"{frame.stem}.npy" if frame.stem in selected else Path(source_depth_dir) / f"{frame.stem}.npy"
        if not source.exists():
            source = Path(source_depth_dir) / f"{frame.stem}.npy"
        if source.exists():
            array = load_depth_array(str(source))
            np.save(depth_dir / f"{frame.stem}.npy", array)
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
            "source_depth_dir": source_depth_dir,
            "refine_depth_dir": refine_depth_dir,
            "frame_list_path": frame_list,
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "external_outputs.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    merge_summary = {
        "dataset": dataset.summary(),
        "output_dir": str(outdir),
        "depth_dir": str(depth_dir),
        "selected_frames_path": frame_list,
        "runtime_sec": runtime_sec,
        "manifest_path": str(outdir / "external_outputs.json"),
    }
    (outdir / "merge_summary.json").write_text(json.dumps(merge_summary, indent=2), encoding="utf-8")
    return payload


def write_real_benchmark_config(
    config_path: str,
    output_dir: str,
    python_bin: str,
    top_k_frames: int,
    risk_neighbors: int,
    coarse_image_size: int,
    refine_image_size: int,
    coarse_device: str,
    refine_device: str,
    window_size: int,
    batch_size: int,
    odm_root: str | None = None,
    odm_roots: Sequence[str] | None = None,
    dronescapes_root: str | None = None,
    dronescapes_roots: Sequence[str] | None = None,
    colmap_bin: str | None = None,
    openmvs_bin_dir: str | None = None,
    skip_colmap_openmvs: bool = False,
    root_dir: str | None = None,
) -> dict:
    root = Path(root_dir or Path(__file__).resolve().parents[3])
    datasets = []
    resolved_odm_roots: list[str] = []
    if odm_roots:
        resolved_odm_roots.extend(str(path) for path in odm_roots if str(path).strip())
    if odm_root:
        resolved_odm_roots.append(odm_root)
    seen_odm_roots: set[str] = set()
    for root_path in resolved_odm_roots:
        if root_path in seen_odm_roots:
            continue
        seen_odm_roots.add(root_path)
        sample_name = Path(root_path).name
        if sample_name.startswith("odmdata_"):
            sample_name = sample_name[len("odmdata_") :]
        safe_sample_name = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in sample_name)
        datasets.append({"name": f"odmdata_{safe_sample_name}_real", "kind": "odmdata", "root": root_path})
    resolved_dronescapes_roots: list[str] = []
    if dronescapes_roots:
        resolved_dronescapes_roots.extend(str(path) for path in dronescapes_roots if str(path).strip())
    if dronescapes_root:
        resolved_dronescapes_roots.append(dronescapes_root)
    seen_dronescapes_roots: set[str] = set()
    for root_path in resolved_dronescapes_roots:
        if root_path in seen_dronescapes_roots:
            continue
        seen_dronescapes_roots.add(root_path)
        split_name = Path(root_path).name
        if split_name.startswith("dronescapes_full_"):
            split_name = split_name[len("dronescapes_full_") :]
        elif split_name.startswith("dronescapes_"):
            split_name = split_name[len("dronescapes_") :]
        safe_split_name = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in split_name)
        dataset_name = "dronescapes_real" if safe_split_name == "test_set_annotated_only" and len(resolved_dronescapes_roots) == 1 else f"dronescapes_{safe_split_name}_real"
        datasets.append({"name": dataset_name, "kind": "dronescapes", "root": root_path})
    methods = []
    if not skip_colmap_openmvs:
        methods.append(
            {
                "name": "colmap_openmvs_real",
                "kind": "command_external",
                "command": f"{root}/scripts/run_colmap_openmvs_baseline.sh --dataset-kind {{dataset_kind}} --dataset-root {{dataset_root}} --output-dir {{output_dir}} --python-bin {python_bin} --colmap-bin {colmap_bin or 'colmap'} --openmvs-bin-dir {openmvs_bin_dir or root / '.external/openMVS_build/bin'}",
            }
        )
    methods.extend(
        [
            {
                "name": "risk_hybrid_real",
                "kind": "command_external",
                "command": f"{root}/scripts/run_risk_hybrid_pipeline.sh --dataset-kind {{dataset_kind}} --dataset-root {{dataset_root}} --output-dir {{output_dir}} --python-bin {python_bin} --top-k-frames {top_k_frames} --risk-neighbors {risk_neighbors} --coarse-image-size {coarse_image_size} --refine-image-size {refine_image_size} --coarse-device {coarse_device} --refine-device {refine_device} --window-size {window_size} --batch-size {batch_size}",
            },
            {
                "name": "dust3r_real",
                "kind": "command_external",
                "command": f"PYTHONPATH={root}/src/geo_uav_recon:{root}/.external/dust3r:{root}/.external/mast3r {python_bin} -m geo_uav_recon.cli dust3r-export --dataset-kind {{dataset_kind}} --dataset-root {{dataset_root}} --output-dir {{output_dir}} --window-size {window_size} --batch-size {batch_size} --image-size {coarse_image_size} --device {coarse_device} --model-name naver/DUSt3R_ViTLarge_BaseDecoder_224_linear",
            },
            {
                "name": "mast3r_real",
                "kind": "command_external",
                "command": f"PYTHONPATH={root}/src/geo_uav_recon:{root}/.external/dust3r:{root}/.external/mast3r {python_bin} -m geo_uav_recon.cli mast3r-export --dataset-kind {{dataset_kind}} --dataset-root {{dataset_root}} --output-dir {{output_dir}} --window-size {window_size} --batch-size {batch_size} --image-size {refine_image_size} --device {refine_device}",
            },
        ]
    )
    payload = {"output_dir": output_dir, "datasets": datasets, "methods": methods}
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def run_benchmark(config_path: str, output_dir: str) -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_results = []
    csv_rows: list[dict[str, Any]] = []

    for dataset_cfg in config["datasets"]:
        dataset = load_dataset(dataset_cfg["kind"], dataset_cfg["root"])
        dataset_out = output_root / dataset_cfg["name"]
        dataset_out.mkdir(parents=True, exist_ok=True)
        method_results = []
        manifests = []
        reference_depth_dir: Path | None = None
        reference_method_name: str | None = None
        has_gt = any(frame.depth_path for frame in dataset.frames)

        for method_cfg in config["methods"]:
            method_out = dataset_out / method_cfg["name"]
            method_out.mkdir(parents=True, exist_ok=True)
            if method_cfg["kind"] == "command_external":
                command = method_cfg["command"].format(
                    dataset_kind=dataset_cfg["kind"],
                    dataset_root=dataset_cfg["root"],
                    output_dir=str(method_out),
                )
                subprocess.run(command, shell=True, check=True, cwd=str(Path(config_path).parent.parent))
            manifest_path = method_out / "external_outputs.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifests.append((method_cfg, method_out, manifest))
            depth_dir = Path(manifest["depth_dir"]) if manifest.get("depth_dir") else None
            depth_files = sorted(depth_dir.glob("*.npy")) if depth_dir and depth_dir.exists() else []
            if not has_gt and depth_files and reference_depth_dir is None:
                if method_cfg["name"].startswith("colmap_openmvs"):
                    reference_depth_dir = depth_dir
                    reference_method_name = method_cfg["name"]
            if depth_files and reference_depth_dir is None and method_cfg["name"].startswith("mast3r"):
                reference_depth_dir = depth_dir
                reference_method_name = method_cfg["name"]

        if not has_gt and reference_depth_dir is None:
            for method_cfg, _, manifest in manifests:
                depth_dir = Path(manifest["depth_dir"]) if manifest.get("depth_dir") else None
                if depth_dir and any(depth_dir.glob("*.npy")):
                    reference_depth_dir = depth_dir
                    reference_method_name = method_cfg["name"]
                    break

        for method_cfg, method_out, manifest in manifests:
            depth_dir = Path(manifest["depth_dir"]) if manifest.get("depth_dir") else None
            point_cloud_path = Path(manifest["point_cloud_path"]) if manifest.get("point_cloud_path") else None
            if has_gt and depth_dir:
                metrics = _compare_depth_dirs(dataset, depth_dir)
            elif depth_dir and reference_depth_dir:
                metrics = _compare_depth_dirs(dataset, depth_dir, reference_depth_dir=reference_depth_dir, scale_align=True)
            else:
                metrics = {"mae": None, "rmse": None, "abs_rel": None, "valid_ratio": 0.0, "num_valid": 0}
            metrics["runtime_sec"] = float(manifest.get("runtime_sec", 0.0))
            selected_frames = _parse_selection(method_out)
            metrics["selected_frames"] = len(selected_frames) if selected_frames else len(dataset.frames)
            metrics["selected_ratio"] = (
                metrics["selected_frames"] / len(dataset.frames) if dataset.frames else 0.0
            )

            visuals = {}
            if depth_dir and depth_dir.exists():
                preview = _save_depth_preview(depth_dir, method_out / "visuals" / "depth_preview.png", method_cfg["name"])
                if preview:
                    visuals["depth_preview"] = _relative(preview, output_root)
            selection = _save_selection_plot(method_out / "selection_summary.json", method_out / "visuals" / "selection.svg", method_cfg["name"])
            if selection:
                visuals["selection"] = _relative(selection, output_root)
            point_viz = _save_point_cloud_plot(point_cloud_path, method_out / "visuals" / "point_cloud.svg") if point_cloud_path else None
            if point_viz:
                visuals["point_cloud"] = _relative(point_viz, output_root)

            method_summary = {
                "method": method_cfg,
                "dataset": dataset.summary(),
                "runtime_sec": metrics["runtime_sec"],
                "selected_frames": selected_frames,
                "depth_dir": str(depth_dir) if depth_dir else None,
                "point_cloud_path": str(point_cloud_path) if point_cloud_path else None,
                "risk_csv": str(method_out / "frame_risks.csv") if (method_out / "frame_risks.csv").exists() else None,
                "reference_method": reference_method_name if not has_gt else None,
            }
            (method_out / "method_summary.json").write_text(json.dumps(method_summary, indent=2), encoding="utf-8")
            method_results.append(
                {
                    "name": method_cfg["name"],
                    "kind": method_cfg["kind"],
                    "depth_dir": _relative(str(depth_dir), output_root) if depth_dir else None,
                    "point_cloud_path": _relative(str(point_cloud_path), output_root) if point_cloud_path else None,
                    "metrics": metrics,
                    "visuals": visuals,
                    "summary": _relative(str(method_out / "method_summary.json"), output_root),
                }
            )
            csv_rows.append(
                {
                    "dataset": dataset_cfg["name"],
                    "method": method_cfg["name"],
                    "mae": metrics["mae"],
                    "rmse": metrics["rmse"],
                    "abs_rel": metrics["abs_rel"],
                    "valid_ratio": metrics["valid_ratio"],
                    "num_valid": metrics["num_valid"],
                    "runtime_sec": metrics["runtime_sec"],
                    "selected_frames": metrics["selected_frames"],
                    "selected_ratio": metrics["selected_ratio"],
                }
            )

        dataset_entry = {
            "dataset_name": dataset_cfg["name"],
            "dataset_type": dataset_cfg["kind"],
            "summary": dataset.summary(),
            "coverage_assets": {},
            "evaluation_mode": "ground_truth" if has_gt else "pseudo_reference",
            "reference_method": reference_method_name if not has_gt else None,
            "methods": method_results,
        }
        dataset_results.append(dataset_entry)

    csv_path = output_root / "benchmark_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["dataset", "method", "mae", "rmse", "abs_rel", "valid_ratio", "num_valid", "runtime_sec", "selected_frames", "selected_ratio"],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    leaderboards = {
        "mae": _relative(_bar_chart([(f"{row['dataset']}/{row['method']}", row["mae"]) for row in csv_rows], "mae", output_root / "leaderboard_mae.svg") or "", output_root),
        "rmse": _relative(_bar_chart([(f"{row['dataset']}/{row['method']}", row["rmse"]) for row in csv_rows], "rmse", output_root / "leaderboard_rmse.svg") or "", output_root),
        "runtime": _relative(_bar_chart([(f"{row['dataset']}/{row['method']}", row["runtime_sec"]) for row in csv_rows], "runtime_sec", output_root / "leaderboard_runtime.svg") or "", output_root),
    }
    leaderboards = {key: value for key, value in leaderboards.items() if value}

    report_lines = [
        "<html><body>",
        "<h1>GEO Benchmark</h1>",
    ]
    for dataset_entry in dataset_results:
        mode = dataset_entry["evaluation_mode"]
        note = ""
        if mode == "pseudo_reference":
            note = f" (pseudo-reference: {dataset_entry['reference_method']})"
        report_lines.append(f"<h2>{dataset_entry['dataset_name']}{note}</h2><ul>")
        for method in dataset_entry["methods"]:
            metrics = method["metrics"]
            report_lines.append(
                f"<li><b>{method['name']}</b>: mae={metrics['mae']}, rmse={metrics['rmse']}, runtime={metrics['runtime_sec']}</li>"
            )
            for label, ref in method["visuals"].items():
                report_lines.append(f'<div><a href="{ref}">{label}</a></div>')
        report_lines.append("</ul>")
    report_lines.append("</body></html>")
    report_path = output_root / "benchmark_report.html"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    summary = {
        "config_path": str(config_path),
        "output_root": str(output_root),
        "datasets": dataset_results,
        "metrics_csv": "benchmark_metrics.csv",
        "leaderboards": leaderboards,
        "benchmark_report": "benchmark_report.html",
    }
    summary_path = output_root / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
