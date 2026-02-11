#!/bin/bash

# Configuration
MODEL_DIR="/home/hgeon/models/llama4_scout"
LLAMA_SERVER="./llama.cpp/build/bin/llama-server"

# Identify the GGUF file(s). LLaMA 4 Scout Q4_K_M might be split.
# If split, we pass the first part or the folder if supported, 
# but llama-server usually takes the first part and finds the rest.
MODEL_PATH="${MODEL_DIR}/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M-00001-of-00002.gguf"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model not found at $MODEL_PATH"
    exit 1
fi

echo "🚀 Starting LLaMA 4 Scout Server with MoE CPU Offloading..."
echo "Model: $MODEL_PATH"

# Run llama-server with requested optimizations
# -ngp 60: Offload most layers to GPU
# -ot "\\d+\\.ffn_.*exps.=CPU": Offload MoE expert layers to CPU
# --ctx-size 16384: Set context window
# --threads 32: CPU threads for offloaded parts
$LLAMA_SERVER \
  --model "$MODEL_PATH" \
  --threads 32 \
  --ctx-size 16384 \
  --n-gpu-layers 60 \
  -ot "\\d+\\.ffn_.*exps.=CPU" \
  --port 8080 \
  --host 0.0.0.0
