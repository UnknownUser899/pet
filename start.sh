#!/usr/bin/env bash
cd "$(dirname "$0")"
MODEL=$(ls models/*.gguf 2>/dev/null | head -n1)
if [ -z "$MODEL" ]; then
  echo "No .gguf model found in ./models — see README.md"
  exit 1
fi
if [ ! -x "./bin/llama-server" ]; then
  echo "llama-server binary not found (or not executable) in ./bin — see README.md"
  exit 1
fi
echo "starting model server: $MODEL"
./bin/llama-server -m "$MODEL" -c 8192 --port 8080 &
LLAMA_PID=$!
trap "kill $LLAMA_PID 2>/dev/null" EXIT
sleep 2
python3 server.py
