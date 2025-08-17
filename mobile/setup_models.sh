#!/bin/bash

set -e  # Exit on first error

echo "🚀 Setting up YOLO11N + FastVLM models..."

# YOLO11n CoreML
YOLO_URL="https://huggingface.co/riddhimanrana/yolo11n-coreml/resolve/main/yolo11n.mlpackage"

mkdir -p Orion\ Live/Detection/model
echo "📦 Downloading YOLOv11n CoreML model..."
curl -L "$YOLO_URL" -o Orion\ Live/Detection/model/yolo11n.mlpackage


# FastVLM Model Files
FASTVLM_BASE="https://huggingface.co/riddhimanrana/fastvlm-0.5b-captions/resolve/main"
FASTVLM_FILES=(
  "fastvithd.mlpackage"
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

mkdir -p FastVLM/model
echo "📦 Downloading FastVLM model files..."
for file in "${FASTVLM_FILES[@]}"; do
  echo "➡️  $file"
  curl -L "$FASTVLM_BASE/$file" -o "FastVLM/model/$file"
done

echo "✅ All models downloaded successfully."
