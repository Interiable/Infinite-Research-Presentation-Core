#!/bin/bash
echo "Downloading Gemma 4 31B (Unsloth Q4_K_M)..."
ollama pull hf.co/unsloth/gemma-4-31B-it-GGUF:Q4_K_M
echo "Creating alias 'gemma4'..."
ollama cp hf.co/unsloth/gemma-4-31B-it-GGUF:Q4_K_M gemma4
echo "Done!"
