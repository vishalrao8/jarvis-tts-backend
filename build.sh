#!/usr/bin/env bash
set -e

echo "=== Installing Python dependencies ==="
pip install --no-cache-dir -r requirements.txt

echo "=== Downloading Standalone Piper Linux Binary ==="
mkdir -p piper
if [ ! -f "piper/piper" ]; then
  curl -sL https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz | tar -xz
  chmod +x piper/piper
fi

echo "=== Downloading J.A.R.V.I.S. Neural ONNX Model and Config ==="
mkdir -p model
if [ ! -f "model/en_GB-jarvis-high.onnx" ]; then
  curl -sL https://huggingface.co/vishalrao8/piper-jarvis-high/resolve/main/en_GB-jarvis-high.onnx -o model/en_GB-jarvis-high.onnx
fi
if [ ! -f "model/en_GB-jarvis-high.onnx.json" ]; then
  curl -sL https://huggingface.co/vishalrao8/piper-jarvis-high/resolve/main/en_GB-jarvis-high.onnx.json -o model/en_GB-jarvis-high.onnx.json
fi

echo "=== Build Complete ==="
