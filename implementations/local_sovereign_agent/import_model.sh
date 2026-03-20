#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_SRC="${1:-}"
MODEL_NAME="${2:-local-provided}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama CLI not found. Please install ollama first: https://ollama.com/docs"
  exit 1
fi

if [ -z "$MODEL_SRC" ]; then
  echo "Usage: $(basename "$0") <path-to-model-archive-or-dir> [model-name]"
  exit 2
fi

echo "[import_model] Source: $MODEL_SRC  Name: $MODEL_NAME"

TMP_OUT="/tmp/ollama_import_out"
echo "Attempting: ollama import \"$MODEL_SRC\" --name \"$MODEL_NAME\""
if ollama import "$MODEL_SRC" --name "$MODEL_NAME" > "$TMP_OUT" 2>&1; then
  echo "[import_model] Import succeeded (with --name)"
  exit 0
fi

echo "Attempting: ollama import \"$MODEL_SRC\" (no --name)"
if ollama import "$MODEL_SRC" > "$TMP_OUT" 2>&1; then
  echo "[import_model] Import succeeded"
  exit 0
fi

echo "Attempting: ollama pull \"$MODEL_SRC\" (fallback to pull)"
if ollama pull "$MODEL_SRC" > "$TMP_OUT" 2>&1; then
  echo "[import_model] Pull succeeded"
  exit 0
fi

echo "Import failed. See $TMP_OUT for details. If you have a local model archive, try:"
echo "  ollama import /path/to/model.tar --name my-model"
echo "Or place unpacked model files under 'implementations/local_sovereign_agent/models/' and re-run this script."
exit 3
