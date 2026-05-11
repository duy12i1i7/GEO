from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qs, urlparse

from huggingface_hub import hf_hub_download, list_repo_files
import requests

from .dataset import summarize_dataset, validate_dataset_root


ODM_SAMPLE_SOURCES = {
    "mygla": "https://github.com/merkato/odm_mygla_dataset/archive/refs/heads/master.zip",
    "toledo": "https://github.com/OpenDroneMap/odm_data_toledo/archive/refs/heads/master.zip",
    "shitan_tw": "https://drive.google.com/open?id=1Spu1F713Tw-z1XMdnrlD6NT4EhhFy2Lj",
    "tuniu_tw_1": "https://drive.google.com/open?id=1faBtGK7Jm5lTo_UWLz6onDGYGqlykHPa",
    "waterbury": "https://github.com/OpenDroneMap/odm_data_waterbury/archive/refs/heads/master.zip",
}

ODM_SAMPLE_ALIASES = {
    "shitan": "shitan_tw",
}

ODM_BENCHMARK_SUITES = {
    "recommended": ["mygla", "toledo", "shitan_tw", "tuniu_tw_1"],
    "starter_plus_rtk": ["mygla", "toledo", "tuniu_tw_1"],
}

DRONESCAPES_BENCHMARK_SUITES = {
    "annotated_only": [
        "train_set_annotated_only",
        "validation_set_annotated_only",
        "semisupervised_set_annotated_only",
        "test_set_annotated_only",
    ],
    "all_splits": [
        "train_set",
        "validation_set",
        "semisupervised_set",
        "test_set",
        "train_set_annotated_only",
        "validation_set_annotated_only",
        "semisupervised_set_annotated_only",
        "test_set_annotated_only",
    ],
}


def _is_valid_dataset(dataset_kind: str, dataset_root: Path) -> bool:
    try:
        checks = validate_dataset_root(dataset_kind, str(dataset_root))["checks"]
    except Exception:
        return False
    if dataset_kind == "odmdata":
        return bool(checks["num_frames_gt_0"])
    if dataset_kind == "dronescapes":
        return bool(checks["num_depth_frames_gt_0"])
    return False


def describe_odm_sources() -> dict:
    return {
        "samples": ODM_SAMPLE_SOURCES,
        "aliases": ODM_SAMPLE_ALIASES,
        "suites": ODM_BENCHMARK_SUITES,
        "dronescapes_suites": DRONESCAPES_BENCHMARK_SUITES,
    }


def normalize_odm_sample_name(sample_name: str) -> str:
    normalized = sample_name.strip().lower()
    return ODM_SAMPLE_ALIASES.get(normalized, normalized)


def resolve_odm_benchmark_suite(suite_name: str | Sequence[str]) -> list[str]:
    if isinstance(suite_name, str):
        requested = suite_name.strip().lower()
        if not requested:
            return []
        if requested in ODM_BENCHMARK_SUITES:
            names = ODM_BENCHMARK_SUITES[requested]
        else:
            names = [part.strip() for part in requested.split(",") if part.strip()]
    else:
        names = [str(part).strip() for part in suite_name if str(part).strip()]

    resolved = [normalize_odm_sample_name(name) for name in names]
    unknown = [name for name in resolved if name not in ODM_SAMPLE_SOURCES]
    if unknown:
        raise RuntimeError(f"Unknown ODMData sample(s): {', '.join(sorted(set(unknown)))}")
    return resolved


def resolve_dronescapes_benchmark_suite(suite_name: str | Sequence[str]) -> list[str]:
    if isinstance(suite_name, str):
        requested = suite_name.strip().lower()
        if not requested:
            return []
        if requested in DRONESCAPES_BENCHMARK_SUITES:
            return list(DRONESCAPES_BENCHMARK_SUITES[requested])
        return [part.strip() for part in requested.split(",") if part.strip()]
    return [str(part).strip() for part in suite_name if str(part).strip()]


def _download(url: str, destination: Path) -> Path:
    if "drive.google.com" in url:
        return _download_google_drive(url, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return destination


def _extract_drive_file_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "drive.google.com" not in parsed.netloc:
        return None
    query_id = parse_qs(parsed.query).get("id")
    if query_id:
        return query_id[0]
    match = re.search(r"/d/([^/]+)", parsed.path)
    if match:
        return match.group(1)
    return None


def _drive_confirm_token(response: requests.Response) -> str | None:
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return None
    text = response.text
    match = re.search(r"confirm=([0-9A-Za-z_]+)", text)
    if match:
        return match.group(1)
    match = re.search(r'name="confirm"\s+value="([^"]+)"', text)
    if match:
        return match.group(1)
    return None


def _download_google_drive(url: str, destination: Path) -> Path:
    file_id = _extract_drive_file_id(url)
    if not file_id:
        raise RuntimeError(f"Could not extract Google Drive file id from {url}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    base_url = "https://drive.google.com/uc"
    session = requests.Session()
    params = {"export": "download", "id": file_id}
    response = session.get(base_url, params=params, stream=True, timeout=180)
    token = _drive_confirm_token(response)
    if token:
        response.close()
        params["confirm"] = token
        response = session.get(base_url, params=params, stream=True, timeout=180)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        preview = response.text[:400]
        response.close()
        raise RuntimeError(f"Google Drive did not return a downloadable archive for {url}. Response preview: {preview}")
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    response.close()
    return destination


def _extract_zip(archive_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(output_dir)


def prepare_odm_dataset(
    output_dir: str,
    sample_name: str = "mygla",
    archive_path: str | None = None,
    source_url: str | None = None,
    download_dir: str | None = None,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    resolved_sample_name = normalize_odm_sample_name(sample_name)
    chosen_url = source_url or ODM_SAMPLE_SOURCES.get(resolved_sample_name)
    archive_candidate = Path(archive_path).expanduser() if archive_path else None

    if not _is_valid_dataset("odmdata", output_path):
        if archive_candidate and archive_candidate.is_dir():
            if output_path != archive_candidate:
                if any(output_path.iterdir()):
                    shutil.rmtree(output_path)
                    output_path.mkdir(parents=True, exist_ok=True)
                for child in archive_candidate.iterdir():
                    target = output_path / child.name
                    if child.is_dir():
                        shutil.copytree(child, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(child, target)
        else:
            if archive_candidate and archive_candidate.is_file():
                archive_file = archive_candidate
            else:
                if not chosen_url:
                    raise RuntimeError("No ODMData source URL is available for the requested sample.")
                cache_dir = Path(download_dir) if download_dir else output_path.parent / "downloads"
                parsed = urlparse(chosen_url)
                archive_file = cache_dir / Path(parsed.path).name
                if not archive_file.exists():
                    _download(chosen_url, archive_file)
            _extract_zip(archive_file, output_path)

    summary = summarize_dataset("odmdata", str(output_path))
    payload = {
        "dataset_kind": "odmdata",
        "dataset_root": str(output_path),
        "summary": summary,
        "checks": validate_dataset_root("odmdata", str(output_path))["checks"],
        "prepared": False,
        "sample_name": resolved_sample_name,
        "source_url": chosen_url,
        "output_dir": str(output_path),
    }
    manifest_path = output_path / "prepare_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _copy_frame_pair(rgb_src: Path, depth_src: Path, rgb_out: Path, depth_out: Path) -> None:
    rgb_out.parent.mkdir(parents=True, exist_ok=True)
    depth_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rgb_src, rgb_out)
    shutil.copy2(depth_src, depth_out)


def _collect_local_dronescapes_files(local_root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    rgb_files: dict[str, Path] = {}
    depth_files: dict[str, Path] = {}
    for path in local_root.rglob("*"):
        if path.is_dir():
            continue
        suffix = path.suffix.lower()
        stem = path.stem
        if suffix in {".png", ".jpg", ".jpeg"} and "/rgb" in path.as_posix():
            rgb_files[stem] = path
        if suffix in {".npz", ".npy"} and "/depth" in path.as_posix():
            depth_files[stem] = path
    return rgb_files, depth_files


def export_dronescapes_subset(
    output_dir: str,
    repo_id: str = "Meehai/dronescapes",
    split: str = "test_set_annotated_only",
    rgb_modality: str = "rgb",
    depth_modality: str = "depth_sfm_manual202204",
    scene_prefixes: Sequence[str] | None = None,
    max_frames: int = 0,
    start_index: int = 0,
    local_root: str | None = None,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rgb_out = output_path / "rgb"
    depth_out = output_path / "depth"

    if _is_valid_dataset("dronescapes", output_path):
        selected_stems = sorted(path.stem for path in rgb_out.glob("*"))
    else:
        scene_prefixes = list(scene_prefixes or [])
        if local_root:
            rgb_files, depth_files = _collect_local_dronescapes_files(Path(local_root))
        else:
            repo_files = list_repo_files(repo_id, repo_type="dataset")
            rgb_repo_files = {}
            depth_repo_files = {}
            for file_path in repo_files:
                lower = file_path.lower()
                if split in file_path and rgb_modality in file_path and lower.endswith((".png", ".jpg", ".jpeg")):
                    rgb_repo_files[Path(file_path).stem] = file_path
                if split in file_path and depth_modality in file_path and lower.endswith((".npz", ".npy")):
                    depth_repo_files[Path(file_path).stem] = file_path
            common_stems = sorted(set(rgb_repo_files) & set(depth_repo_files))
            if scene_prefixes:
                common_stems = [stem for stem in common_stems if any(stem.startswith(prefix) for prefix in scene_prefixes)]
            if max_frames and max_frames > 0:
                selected_stems = common_stems[start_index : start_index + max_frames]
            else:
                selected_stems = common_stems[start_index:]
            for stem in selected_stems:
                rgb_cache = Path(hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=rgb_repo_files[stem]))
                depth_cache = Path(hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=depth_repo_files[stem]))
                _copy_frame_pair(rgb_cache, depth_cache, rgb_out / rgb_cache.name, depth_out / depth_cache.name)
            rgb_files = {}
            depth_files = {}
        if local_root:
            common_stems = sorted(set(rgb_files) & set(depth_files))
            if scene_prefixes:
                common_stems = [stem for stem in common_stems if any(stem.startswith(prefix) for prefix in scene_prefixes)]
            if max_frames and max_frames > 0:
                selected_stems = common_stems[start_index : start_index + max_frames]
            else:
                selected_stems = common_stems[start_index:]
            for stem in selected_stems:
                _copy_frame_pair(rgb_files[stem], depth_files[stem], rgb_out / rgb_files[stem].name, depth_out / depth_files[stem].name)

    selection_mode = "full_split" if start_index == 0 and (not max_frames or max_frames <= 0) and not scene_prefixes else "subset"
    payload = {
        "output_dir": str(output_path),
        "repo_id": repo_id,
        "split": split,
        "rgb_modality": rgb_modality,
        "depth_modality": depth_modality,
        "scene_prefixes": list(scene_prefixes or []),
        "max_frames": max_frames,
        "start_index": start_index,
        "selection_mode": selection_mode,
        "local_root": local_root,
        "num_frames": len(selected_stems),
        "frame_stems": selected_stems,
        "dataset_summary": summarize_dataset("dronescapes", str(output_path)),
    }
    (output_path / "subset_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
