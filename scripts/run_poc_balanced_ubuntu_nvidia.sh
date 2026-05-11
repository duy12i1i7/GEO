#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-geo-uav-recon}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"

THERMAL_SAFE="${THERMAL_SAFE:-1}"
BUILD_JOBS="${BUILD_JOBS:-2}"
WITH_APT="${WITH_APT:-1}"
WITH_OPENMVS="${WITH_OPENMVS:-0}"

ODM_OUTPUT_ROOT="${ODM_OUTPUT_ROOT:-$ROOT_DIR/data/geo_uav_recon/odm_poc_mygla}"
ODM_SAMPLE_NAME="${ODM_SAMPLE_NAME:-mygla}"
DRONESCAPES_OUTPUT_ROOT="${DRONESCAPES_OUTPUT_ROOT:-$ROOT_DIR/data/geo_uav_recon/dronescapes_poc}"
DRONESCAPES_SPLIT="${DRONESCAPES_SPLIT:-test_set_annotated_only}"
DRONESCAPES_MAX_FRAMES="${DRONESCAPES_MAX_FRAMES:-32}"

COARSE_DEVICE="${COARSE_DEVICE:-cuda}"
REFINE_DEVICE="${REFINE_DEVICE:-cuda}"
COARSE_IMAGE_SIZE="${COARSE_IMAGE_SIZE:-224}"
REFINE_IMAGE_SIZE="${REFINE_IMAGE_SIZE:-384}"
BATCH_SIZE="${BATCH_SIZE:-1}"
TOP_K_FRAMES="${TOP_K_FRAMES:-8}"
RISK_NEIGHBORS="${RISK_NEIGHBORS:-4}"

log() {
  printf '[run-poc-balanced] %s\n' "$1"
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  log "Python env missing, running lightweight Ubuntu bootstrap"
  THERMAL_SAFE="$THERMAL_SAFE" \
  BUILD_JOBS="$BUILD_JOBS" \
  WITH_APT="$WITH_APT" \
  WITH_OPENMVS="$WITH_OPENMVS" \
  "$ROOT_DIR/scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'Python interpreter still missing after bootstrap: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

log "running balanced 2-dataset POC benchmark"
exec "$ROOT_DIR/scripts/run_real_uav_benchmark.sh" \
  --python-bin "$PYTHON_BIN" \
  --odm-output-root "$ODM_OUTPUT_ROOT" \
  --odm-sample-name "$ODM_SAMPLE_NAME" \
  --dronescapes-output-root "$DRONESCAPES_OUTPUT_ROOT" \
  --dronescapes-split "$DRONESCAPES_SPLIT" \
  --dronescapes-max-frames "$DRONESCAPES_MAX_FRAMES" \
  --coarse-device "$COARSE_DEVICE" \
  --refine-device "$REFINE_DEVICE" \
  --coarse-image-size "$COARSE_IMAGE_SIZE" \
  --refine-image-size "$REFINE_IMAGE_SIZE" \
  --batch-size "$BATCH_SIZE" \
  --top-k-frames "$TOP_K_FRAMES" \
  --risk-neighbors "$RISK_NEIGHBORS" \
  --skip-colmap-openmvs
