#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: run_colab_inference.sh --prompt PROMPT [--image IMAGE ...] [--output OUTPUT.mp4] [options]

Run one Google Veo 3.1 video inference on Colab CLI.

Options:
  -p, --prompt PATH         Local UTF-8 prompt text file or prompt string (required)
  -i, --image PATH          Local reference image (optional; up to 3 images)
      --first-frame PATH    First frame image to initiate video motion
      --last-frame PATH     Last frame image to guide video ending
  -o, --output PATH         Output MP4 path (default: veo_output_<timestamp>.mp4)
  -m, --model NAME          Veo model (default: veo-3.1-generate-preview)
  -d, --duration SECS       Video duration in seconds (5-8, default: 5)
  -a, --aspect-ratio RATIO  Aspect ratio: 16:9 or 9:16 (default: 16:9)
  -r, --resolution RES      Resolution: 720p, 1080p, or 4k (default: 1080p)
  -h, --help                Show this help

Environment overrides:
  COLAB_AUTH          CLI auth provider (default: oauth2; adc is also supported)
  COLAB_GPU           Colab GPU model (default: none / CPU)
  COLAB_EXEC_TIMEOUT  Notebook execution timeout in seconds (default: 1200)
  GEMINI_API_KEY      Google GenAI API Key for Veo 3.1
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUNNER="$SCRIPT_DIR/scripts/runner.py"
INPUT_IMAGES=()
FIRST_FRAME=""
LAST_FRAME=""
PROMPT_VAL=""
OUTPUT_TARGET=""
MODEL_NAME="veo-3.1-generate-preview"
DURATION="5"
ASPECT_RATIO="16:9"
RESOLUTION="1080p"

while (($#)); do
  case "$1" in
    -i|--image)
      (($# >= 2)) || { echo "Missing path after $1" >&2; usage >&2; exit 2; }
      INPUT_IMAGES+=("$2")
      shift 2
      ;;
    --first-frame)
      (($# >= 2)) || { echo "Missing path after $1" >&2; usage >&2; exit 2; }
      FIRST_FRAME="$2"
      shift 2
      ;;
    --last-frame)
      (($# >= 2)) || { echo "Missing path after $1" >&2; usage >&2; exit 2; }
      LAST_FRAME="$2"
      shift 2
      ;;
    -p|--prompt)
      (($# >= 2)) || { echo "Missing value after $1" >&2; usage >&2; exit 2; }
      PROMPT_VAL="$2"
      shift 2
      ;;
    -o|--output)
      (($# >= 2)) || { echo "Missing path after $1" >&2; usage >&2; exit 2; }
      OUTPUT_TARGET="$2"
      shift 2
      ;;
    -m|--model)
      (($# >= 2)) || { echo "Missing value after $1" >&2; usage >&2; exit 2; }
      MODEL_NAME="$2"
      shift 2
      ;;
    -d|--duration)
      (($# >= 2)) || { echo "Missing value after $1" >&2; usage >&2; exit 2; }
      DURATION="$2"
      shift 2
      ;;
    -a|--aspect-ratio)
      (($# >= 2)) || { echo "Missing value after $1" >&2; usage >&2; exit 2; }
      ASPECT_RATIO="$2"
      shift 2
      ;;
    -r|--resolution)
      (($# >= 2)) || { echo "Missing value after $1" >&2; usage >&2; exit 2; }
      RESOLUTION="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PROMPT_VAL" ]]; then
  echo "Prompt is required; pass it with --prompt." >&2
  usage >&2
  exit 2
fi

if ((${#INPUT_IMAGES[@]} > 3)); then
  echo "Veo 3.1 supports up to 3 reference images with --image." >&2
  exit 2
fi

[[ -f "$RUNNER" ]] || { echo "Bundled runner not found: $RUNNER" >&2; exit 2; }
command -v colab >/dev/null 2>&1 || { echo "Colab CLI is missing. Install it with: uv tool install google-colab-cli" >&2; exit 127; }

EXEC_TIMEOUT="${COLAB_EXEC_TIMEOUT:-1200}"
COLAB_GPU_CHOICE="${COLAB_GPU:-none}"

ARGS=(single --prompt "$PROMPT_VAL" --model "$MODEL_NAME" --duration "$DURATION" --aspect-ratio "$ASPECT_RATIO" --resolution "$RESOLUTION" --timeout "$EXEC_TIMEOUT" --gpu "$COLAB_GPU_CHOICE")

for input_path in "${INPUT_IMAGES[@]}"; do
  ARGS+=(-i "$input_path")
done

if [[ -n "$FIRST_FRAME" ]]; then ARGS+=(--first-frame "$FIRST_FRAME"); fi
if [[ -n "$LAST_FRAME" ]]; then ARGS+=(--last-frame "$LAST_FRAME"); fi
if [[ -n "$OUTPUT_TARGET" ]]; then ARGS+=(-o "$OUTPUT_TARGET"); fi

exec python3 "$RUNNER" "${ARGS[@]}"
