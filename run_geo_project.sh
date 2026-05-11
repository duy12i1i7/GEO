#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_ROOT="$ROOT_DIR/data/geo_uav_recon"
OUTPUT_ROOT="$ROOT_DIR/output/geo_uav_recon"
MODE="full"
ODM_ROOTS=()
ODM_OUTPUT_ROOT=""
ODM_SAMPLE_NAME="mygla"
ODM_BENCHMARK_SUITE=""
ODM_ARCHIVE_PATH=""
ODM_SOURCE_URL=""
ODM_DOWNLOAD_DIR=""
DRONESCAPES_ROOT=""
DRONESCAPES_OUTPUT_ROOT=""
DRONESCAPES_SOURCE_ROOT=""
DRONESCAPES_REPO_ID="Meehai/dronescapes"
DRONESCAPES_SPLIT="test_set_annotated_only"
DRONESCAPES_BENCHMARK_SUITE=""
DRONESCAPES_RGB_MODALITY="rgb"
DRONESCAPES_DEPTH_MODALITY="depth_sfm_manual202204"
PYTHON_BIN=""
AUTO_BOOTSTRAP=1
RUN_TESTS=1
TOP_K_FRAMES=16
RISK_NEIGHBORS=6
COARSE_IMAGE_SIZE=224
REFINE_IMAGE_SIZE=512
COARSE_DEVICE="cpu"
REFINE_DEVICE="cpu"
WINDOW_SIZE=2
BATCH_SIZE=1
DRONESCAPES_MAX_FRAMES=0
DRONESCAPES_START_INDEX=0
DRONESCAPES_SCENE_PREFIXES=()
OUTPUT_DIR="$OUTPUT_ROOT/ready_run"
CONFIG_PATH="$OUTPUT_DIR/benchmark_real.json"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

One-command entrypoint for the GEO UAV reconstruction project.

Modes:
  quick   Uses a compact Dronescapes subset and runs the benchmark.
  full    Default. Runs the real benchmark with the ODMData suite and all Dronescapes splits unless overridden.

Options:
  --mode <quick|full>
  --odm-root <path>                    Repeatable
  --odm-output-root <path>
  --odm-sample-name <name>
  --odm-benchmark-suite <name|csv>
  --odm-archive-path <path>
  --odm-source-url <url>
  --odm-download-dir <path>
  --dronescapes-root <path>
  --dronescapes-output-root <path>
  --dronescapes-source-root <path>
  --dronescapes-repo-id <repo>
  --dronescapes-split <name>
  --dronescapes-benchmark-suite <name|csv>
  --dronescapes-rgb-modality <name>
  --dronescapes-depth-modality <name>
  --python-bin <path>
  --no-bootstrap
  --skip-tests
  --top-k-frames <int>
  --risk-neighbors <int>
  --coarse-image-size <int>
  --refine-image-size <int>
  --coarse-device <cpu|cuda>
  --refine-device <cpu|cuda>
  --window-size <int>
  --batch-size <int>
  --dronescapes-max-frames <int>
  --dronescapes-start-index <int>
  --dronescapes-scene-prefix <prefix>   Repeatable
  --output-dir <path>
  --config-path <path>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --odm-root) ODM_ROOTS+=("$2"); shift 2 ;;
    --odm-output-root) ODM_OUTPUT_ROOT="$2"; shift 2 ;;
    --odm-sample-name) ODM_SAMPLE_NAME="$2"; shift 2 ;;
    --odm-benchmark-suite) ODM_BENCHMARK_SUITE="$2"; shift 2 ;;
    --odm-archive-path) ODM_ARCHIVE_PATH="$2"; shift 2 ;;
    --odm-source-url) ODM_SOURCE_URL="$2"; shift 2 ;;
    --odm-download-dir) ODM_DOWNLOAD_DIR="$2"; shift 2 ;;
    --dronescapes-root) DRONESCAPES_ROOT="$2"; shift 2 ;;
    --dronescapes-output-root) DRONESCAPES_OUTPUT_ROOT="$2"; shift 2 ;;
    --dronescapes-source-root) DRONESCAPES_SOURCE_ROOT="$2"; shift 2 ;;
    --dronescapes-repo-id) DRONESCAPES_REPO_ID="$2"; shift 2 ;;
    --dronescapes-split) DRONESCAPES_SPLIT="$2"; shift 2 ;;
    --dronescapes-benchmark-suite) DRONESCAPES_BENCHMARK_SUITE="$2"; shift 2 ;;
    --dronescapes-rgb-modality) DRONESCAPES_RGB_MODALITY="$2"; shift 2 ;;
    --dronescapes-depth-modality) DRONESCAPES_DEPTH_MODALITY="$2"; shift 2 ;;
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    --no-bootstrap) AUTO_BOOTSTRAP=0; shift 1 ;;
    --skip-tests) RUN_TESTS=0; shift 1 ;;
    --top-k-frames) TOP_K_FRAMES="$2"; shift 2 ;;
    --risk-neighbors) RISK_NEIGHBORS="$2"; shift 2 ;;
    --coarse-image-size) COARSE_IMAGE_SIZE="$2"; shift 2 ;;
    --refine-image-size) REFINE_IMAGE_SIZE="$2"; shift 2 ;;
    --coarse-device) COARSE_DEVICE="$2"; shift 2 ;;
    --refine-device) REFINE_DEVICE="$2"; shift 2 ;;
    --window-size) WINDOW_SIZE="$2"; shift 2 ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --dronescapes-max-frames) DRONESCAPES_MAX_FRAMES="$2"; shift 2 ;;
    --dronescapes-start-index) DRONESCAPES_START_INDEX="$2"; shift 2 ;;
    --dronescapes-scene-prefix) DRONESCAPES_SCENE_PREFIXES+=("$2"); shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --config-path) CONFIG_PATH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "$DATA_ROOT" "$OUTPUT_ROOT"

if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  printf 'Unsupported mode: %s\n' "$MODE" >&2
  usage >&2
  exit 2
fi

if [[ ${#ODM_ROOTS[@]} -gt 0 && -n "$ODM_BENCHMARK_SUITE" ]]; then
  printf 'Use either repeated --odm-root or --odm-benchmark-suite, not both.\n' >&2
  exit 2
fi

if [[ -n "$DRONESCAPES_ROOT" && -n "$DRONESCAPES_BENCHMARK_SUITE" ]]; then
  printf 'Use either --dronescapes-root or --dronescapes-benchmark-suite, not both.\n' >&2
  exit 2
fi

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.micromamba/envs/geo-uav-recon-full/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.micromamba/envs/geo-uav-recon-full/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [[ ! -x "$PYTHON_BIN" && "$PYTHON_BIN" != "python3" ]]; then
  printf 'Python interpreter not found: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.micromamba/envs/geo-uav-recon-full/bin/python" && "$AUTO_BOOTSTRAP" == "1" ]]; then
  if [[ "$MODE" == "full" || ${#ODM_ROOTS[@]} -gt 0 || -n "$ODM_OUTPUT_ROOT" || -n "$ODM_BENCHMARK_SUITE" ]]; then
    WITH_OPENMVS=1 "$ROOT_DIR/scripts/bootstrap_geo_uav_recon_full.sh"
  else
    WITH_OPENMVS=0 "$ROOT_DIR/scripts/bootstrap_geo_uav_recon_full.sh"
  fi
  PYTHON_BIN="$ROOT_DIR/.micromamba/envs/geo-uav-recon-full/bin/python"
fi

if [[ "$MODE" == "full" ]]; then
  if [[ ${#ODM_ROOTS[@]} -eq 0 && -z "$ODM_OUTPUT_ROOT" && -z "$ODM_BENCHMARK_SUITE" ]]; then
    ODM_BENCHMARK_SUITE="recommended"
  fi
  if [[ -z "$DRONESCAPES_ROOT" && -z "$DRONESCAPES_OUTPUT_ROOT" && -z "$DRONESCAPES_BENCHMARK_SUITE" ]]; then
    DRONESCAPES_BENCHMARK_SUITE="all_splits"
  fi
fi

if [[ ${#ODM_ROOTS[@]} -eq 0 && -z "$ODM_OUTPUT_ROOT" && "$MODE" == "full" ]]; then
  if [[ -n "$ODM_BENCHMARK_SUITE" ]]; then
    SUITE_SLUG="$(printf '%s' "$ODM_BENCHMARK_SUITE" | tr ',/' '__' | tr -cs '[:alnum:]_-' '_')"
    ODM_OUTPUT_ROOT="$DATA_ROOT/odm_suite_${SUITE_SLUG}"
  else
    ODM_OUTPUT_ROOT="$DATA_ROOT/odmdata_${ODM_SAMPLE_NAME}"
  fi
fi

if [[ "$AUTO_BOOTSTRAP" == "1" && "$MODE" == "full" ]]; then
  if [[ ! -x "$ROOT_DIR/.external/openMVS_build/bin/InterfaceCOLMAP" || ! -x "$ROOT_DIR/.external/openMVS_build/bin/DensifyPointCloud" ]]; then
    WITH_OPENMVS=1 "$ROOT_DIR/scripts/bootstrap_geo_uav_recon_full.sh"
    PYTHON_BIN="$ROOT_DIR/.micromamba/envs/geo-uav-recon-full/bin/python"
  fi
fi

if [[ "$RUN_TESTS" == "1" ]]; then
  PYTHONPATH="$ROOT_DIR/src/geo_uav_recon" \
    "$PYTHON_BIN" -m unittest discover -s "$ROOT_DIR/src/geo_uav_recon/test" -v >/dev/null
fi

if [[ -z "$DRONESCAPES_ROOT" && -z "$DRONESCAPES_OUTPUT_ROOT" ]]; then
  if [[ "$MODE" == "full" ]]; then
    if [[ -n "$DRONESCAPES_BENCHMARK_SUITE" ]]; then
      DRONESCAPES_OUTPUT_ROOT="$DATA_ROOT/dronescapes_suite_${DRONESCAPES_BENCHMARK_SUITE}"
    else
      DRONESCAPES_ROOT="$DATA_ROOT/dronescapes_full_${DRONESCAPES_SPLIT}"
    fi
  else
    DRONESCAPES_ROOT="$DATA_ROOT/dronescapes_ready_subset"
  fi
fi

if [[ "$MODE" == "quick" && "$DRONESCAPES_MAX_FRAMES" == "0" && ${#DRONESCAPES_SCENE_PREFIXES[@]} -eq 0 ]]; then
  DRONESCAPES_MAX_FRAMES=4
  DRONESCAPES_SCENE_PREFIXES=("barsana")
  TOP_K_FRAMES=2
  RISK_NEIGHBORS=2
fi

REAL_ARGS=(
  "$ROOT_DIR/scripts/run_real_uav_benchmark.sh"
  --dronescapes-repo-id "$DRONESCAPES_REPO_ID"
  --dronescapes-rgb-modality "$DRONESCAPES_RGB_MODALITY"
  --dronescapes-depth-modality "$DRONESCAPES_DEPTH_MODALITY"
  --output-dir "$OUTPUT_DIR"
  --config-path "$CONFIG_PATH"
  --python-bin "$PYTHON_BIN"
  --top-k-frames "$TOP_K_FRAMES"
  --risk-neighbors "$RISK_NEIGHBORS"
  --coarse-device "$COARSE_DEVICE"
  --refine-device "$REFINE_DEVICE"
  --coarse-image-size "$COARSE_IMAGE_SIZE"
  --refine-image-size "$REFINE_IMAGE_SIZE"
  --window-size "$WINDOW_SIZE"
  --batch-size "$BATCH_SIZE"
  --dronescapes-max-frames "$DRONESCAPES_MAX_FRAMES"
  --dronescapes-start-index "$DRONESCAPES_START_INDEX"
)

if [[ -n "$DRONESCAPES_BENCHMARK_SUITE" ]]; then
  REAL_ARGS+=(--dronescapes-output-root "$DRONESCAPES_OUTPUT_ROOT" --dronescapes-benchmark-suite "$DRONESCAPES_BENCHMARK_SUITE")
else
  REAL_ARGS+=(--dronescapes-root "$DRONESCAPES_ROOT" --dronescapes-split "$DRONESCAPES_SPLIT")
fi
for prefix in "${DRONESCAPES_SCENE_PREFIXES[@]}"; do
  [[ -n "$prefix" ]] && REAL_ARGS+=(--dronescapes-scene-prefix "$prefix")
done

if [[ "$MODE" == "full" ]]; then
  if [[ ${#ODM_ROOTS[@]} -gt 0 ]]; then
    for odm_root in "${ODM_ROOTS[@]}"; do
      REAL_ARGS+=(--odm-root "$odm_root")
    done
  else
    REAL_ARGS+=(--odm-output-root "$ODM_OUTPUT_ROOT")
    if [[ -n "$ODM_BENCHMARK_SUITE" ]]; then
      REAL_ARGS+=(--odm-benchmark-suite "$ODM_BENCHMARK_SUITE")
    else
      REAL_ARGS+=(--odm-sample-name "$ODM_SAMPLE_NAME")
      [[ -n "$ODM_ARCHIVE_PATH" ]] && REAL_ARGS+=(--odm-archive-path "$ODM_ARCHIVE_PATH")
      [[ -n "$ODM_SOURCE_URL" ]] && REAL_ARGS+=(--odm-source-url "$ODM_SOURCE_URL")
    fi
    [[ -n "$ODM_DOWNLOAD_DIR" ]] && REAL_ARGS+=(--odm-download-dir "$ODM_DOWNLOAD_DIR")
  fi
else
  REAL_ARGS+=(--skip-colmap-openmvs)
fi

if [[ -n "$DRONESCAPES_BENCHMARK_SUITE" || ! -d "$DRONESCAPES_ROOT" ]]; then
  REAL_ARGS=(
    "$ROOT_DIR/scripts/run_real_uav_benchmark.sh"
    --dronescapes-repo-id "$DRONESCAPES_REPO_ID"
    --dronescapes-rgb-modality "$DRONESCAPES_RGB_MODALITY"
    --dronescapes-depth-modality "$DRONESCAPES_DEPTH_MODALITY"
    --output-dir "$OUTPUT_DIR"
    --config-path "$CONFIG_PATH"
    --python-bin "$PYTHON_BIN"
    --top-k-frames "$TOP_K_FRAMES"
    --risk-neighbors "$RISK_NEIGHBORS"
    --coarse-device "$COARSE_DEVICE"
    --refine-device "$REFINE_DEVICE"
    --coarse-image-size "$COARSE_IMAGE_SIZE"
    --refine-image-size "$REFINE_IMAGE_SIZE"
    --window-size "$WINDOW_SIZE"
    --batch-size "$BATCH_SIZE"
    --dronescapes-max-frames "$DRONESCAPES_MAX_FRAMES"
    --dronescapes-start-index "$DRONESCAPES_START_INDEX"
  )
  if [[ -n "$DRONESCAPES_BENCHMARK_SUITE" ]]; then
    REAL_ARGS+=(--dronescapes-output-root "$DRONESCAPES_OUTPUT_ROOT" --dronescapes-benchmark-suite "$DRONESCAPES_BENCHMARK_SUITE")
  else
    REAL_ARGS+=(
      --dronescapes-output-root "$DRONESCAPES_ROOT"
      --dronescapes-split "$DRONESCAPES_SPLIT"
      --dronescapes-max-frames "$DRONESCAPES_MAX_FRAMES"
      --dronescapes-start-index "$DRONESCAPES_START_INDEX"
    )
  fi
  if [[ -n "$DRONESCAPES_SOURCE_ROOT" ]]; then
    REAL_ARGS+=(--dronescapes-source-root "$DRONESCAPES_SOURCE_ROOT")
  fi
  for prefix in "${DRONESCAPES_SCENE_PREFIXES[@]}"; do
    [[ -n "$prefix" ]] && REAL_ARGS+=(--dronescapes-scene-prefix "$prefix")
  done
  if [[ "$MODE" == "full" ]]; then
    if [[ ${#ODM_ROOTS[@]} -gt 0 ]]; then
      for odm_root in "${ODM_ROOTS[@]}"; do
        REAL_ARGS+=(--odm-root "$odm_root")
      done
    else
      REAL_ARGS+=(--odm-output-root "$ODM_OUTPUT_ROOT")
      if [[ -n "$ODM_BENCHMARK_SUITE" ]]; then
        REAL_ARGS+=(--odm-benchmark-suite "$ODM_BENCHMARK_SUITE")
      else
        REAL_ARGS+=(--odm-sample-name "$ODM_SAMPLE_NAME")
        [[ -n "$ODM_ARCHIVE_PATH" ]] && REAL_ARGS+=(--odm-archive-path "$ODM_ARCHIVE_PATH")
        [[ -n "$ODM_SOURCE_URL" ]] && REAL_ARGS+=(--odm-source-url "$ODM_SOURCE_URL")
      fi
      [[ -n "$ODM_DOWNLOAD_DIR" ]] && REAL_ARGS+=(--odm-download-dir "$ODM_DOWNLOAD_DIR")
    fi
  else
    REAL_ARGS+=(--skip-colmap-openmvs)
  fi
fi

exec "${REAL_ARGS[@]}"
