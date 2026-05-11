#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ODM_ROOT=""
ODM_OUTPUT_ROOT=""
ODM_SAMPLE_NAME="mygla"
ODM_ARCHIVE_PATH=""
ODM_SOURCE_URL=""
ODM_DOWNLOAD_DIR=""
DRONESCAPES_ROOT=""
DRONESCAPES_SOURCE_ROOT=""
DRONESCAPES_OUTPUT_ROOT=""
DRONESCAPES_REPO_ID="Meehai/dronescapes"
DRONESCAPES_SPLIT="test_set_annotated_only"
DRONESCAPES_RGB_MODALITY="rgb"
DRONESCAPES_DEPTH_MODALITY="depth_sfm_manual202204"
DRONESCAPES_MAX_FRAMES=0
DRONESCAPES_START_INDEX=0
DRONESCAPES_SCENE_PREFIXES=()
OUTPUT_DIR="$ROOT_DIR/output/real_uav_benchmark"
CONFIG_PATH="$ROOT_DIR/output/real_uav_benchmark/benchmark_real.json"
COLMAP_BIN="${COLMAP_BIN:-$(command -v colmap || true)}"
OPENMVS_BIN_DIR="${OPENMVS_BIN_DIR:-$ROOT_DIR/.external/openMVS_build/bin}"
SKIP_COLMAP_OPENMVS=0
TOP_K_FRAMES=16
RISK_NEIGHBORS=6
COARSE_IMAGE_SIZE=224
REFINE_IMAGE_SIZE=512
COARSE_DEVICE="cpu"
REFINE_DEVICE="cpu"
WINDOW_SIZE=2
BATCH_SIZE=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Real benchmark orchestration for ODMData and/or Dronescapes.

Dataset options:
  --odm-root <path>                    Prepared ODMData sample root
  --odm-output-root <path>             Where to prepare/download one ODMData sample if root is absent
  --odm-sample-name <name>             Bundled sample name (default: mygla)
  --odm-archive-path <path>            Local archive or extracted root for ODMData
  --odm-source-url <url>               Override bundled ODMData source URL
  --odm-download-dir <path>            Cache directory for ODMData downloads
  --dronescapes-root <path>            Prepared Dronescapes export root consumed by the loader
  --dronescapes-source-root <path>     Local clone/root of the official Dronescapes repository
  --dronescapes-output-root <path>     Where to build the prepared Dronescapes export if needed
  --dronescapes-repo-id <repo>         Hugging Face dataset repo (default: Meehai/dronescapes)
  --dronescapes-split <name>           Split name (default: test_set_annotated_only)
  --dronescapes-rgb-modality <name>    RGB modality (default: rgb)
  --dronescapes-depth-modality <name>  Depth modality (default: depth_sfm_manual202204)
  --dronescapes-scene-prefix <prefix>  Repeatable filter for stems/scenes
  --dronescapes-max-frames <int>       Limit export size; use 0 for the full split (default: 0)
  --dronescapes-start-index <int>      Offset after sorting (default: 0)

Benchmark options:
  --output-dir <path>                  Benchmark output root
  --config-path <path>                 Generated config path
  --python-bin <path>                  Python interpreter, ideally the full env
  --colmap-bin <path>                  COLMAP executable
  --openmvs-bin-dir <path>             OpenMVS binary directory
  --skip-colmap-openmvs                Exclude the COLMAP+OpenMVS baseline
  --top-k-frames <int>                 Risk-hybrid refinement budget
  --risk-neighbors <int>               Neighbor count for frame risk
  --coarse-image-size <int>            DUSt3R image size
  --refine-image-size <int>            MASt3R image size
  --coarse-device <cpu|cuda>
  --refine-device <cpu|cuda>
  --window-size <int>
  --batch-size <int>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --odm-root) ODM_ROOT="$2"; shift 2 ;;
    --odm-output-root) ODM_OUTPUT_ROOT="$2"; shift 2 ;;
    --odm-sample-name) ODM_SAMPLE_NAME="$2"; shift 2 ;;
    --odm-archive-path) ODM_ARCHIVE_PATH="$2"; shift 2 ;;
    --odm-source-url) ODM_SOURCE_URL="$2"; shift 2 ;;
    --odm-download-dir) ODM_DOWNLOAD_DIR="$2"; shift 2 ;;
    --dronescapes-root) DRONESCAPES_ROOT="$2"; shift 2 ;;
    --dronescapes-source-root) DRONESCAPES_SOURCE_ROOT="$2"; shift 2 ;;
    --dronescapes-output-root) DRONESCAPES_OUTPUT_ROOT="$2"; shift 2 ;;
    --dronescapes-repo-id) DRONESCAPES_REPO_ID="$2"; shift 2 ;;
    --dronescapes-split) DRONESCAPES_SPLIT="$2"; shift 2 ;;
    --dronescapes-rgb-modality) DRONESCAPES_RGB_MODALITY="$2"; shift 2 ;;
    --dronescapes-depth-modality) DRONESCAPES_DEPTH_MODALITY="$2"; shift 2 ;;
    --dronescapes-scene-prefix) DRONESCAPES_SCENE_PREFIXES+=("$2"); shift 2 ;;
    --dronescapes-max-frames) DRONESCAPES_MAX_FRAMES="$2"; shift 2 ;;
    --dronescapes-start-index) DRONESCAPES_START_INDEX="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --config-path) CONFIG_PATH="$2"; shift 2 ;;
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    --colmap-bin) COLMAP_BIN="$2"; shift 2 ;;
    --openmvs-bin-dir) OPENMVS_BIN_DIR="$2"; shift 2 ;;
    --skip-colmap-openmvs) SKIP_COLMAP_OPENMVS=1; shift 1 ;;
    --top-k-frames) TOP_K_FRAMES="$2"; shift 2 ;;
    --risk-neighbors) RISK_NEIGHBORS="$2"; shift 2 ;;
    --coarse-image-size) COARSE_IMAGE_SIZE="$2"; shift 2 ;;
    --refine-image-size) REFINE_IMAGE_SIZE="$2"; shift 2 ;;
    --coarse-device) COARSE_DEVICE="$2"; shift 2 ;;
    --refine-device) REFINE_DEVICE="$2"; shift 2 ;;
    --window-size) WINDOW_SIZE="$2"; shift 2 ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$ODM_ROOT" && -z "$ODM_OUTPUT_ROOT" && -z "$DRONESCAPES_ROOT" && -z "$DRONESCAPES_OUTPUT_ROOT" ]]; then
  printf 'Provide at least one dataset root/output root.\n' >&2
  usage >&2
  exit 2
fi

if [[ -z "$COLMAP_BIN" && -x "/opt/homebrew/bin/colmap" ]]; then
  COLMAP_BIN="/opt/homebrew/bin/colmap"
fi

if [[ "$SKIP_COLMAP_OPENMVS" != "1" ]]; then
  if [[ ! -x "$OPENMVS_BIN_DIR/InterfaceCOLMAP" || ! -x "$OPENMVS_BIN_DIR/DensifyPointCloud" ]]; then
    printf 'OpenMVS binaries not found under %s. Re-run with --skip-colmap-openmvs or provide --openmvs-bin-dir.\n' "$OPENMVS_BIN_DIR" >&2
    exit 1
  fi
fi

export PYTHONPATH="$ROOT_DIR/src/geo_uav_recon${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "$ODM_ROOT" && -n "$ODM_OUTPUT_ROOT" ]]; then
  ODM_ROOT="$ODM_OUTPUT_ROOT"
  ODM_ARGS=(
    -m geo_uav_recon.cli prepare-odm
    --output-dir "$ODM_OUTPUT_ROOT"
    --sample-name "$ODM_SAMPLE_NAME"
  )
  if [[ -n "$ODM_ARCHIVE_PATH" ]]; then
    ODM_ARGS+=(--archive-path "$ODM_ARCHIVE_PATH")
  fi
  if [[ -n "$ODM_SOURCE_URL" ]]; then
    ODM_ARGS+=(--source-url "$ODM_SOURCE_URL")
  fi
  if [[ -n "$ODM_DOWNLOAD_DIR" ]]; then
    ODM_ARGS+=(--download-dir "$ODM_DOWNLOAD_DIR")
  fi
  "$PYTHON_BIN" "${ODM_ARGS[@]}" >/dev/null
fi

if [[ -z "$DRONESCAPES_ROOT" && -n "$DRONESCAPES_OUTPUT_ROOT" ]]; then
  DRONESCAPES_ROOT="$DRONESCAPES_OUTPUT_ROOT"
  SUBSET_ARGS=(
    -m geo_uav_recon.cli dronescapes-subset
    --output-dir "$DRONESCAPES_OUTPUT_ROOT"
    --repo-id "$DRONESCAPES_REPO_ID"
    --split "$DRONESCAPES_SPLIT"
    --rgb-modality "$DRONESCAPES_RGB_MODALITY"
    --depth-modality "$DRONESCAPES_DEPTH_MODALITY"
    --max-frames "$DRONESCAPES_MAX_FRAMES"
    --start-index "$DRONESCAPES_START_INDEX"
  )
  if [[ -n "$DRONESCAPES_SOURCE_ROOT" ]]; then
    SUBSET_ARGS+=(--local-root "$DRONESCAPES_SOURCE_ROOT")
  fi
  for prefix in "${DRONESCAPES_SCENE_PREFIXES[@]}"; do
    SUBSET_ARGS+=(--scene-prefix "$prefix")
  done
  "$PYTHON_BIN" "${SUBSET_ARGS[@]}" >/dev/null
fi

if [[ -n "$ODM_ROOT" ]]; then
  "$PYTHON_BIN" -m geo_uav_recon.cli validate-dataset --dataset-kind odmdata --dataset-root "$ODM_ROOT" >/dev/null
fi
if [[ -n "$DRONESCAPES_ROOT" ]]; then
  "$PYTHON_BIN" -m geo_uav_recon.cli validate-dataset --dataset-kind dronescapes --dataset-root "$DRONESCAPES_ROOT" >/dev/null
fi

CONFIG_ARGS=(
  -m geo_uav_recon.cli write-real-config
  --config-path "$CONFIG_PATH"
  --output-dir "$OUTPUT_DIR"
  --python-bin "$PYTHON_BIN"
  --colmap-bin "$COLMAP_BIN"
  --top-k-frames "$TOP_K_FRAMES"
  --risk-neighbors "$RISK_NEIGHBORS"
  --coarse-image-size "$COARSE_IMAGE_SIZE"
  --refine-image-size "$REFINE_IMAGE_SIZE"
  --coarse-device "$COARSE_DEVICE"
  --refine-device "$REFINE_DEVICE"
  --window-size "$WINDOW_SIZE"
  --batch-size "$BATCH_SIZE"
)
if [[ -n "$ODM_ROOT" ]]; then
  CONFIG_ARGS+=(--odm-root "$ODM_ROOT")
fi
if [[ -n "$DRONESCAPES_ROOT" ]]; then
  CONFIG_ARGS+=(--dronescapes-root "$DRONESCAPES_ROOT")
fi
if [[ "$SKIP_COLMAP_OPENMVS" == "1" ]]; then
  CONFIG_ARGS+=(--skip-colmap-openmvs)
else
  CONFIG_ARGS+=(--openmvs-bin-dir "$OPENMVS_BIN_DIR")
fi

"$PYTHON_BIN" "${CONFIG_ARGS[@]}" >/dev/null
"$PYTHON_BIN" -m geo_uav_recon.cli benchmark --config "$CONFIG_PATH" --output-dir "$OUTPUT_DIR"

printf '\nArtifacts:\n'
printf '  %s\n' "$OUTPUT_DIR/benchmark_summary.json"
printf '  %s\n' "$OUTPUT_DIR/benchmark_report.html"
