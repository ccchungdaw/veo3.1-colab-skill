#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Install the Google Veo 3.1 Colab skill into Gemini CLI and/or Codex skills directory.

Usage:
  ./install.sh [--gemini] [--codex] [--all] [--dest DIR] [--force]

Targets:
  --gemini      Install to Gemini CLI (~/.gemini/skills) [Default]
  --codex       Install to Codex (~/.codex/skills)
  --all         Install to both Gemini CLI and Codex
  --dest DIR    Install to a custom directory

Options:
  --force       Replace existing install after creating a backup
  -h, --help    Show this help
EOF
}

SKILL_NAME="veo3.1-colab"
REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TARGET="gemini"
FORCE=0
CUSTOM_DEST=""

while (($#)); do
  case "$1" in
    --gemini) TARGET="gemini"; shift ;;
    --codex) TARGET="codex"; shift ;;
    --all) TARGET="all"; shift ;;
    --dest)
      (($# >= 2)) || { echo "Missing directory after --dest" >&2; exit 2; }
      CUSTOM_DEST="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# Check required files
for req in "SKILL.md" "scripts/runner.py" "assets/Veo_3_1_Colab.ipynb"; do
  [[ -f "$REPO_DIR/$req" ]] || { echo "Repository is missing required file: $req" >&2; exit 2; }
done

install_to() {
  local root_dir="$1"
  local label="$2"
  local target_path="$root_dir/$SKILL_NAME"
  local backup_path=""

  mkdir -p "$root_dir"

  if [[ -d "$target_path" ]]; then
    if (( ! FORCE )); then
      echo "[$label] Skill already installed; preserving: $target_path"
      echo "       Use --force to replace it."
      return 0
    fi
    local ts
    ts="$(date -u +"%Y%m%dT%H%M%SZ")"
    backup_path="$target_path.backup.$ts"
    mv "$target_path" "$backup_path"
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t 'veo_install')"

  cp "$REPO_DIR/SKILL.md" "$tmp_dir/"
  cp -R "$REPO_DIR/scripts" "$tmp_dir/"
  cp -R "$REPO_DIR/assets" "$tmp_dir/"

  find "$tmp_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

  mv "$tmp_dir" "$target_path"
  echo "[$label] Installed $SKILL_NAME to: $target_path"
  if [[ -n "$backup_path" ]]; then
    echo "       Previous installation preserved at: $backup_path"
  fi
}

if [[ -n "$CUSTOM_DEST" ]]; then
  install_to "$CUSTOM_DEST" "Custom"
  exit 0
fi

GEMINI_SKILLS="${GEMINI_HOME:-$HOME/.gemini}/skills"
CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"

case "$TARGET" in
  gemini) install_to "$GEMINI_SKILLS" "Gemini CLI" ;;
  codex) install_to "$CODEX_SKILLS" "Codex" ;;
  all)
    install_to "$GEMINI_SKILLS" "Gemini CLI"
    install_to "$CODEX_SKILLS" "Codex"
    ;;
esac
