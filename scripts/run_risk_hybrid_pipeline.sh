#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATASET_KIND="odmdata"
DATASET_ROOT=""
OUTPUT_DIR=""
PYTHON_BIN="${PYTHON_BIN:-python3}"
COARSE_MODEL="naver/DUSt3R_ViTLarge_BaseDecoder_224_linear"
REFINE_MODEL="naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric"
COARSE_IMAGE_SIZE=224
REFINE_IMAGE_SIZE=512
COARSE_DEVICE="cpu"
REFINE_DEVICE="cpu"
WINDOW_SIZE=2
BATCH_SIZE=1
TOP_K_FRAMES=16
RISK_NEIGHBORS=6
STRATEGY="risk"
ALLOW_DEPTH_PRIOR=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --dataset-root <path> --output-dir <path> [options]

Options:
  --dataset-kind <odmdata|dronescapes>
  --dataset-root <path>
  --output-dir <path>
  --python-bin <path>
  --top-k-frames <int>
  --risk-neighbors <int>
  --strategy <risk|random|texture|overlap|depth|full|none>
  --coarse-model <hf-model>
  --refine-model <hf-model>
  --coarse-image-size <int>
  --refine-image-size <int>
  --coarse-device <cpu|cuda>
  --refine-device <cpu|cuda>
  --window-size <int>
  --batch-size <int>
  --allow-depth-prior
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-kind) DATASET_KIND="$2"; shift 2 ;;
    --dataset-root) DATASET_ROOT="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    --top-k-frames) TOP_K_FRAMES="$2"; shift 2 ;;
    --risk-neighbors) RISK_NEIGHBORS="$2"; shift 2 ;;
    --strategy) STRATEGY="$2"; shift 2 ;;
    --coarse-model) COARSE_MODEL="$2"; shift 2 ;;
    --refine-model) REFINE_MODEL="$2"; shift 2 ;;
    --coarse-image-size) COARSE_IMAGE_SIZE="$2"; shift 2 ;;
    --refine-image-size) REFINE_IMAGE_SIZE="$2"; shift 2 ;;
    --coarse-device) COARSE_DEVICE="$2"; shift 2 ;;
    --refine-device) REFINE_DEVICE="$2"; shift 2 ;;
    --window-size) WINDOW_SIZE="$2"; shift 2 ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --allow-depth-prior) ALLOW_DEPTH_PRIOR=1; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$DATASET_ROOT" || -z "$OUTPUT_DIR" ]]; then
  usage >&2
  exit 2
fi

export PYTHONPATH="$ROOT_DIR/src/geo_uav_recon:$ROOT_DIR/.external/dust3r:$ROOT_DIR/.external/mast3r${PYTHONPATH:+:$PYTHONPATH}"

SELECT_DIR="$OUTPUT_DIR/select"
COARSE_DIR="$OUTPUT_DIR/coarse"
REFINE_DIR="$OUTPUT_DIR/refine"
MERGED_DIR="$OUTPUT_DIR/merged"

rm -rf "$SELECT_DIR" "$COARSE_DIR" "$REFINE_DIR" "$MERGED_DIR"
mkdir -p "$SELECT_DIR" "$COARSE_DIR" "$REFINE_DIR" "$MERGED_DIR"

START_SEC="$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')"

SELECT_ARGS=(
  -m geo_uav_recon.cli select-frames
  --dataset-kind "$DATASET_KIND"
  --dataset-root "$DATASET_ROOT"
  --output-dir "$SELECT_DIR"
  --strategy "$STRATEGY"
  --top-k-frames "$TOP_K_FRAMES"
  --risk-neighbors "$RISK_NEIGHBORS"
)
if [[ "$ALLOW_DEPTH_PRIOR" == "1" ]]; then
  SELECT_ARGS+=(--allow-depth-prior)
fi
"$PYTHON_BIN" "${SELECT_ARGS[@]}" >/dev/null

FRAME_LIST="$SELECT_DIR/selected_frames.txt"

"$PYTHON_BIN" -m geo_uav_recon.cli dust3r-export \
  --dataset-kind "$DATASET_KIND" \
  --dataset-root "$DATASET_ROOT" \
  --output-dir "$COARSE_DIR" \
  --window-size "$WINDOW_SIZE" \
  --batch-size "$BATCH_SIZE" \
  --image-size "$COARSE_IMAGE_SIZE" \
  --device "$COARSE_DEVICE" \
  --model-name "$COARSE_MODEL" >/dev/null

"$PYTHON_BIN" -m geo_uav_recon.cli mast3r-export \
  --dataset-kind "$DATASET_KIND" \
  --dataset-root "$DATASET_ROOT" \
  --output-dir "$REFINE_DIR" \
  --window-size "$WINDOW_SIZE" \
  --batch-size "$BATCH_SIZE" \
  --image-size "$REFINE_IMAGE_SIZE" \
  --device "$REFINE_DEVICE" \
  --model-name "$REFINE_MODEL" \
  --frame-list "$FRAME_LIST" >/dev/null

END_SEC="$("$PYTHON_BIN" -c 'import time; print(time.perf_counter())')"
RUNTIME_SEC="$("$PYTHON_BIN" - "$START_SEC" "$END_SEC" <<'PY'
import sys
start = float(sys.argv[1])
end = float(sys.argv[2])
print(f"{end - start:.6f}")
PY
)"

"$PYTHON_BIN" -m geo_uav_recon.cli merge-depths \
  --dataset-kind "$DATASET_KIND" \
  --dataset-root "$DATASET_ROOT" \
  --output-dir "$MERGED_DIR" \
  --source-depth-dir "$COARSE_DIR/depth" \
  --refine-depth-dir "$REFINE_DIR/depth" \
  --frame-list "$FRAME_LIST" \
  --runtime-sec "$RUNTIME_SEC" >/dev/null

cp "$MERGED_DIR/external_outputs.json" "$OUTPUT_DIR/external_outputs.json"
cp "$MERGED_DIR/point_cloud.xyz" "$OUTPUT_DIR/point_cloud.xyz" 2>/dev/null || true
rm -rf "$OUTPUT_DIR/depth"
cp -R "$MERGED_DIR/depth" "$OUTPUT_DIR/depth"
cp "$SELECT_DIR/selection_summary.json" "$OUTPUT_DIR/selection_summary.json"
cp "$MERGED_DIR/merge_summary.json" "$OUTPUT_DIR/merge_summary.json"
cp "$SELECT_DIR/frame_risks.csv" "$OUTPUT_DIR/frame_risks.csv" 2>/dev/null || true

printf '%s\n' "$OUTPUT_DIR/external_outputs.json"
