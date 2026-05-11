#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATASET_KIND="odmdata"
DATASET_ROOT=""
OUTPUT_DIR=""
PYTHON_BIN="${PYTHON_BIN:-python3}"
COLMAP_BIN="${COLMAP_BIN:-$(command -v colmap || true)}"
OPENMVS_BIN_DIR="${OPENMVS_BIN_DIR:-$ROOT_DIR/.external/openMVS_build/bin}"

usage() {
  cat <<EOF
Usage: $(basename "$0") --dataset-root <path> --output-dir <path> [options]

Options:
  --dataset-kind <odmdata|dronescapes>   Dataset kind (default: odmdata)
  --dataset-root <path>                 Dataset root consumed by geo_uav_recon
  --output-dir <path>                   Output directory for COLMAP/OpenMVS artifacts
  --python-bin <path>                   Python interpreter for the benchmark CLI
  --colmap-bin <path>                   COLMAP executable (default: first on PATH)
  --openmvs-bin-dir <path>              Directory containing InterfaceCOLMAP and DensifyPointCloud
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-kind)
      DATASET_KIND="$2"
      shift 2
      ;;
    --dataset-root)
      DATASET_ROOT="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --colmap-bin)
      COLMAP_BIN="$2"
      shift 2
      ;;
    --openmvs-bin-dir)
      OPENMVS_BIN_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$DATASET_ROOT" || -z "$OUTPUT_DIR" ]]; then
  usage >&2
  exit 2
fi

if [[ -z "$COLMAP_BIN" || ! -x "$COLMAP_BIN" ]]; then
  printf 'COLMAP executable not found: %s\n' "$COLMAP_BIN" >&2
  exit 1
fi

INTERFACE_COLMAP="$OPENMVS_BIN_DIR/InterfaceCOLMAP"
DENSIFY_POINT_CLOUD="$OPENMVS_BIN_DIR/DensifyPointCloud"
if [[ ! -x "$INTERFACE_COLMAP" || ! -x "$DENSIFY_POINT_CLOUD" ]]; then
  printf 'OpenMVS binaries not found under: %s\n' "$OPENMVS_BIN_DIR" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src/geo_uav_recon${PYTHONPATH:+:$PYTHONPATH}"

IMAGE_DIR="$("$PYTHON_BIN" - "$DATASET_KIND" "$DATASET_ROOT" <<'PY'
import sys
from pathlib import Path
from geo_uav_recon.dataset import load_dataset

dataset_kind = sys.argv[1]
dataset_root = sys.argv[2]
dataset = load_dataset(dataset_kind, dataset_root, frame_limit=1)
if not dataset.frames:
    raise SystemExit(1)
print(Path(dataset.frames[0].image_path).parent)
PY
)"

if [[ ! -d "$IMAGE_DIR" ]]; then
  printf 'Could not locate an image folder under dataset root: %s\n' "$DATASET_ROOT" >&2
  exit 1
fi

COLMAP_WORKSPACE="$OUTPUT_DIR/colmap_workspace"
COLMAP_SPARSE="$COLMAP_WORKSPACE/sparse"
COLMAP_DENSE="$COLMAP_WORKSPACE/dense"
OPENMVS_WORKSPACE="$OUTPUT_DIR/openmvs"
rm -rf "$COLMAP_WORKSPACE" "$OPENMVS_WORKSPACE" "$OUTPUT_DIR/depth" "$OUTPUT_DIR/point_cloud.xyz" "$OUTPUT_DIR/external_outputs.json"
mkdir -p "$COLMAP_SPARSE" "$COLMAP_DENSE" "$OPENMVS_WORKSPACE"

DATABASE_PATH="$COLMAP_WORKSPACE/database.db"

START_SEC="$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')"

"$COLMAP_BIN" feature_extractor \
  --database_path "$DATABASE_PATH" \
  --image_path "$IMAGE_DIR" \
  --ImageReader.single_camera 1 \
  --ImageReader.camera_model PINHOLE \
  --FeatureExtraction.use_gpu 0 \
  --SiftExtraction.max_num_features 12000

"$COLMAP_BIN" exhaustive_matcher \
  --database_path "$DATABASE_PATH" \
  --FeatureMatching.use_gpu 0

"$COLMAP_BIN" mapper \
  --database_path "$DATABASE_PATH" \
  --image_path "$IMAGE_DIR" \
  --output_path "$COLMAP_SPARSE" \
  --Mapper.init_min_num_inliers 8 \
  --Mapper.abs_pose_min_num_inliers 8 \
  --Mapper.filter_max_reproj_error 4

if [[ ! -d "$COLMAP_SPARSE/0" ]]; then
  printf 'COLMAP mapper did not produce sparse/0 under %s\n' "$COLMAP_SPARSE" >&2
  exit 1
fi

"$COLMAP_BIN" image_undistorter \
  --image_path "$IMAGE_DIR" \
  --input_path "$COLMAP_SPARSE/0" \
  --output_path "$COLMAP_DENSE" \
  --output_type COLMAP

(
  cd "$OPENMVS_WORKSPACE"
  "$INTERFACE_COLMAP" \
    -i "$COLMAP_DENSE" \
    -o scene.mvs \
    --image-folder "$COLMAP_DENSE/images"

  "$DENSIFY_POINT_CLOUD" \
    scene.mvs \
    --resolution-level 1 \
    --estimate-colors 2 \
    --estimate-normals 0 \
    --fusion-filter 2 \
    --number-views 0
)

"$PYTHON_BIN" -m geo_uav_recon.cli colmap-openmvs-export \
  --dataset-kind "$DATASET_KIND" \
  --dataset-root "$DATASET_ROOT" \
  --colmap-workspace "$COLMAP_DENSE" \
  --openmvs-root "$OPENMVS_WORKSPACE" \
  --output-dir "$OUTPUT_DIR" >/dev/null

END_SEC="$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')"
RUNTIME_SEC="$("$PYTHON_BIN" - "$START_SEC" "$END_SEC" <<'PY'
import sys
start = float(sys.argv[1])
end = float(sys.argv[2])
print(f"{end - start:.6f}")
PY
)"

"$PYTHON_BIN" - "$OUTPUT_DIR/external_outputs.json" "$RUNTIME_SEC" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
runtime_sec = float(sys.argv[2])
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
payload["runtime_sec"] = runtime_sec
manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

printf '%s\n' "$OUTPUT_DIR/external_outputs.json"
