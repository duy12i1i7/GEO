#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/src/hawkbot_uav_usegeo"
MICROMAMBA_ROOT="${MICROMAMBA_ROOT:-$ROOT_DIR/.micromamba}"
ENV_PATH="${ENV_PATH:-$MICROMAMBA_ROOT/envs/uav-usegeo-full}"
WITH_OPENMVS="${WITH_OPENMVS:-0}"
WITH_COLMAP="${WITH_COLMAP:-1}"

log() {
  printf '[bootstrap-full] %s\n' "$1"
}

ensure_brew_formula() {
  local formula="$1"
  if brew list --versions "$formula" >/dev/null 2>&1; then
    log "brew formula already installed: $formula"
  else
    log "installing brew formula: $formula"
    brew install "$formula"
  fi
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

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

log "project root: $ROOT_DIR"
require_cmd brew

ensure_brew_formula micromamba
ensure_brew_formula cmake
ensure_brew_formula ninja
ensure_brew_formula autoconf
ensure_brew_formula autoconf-archive
ensure_brew_formula automake
ensure_brew_formula libtool
if [[ "$WITH_COLMAP" == "1" ]]; then
  ensure_brew_formula colmap
fi

mkdir -p "$MICROMAMBA_ROOT"
MICROMAMBA_BIN="/opt/homebrew/bin/micromamba"
if [[ ! -x "$MICROMAMBA_BIN" ]]; then
  MICROMAMBA_BIN="$(command -v micromamba)"
fi

if [[ ! -d "$ENV_PATH" ]]; then
  log "creating micromamba environment: $ENV_PATH"
  "$MICROMAMBA_BIN" create -y -r "$MICROMAMBA_ROOT" -p "$ENV_PATH" python=3.11 pip
else
  log "micromamba environment already exists: $ENV_PATH"
fi

RUN_IN_ENV=("$MICROMAMBA_BIN" run -r "$MICROMAMBA_ROOT" -p "$ENV_PATH")

log "upgrading pip/setuptools/wheel in full environment"
"${RUN_IN_ENV[@]}" python -m pip install --upgrade pip "setuptools<82" wheel

log "installing project base requirements"
"${RUN_IN_ENV[@]}" python -m pip install -r "$PACKAGE_DIR/requirements/base.txt"

log "installing torch stack"
"${RUN_IN_ENV[@]}" python -m pip install -r "$PACKAGE_DIR/requirements/deep_optional.txt"

log "installing hawkbot_uav_usegeo in editable mode"
"${RUN_IN_ENV[@]}" python -m pip install -e "$PACKAGE_DIR"

mkdir -p "$ROOT_DIR/.external"

DUST3R_DIR="$ROOT_DIR/.external/dust3r"
MAST3R_DIR="$ROOT_DIR/.external/mast3r"
clone_or_update_repo "https://github.com/naver/dust3r.git" "$DUST3R_DIR"
clone_or_update_repo "https://github.com/naver/mast3r.git" "$MAST3R_DIR"

log "installing DUSt3R requirements"
"${RUN_IN_ENV[@]}" python -m pip install -r "$DUST3R_DIR/requirements.txt"
if [[ -f "$DUST3R_DIR/requirements_optional.txt" ]]; then
  "${RUN_IN_ENV[@]}" python -m pip install -r "$DUST3R_DIR/requirements_optional.txt" || true
fi

log "installing MASt3R requirements"
"${RUN_IN_ENV[@]}" python -m pip install -r "$MAST3R_DIR/requirements.txt"
"${RUN_IN_ENV[@]}" python -m pip install -r "$MAST3R_DIR/dust3r/requirements.txt"

if [[ "$WITH_OPENMVS" == "1" ]]; then
  OPENMVS_DIR="$ROOT_DIR/.external/openMVS"
  VCPKG_DIR="$ROOT_DIR/.external/vcpkg"
  OPENMVS_BUILD="$ROOT_DIR/.external/openMVS_build"
  clone_or_update_repo "https://github.com/cdcseacave/openMVS.git" "$OPENMVS_DIR"
  clone_or_update_repo "https://github.com/microsoft/vcpkg.git" "$VCPKG_DIR"
  if [[ ! -x "$VCPKG_DIR/vcpkg" ]]; then
    log "bootstrapping vcpkg"
    VCPKG_DISABLE_METRICS=1 "$VCPKG_DIR/bootstrap-vcpkg.sh" -disableMetrics
  fi
  log "configuring OpenMVS"
  PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH" VCPKG_DISABLE_METRICS=1 cmake \
    -S "$OPENMVS_DIR" \
    -B "$OPENMVS_BUILD" \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_DIR/scripts/buildsystems/vcpkg.cmake" \
    -DVCPKG_TARGET_TRIPLET=arm64-osx \
    -DOpenMVS_BUILD_VIEWER=OFF \
    -DOpenMVS_ENABLE_TESTS=OFF \
    -DOpenMVS_USE_BREAKPAD=OFF \
    -DOpenMVS_USE_CUDA=OFF \
    -DOpenMVS_USE_PYTHON=OFF \
    -DOpenMVS_USE_SIFTGPU=OFF
  log "building OpenMVS"
  PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH" cmake --build "$OPENMVS_BUILD" -j"$(sysctl -n hw.ncpu)"
fi

cat <<EOF

Full environment ready.

Run commands inside the environment with:
  $MICROMAMBA_BIN run -r "$MICROMAMBA_ROOT" -p "$ENV_PATH" <command>

Example:
  $MICROMAMBA_BIN run -r "$MICROMAMBA_ROOT" -p "$ENV_PATH" python -m hawkbot_uav_usegeo.cli --help

Project entrypoint:
  "$ROOT_DIR/run_geo_project.sh"
EOF
