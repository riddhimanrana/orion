#!/bin/bash

set -euo pipefail

echo "🚀 Setting up YOLO11N + FastVLM models..."

download_mlpackage_dir() {
  local repo="$1"
  local package_name="$2"
  local target_dir="$3"

  echo "📦 Downloading ${package_name} from ${repo}..."

  python3 - "$repo" "$package_name" "$target_dir" <<'PY'
import json
import urllib.request
from pathlib import Path
import sys

repo = sys.argv[1]
package = sys.argv[2]
target = Path(sys.argv[3])

api = f"https://huggingface.co/api/models/{repo}/tree/main?recursive=1"
with urllib.request.urlopen(api, timeout=60) as r:
    entries = json.loads(r.read().decode("utf-8"))

files = [
    e["path"]
    for e in entries
    if e.get("type") == "file" and e.get("path", "").startswith(package + "/")
]

if not files:
    raise RuntimeError(f"No files found under {package} in {repo}")

if target.exists() and target.is_file():
    target.unlink()
if target.exists() and not target.is_dir():
    raise RuntimeError(f"Target path exists but is not a directory: {target}")
target.mkdir(parents=True, exist_ok=True)

for full_path in files:
    rel = full_path[len(package) + 1 :]
    out = target / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{repo}/resolve/main/{full_path}?download=true"
    with urllib.request.urlopen(url, timeout=180) as r:
        out.write_bytes(r.read())

manifest = target / "Manifest.json"
if not manifest.exists():
    raise RuntimeError(f"Downloaded package missing Manifest.json: {target}")

print(f"✅ {package}: downloaded {len(files)} files to {target}")
PY
}

# YOLO11n CoreML package directory
mkdir -p "Orion Live/Detection/model"
download_mlpackage_dir "riddhimanrana/yolo11n-coreml" "yolo11n.mlpackage" "Orion Live/Detection/model/yolo11n.mlpackage"


# FastVLM CoreML vision tower package directory
mkdir -p "FastVLM/model"
download_mlpackage_dir "riddhimanrana/fastvlm-0.5b-captions" "fastvithd.mlpackage" "FastVLM/model/fastvithd.mlpackage"


# FastVLM text model/tokenizer files
FASTVLM_BASE="https://huggingface.co/riddhimanrana/fastvlm-0.5b-captions/resolve/main"
FASTVLM_FILES=(
  "added_tokens.json"
  "config.json"
  "merges.txt"
  "model.safetensors"
  "model.safetensors.index.json"
  "preprocessor_config.json"
  "processor_config.json"
  "special_tokens_map.json"
  "tokenizer.json"
  "tokenizer_config.json"
  "vocab.json"
)

echo "📦 Downloading FastVLM model files..."
for file in "${FASTVLM_FILES[@]}"; do
  echo "➡️  $file"
  curl -fL "$FASTVLM_BASE/$file" -o "FastVLM/model/$file"
done

echo "✅ All models downloaded successfully."
