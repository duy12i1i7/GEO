#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/src/geo_uav_recon"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-geo-uav-recon}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu124}"
WITH_APT="${WITH_APT:-1}"
WITH_COLMAP="${WITH_COLMAP:-1}"
WITH_OPENMVS="${WITH_OPENMVS:-1}"
USE_SUDO="${USE_SUDO:-1}"
VCPKG_ROOT="${VCPKG_ROOT:-$ROOT_DIR/.external/vcpkg}"
APT_INSTALL="apt-get install -y"
APT_UPDATE="apt-get update"

log() {
  printf '[bootstrap-ubuntu-cuda] %s\n' "$1"
}

run_root() {
  if [[ "$USE_SUDO" == "1" ]] && command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

clone_or_update_repo() {
  local url="$1"
  local target="$2"
  if [[ -d "$target/.git" ]]; then
    log "updating existing repo: $target"
    git -C "$target" pull --ff-only
    git -C "$target" submodule update --init --recursive
  else
    log "cloning repo: $url -> $target"
    git clone --recursive "$url" "$target"
  fi
}

install_apt_deps() {
  log "installing Ubuntu system dependencies"
  run_root bash -lc "$APT_UPDATE"
  run_root bash -lc "$APT_INSTALL software-properties-common curl git build-essential cmake ninja-build pkg-config"
  run_root bash -lc "$APT_INSTALL python3 python3-venv python3-pip"
  run_root bash -lc "$APT_INSTALL autoconf autoconf-archive automake libtool"
  run_root bash -lc "$APT_INSTALL libeigen3-dev libboost-all-dev libopencv-dev"
  run_root bash -lc "$APT_INSTALL libfreeimage-dev libgflags-dev libgoogle-glog-dev"
  run_root bash -lc "$APT_INSTALL libglew-dev libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev"
  run_root bash -lc "$APT_INSTALL libx11-dev libxrandr-dev libxi-dev libxxf86vm-dev libxcursor-dev"
  run_root bash -lc "$APT_INSTALL libcgal-dev libceres-dev libflann-dev qtbase5-dev"
  if [[ "$WITH_COLMAP" == "1" ]]; then
    run_root bash -lc "$APT_INSTALL colmap"
  fi
}

build_openmvs() {
  local openmvs_dir="$ROOT_DIR/.external/openMVS"
  local openmvs_build="$ROOT_DIR/.external/openMVS_build"
  local vcpkg_triplet="x64-linux-geo-release"
  local overlay_triplets_dir="$ROOT_DIR/.external/vcpkg_triplets"
  local triplet_path="$overlay_triplets_dir/$vcpkg_triplet.cmake"
  local openmvs_use_cuda="OFF"
  if [[ "$(uname -m)" == "aarch64" || "$(uname -m)" == "arm64" ]]; then
    vcpkg_triplet="arm64-linux-geo-release"
    triplet_path="$overlay_triplets_dir/$vcpkg_triplet.cmake"
  fi
  if command -v nvcc >/dev/null 2>&1; then
    openmvs_use_cuda="ON"
    log "nvcc detected; enabling CUDA dependency feature for OpenMVS"
  else
    log "nvcc not found; OpenMVS will be built without CUDA acceleration"
  fi
  clone_or_update_repo "https://github.com/cdcseacave/openMVS.git" "$openmvs_dir"
  clone_or_update_repo "https://github.com/microsoft/vcpkg.git" "$VCPKG_ROOT"
  if [[ ! -x "$VCPKG_ROOT/vcpkg" ]]; then
    log "bootstrapping vcpkg"
    VCPKG_DISABLE_METRICS=1 "$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics
  fi
  mkdir -p "$overlay_triplets_dir"
  if [[ "$(uname -m)" == "aarch64" || "$(uname -m)" == "arm64" ]]; then
    cat >"$triplet_path" <<'EOF'
set(VCPKG_TARGET_ARCHITECTURE arm64)
set(VCPKG_CMAKE_SYSTEM_NAME Linux)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_BUILD_TYPE release)
set(VCPKG_C_FLAGS "-mfma")
set(VCPKG_CXX_FLAGS "-mfma")
set(VCPKG_C_FLAGS_RELEASE "-mfma")
set(VCPKG_CXX_FLAGS_RELEASE "-mfma")
EOF
  else
    cat >"$triplet_path" <<'EOF'
set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CMAKE_SYSTEM_NAME Linux)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_BUILD_TYPE release)
set(VCPKG_C_FLAGS "-mfma")
set(VCPKG_CXX_FLAGS "-mfma")
set(VCPKG_C_FLAGS_RELEASE "-mfma")
set(VCPKG_CXX_FLAGS_RELEASE "-mfma")
EOF
  fi
  log "installing OpenMVS manifest dependencies with vcpkg"
  VCPKG_INSTALL_ARGS=(
    "$VCPKG_ROOT/vcpkg"
    install
    "--x-manifest-root=$openmvs_dir"
    "--overlay-triplets=$overlay_triplets_dir"
    "--triplet=$vcpkg_triplet"
  )
  if [[ "$openmvs_use_cuda" == "ON" ]]; then
    VCPKG_INSTALL_ARGS+=("--x-feature=cuda")
  fi
  VCPKG_DISABLE_METRICS=1 "${VCPKG_INSTALL_ARGS[@]}"
  log "configuring OpenMVS with CUDA"
  VCPKG_ROOT="$VCPKG_ROOT" VCPKG_DISABLE_METRICS=1 cmake \
    -S "$openmvs_dir" \
    -B "$openmvs_build" \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" \
    -DVCPKG_OVERLAY_TRIPLETS="$overlay_triplets_dir" \
    -DVCPKG_TARGET_TRIPLET="$vcpkg_triplet" \
    -DVCPKG_MANIFEST_MODE=ON \
    -DVCPKG_MANIFEST_DIR="$openmvs_dir" \
    -DOpenMVS_BUILD_VIEWER=OFF \
    -DOpenMVS_ENABLE_TESTS=OFF \
    -DOpenMVS_USE_CUDA="$openmvs_use_cuda" \
    -DOpenMVS_USE_PYTHON=OFF \
    -DOpenMVS_USE_SIFTGPU=OFF
  log "building OpenMVS"
  cmake --build "$openmvs_build" -j"$(nproc)"
}

log "project root: $ROOT_DIR"
require_cmd git

if [[ "$WITH_APT" == "1" ]]; then
  install_apt_deps
fi

require_cmd cmake
if ! command -v ninja >/dev/null 2>&1 && ! command -v ninja-build >/dev/null 2>&1; then
  printf 'Missing required command: ninja or ninja-build\n' >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf 'Python interpreter not found: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  log "creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  log "venv already exists: $VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

log "upgrading pip/setuptools/wheel"
"$VENV_PY" -m pip install --upgrade pip "setuptools<82" wheel

log "installing project base requirements"
"$VENV_PIP" install -r "$PACKAGE_DIR/requirements/base.txt"

log "installing torch CUDA wheels from $TORCH_INDEX_URL"
"$VENV_PIP" install torch torchvision --index-url "$TORCH_INDEX_URL"

log "installing geo_uav_recon in editable mode"
"$VENV_PIP" install -e "$PACKAGE_DIR"

mkdir -p "$ROOT_DIR/.external"
DUST3R_DIR="$ROOT_DIR/.external/dust3r"
MAST3R_DIR="$ROOT_DIR/.external/mast3r"

clone_or_update_repo "https://github.com/naver/dust3r.git" "$DUST3R_DIR"
clone_or_update_repo "https://github.com/naver/mast3r.git" "$MAST3R_DIR"

log "installing DUSt3R requirements"
"$VENV_PIP" install -r "$DUST3R_DIR/requirements.txt"
if [[ -f "$DUST3R_DIR/requirements_optional.txt" ]]; then
  "$VENV_PIP" install -r "$DUST3R_DIR/requirements_optional.txt" || true
fi

log "installing MASt3R requirements"
"$VENV_PIP" install -r "$MAST3R_DIR/requirements.txt"
"$VENV_PIP" install -r "$MAST3R_DIR/dust3r/requirements.txt"

if [[ "$WITH_OPENMVS" == "1" ]]; then
  build_openmvs
fi

if [[ "$WITH_COLMAP" == "1" ]] && ! command -v colmap >/dev/null 2>&1; then
  printf 'COLMAP is not available in PATH after bootstrap.\n' >&2
  exit 1
fi

log "verifying torch CUDA availability"
"$VENV_PY" - <<'PY'
import torch
print("torch.cuda.is_available =", torch.cuda.is_available())
if torch.cuda.is_available():
    print("torch.cuda.device_count =", torch.cuda.device_count())
    print("torch.cuda.device_name =", torch.cuda.get_device_name(0))
PY

cat <<EOF

Ubuntu + NVIDIA environment ready.

Activate:
  source "$VENV_DIR/bin/activate"

Recommended full run:
  "$ROOT_DIR/run_geo_project.sh" \\
    --no-bootstrap \\
    --python-bin "$VENV_PY" \\
    --coarse-device cuda \\
    --refine-device cuda \\
    --batch-size 4
EOF
