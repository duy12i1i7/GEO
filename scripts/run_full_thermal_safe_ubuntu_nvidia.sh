#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-geo-uav-recon}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"
OPENMVS_BIN_DIR="${OPENMVS_BIN_DIR:-$ROOT_DIR/.external/openMVS_build/bin}"

THERMAL_SAFE="${THERMAL_SAFE:-1}"
BUILD_JOBS="${BUILD_JOBS:-1}"
CPU_THREADS="${CPU_THREADS:-4}"
WITH_APT="${WITH_APT:-1}"
WITH_OPENMVS="${WITH_OPENMVS:-1}"
COARSE_DEVICE="${COARSE_DEVICE:-cuda}"
REFINE_DEVICE="${REFINE_DEVICE:-cuda}"
BATCH_SIZE="${BATCH_SIZE:-2}"
ODM_BENCHMARK_SUITE="${ODM_BENCHMARK_SUITE:-recommended}"
DRONESCAPES_BENCHMARK_SUITE="${DRONESCAPES_BENCHMARK_SUITE:-all_splits}"
TOP_K_FRAMES="${TOP_K_FRAMES:-16}"
RISK_NEIGHBORS="${RISK_NEIGHBORS:-6}"

log() {
  printf '[run-full-thermal-safe] %s\n' "$1"
}

need_bootstrap=0
if [[ ! -x "$PYTHON_BIN" ]]; then
  need_bootstrap=1
fi
if [[ "$WITH_OPENMVS" == "1" ]]; then
  if [[ ! -x "$OPENMVS_BIN_DIR/InterfaceCOLMAP" || ! -x "$OPENMVS_BIN_DIR/DensifyPointCloud" ]]; then
    need_bootstrap=1
  fi
fi

if [[ "$need_bootstrap" == "1" ]]; then
  log "environment or OpenMVS binaries missing, running Ubuntu bootstrap"
  THERMAL_SAFE="$THERMAL_SAFE" \
  BUILD_JOBS="$BUILD_JOBS" \
  WITH_APT="$WITH_APT" \
  WITH_OPENMVS="$WITH_OPENMVS" \
  "$ROOT_DIR/scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'Python interpreter missing after bootstrap: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [[ "$WITH_OPENMVS" == "1" ]]; then
  if [[ ! -x "$OPENMVS_BIN_DIR/InterfaceCOLMAP" || ! -x "$OPENMVS_BIN_DIR/DensifyPointCloud" ]]; then
    printf 'OpenMVS binaries missing after bootstrap: %s\n' "$OPENMVS_BIN_DIR" >&2
    exit 1
  fi
fi

log "running full GEO benchmark with thermal-safe limits"
exec "$ROOT_DIR/run_geo_project.sh" \
  --no-bootstrap \
  --python-bin "$PYTHON_BIN" \
  --thermal-safe \
  --cpu-threads "$CPU_THREADS" \
  --build-jobs "$BUILD_JOBS" \
  --coarse-device "$COARSE_DEVICE" \
  --refine-device "$REFINE_DEVICE" \
  --batch-size "$BATCH_SIZE" \
  --odm-benchmark-suite "$ODM_BENCHMARK_SUITE" \
  --dronescapes-benchmark-suite "$DRONESCAPES_BENCHMARK_SUITE" \
  --top-k-frames "$TOP_K_FRAMES" \
  --risk-neighbors "$RISK_NEIGHBORS"
