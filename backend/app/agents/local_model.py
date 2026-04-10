import os
from langchain_openai import ChatOpenAI

# Centralized Local LLM Definition (Ollama)
# v4.0: Upgraded from qwen3-research (32B) to llama3.3 (70B) for superior drafting intelligence
# v4.4: Extended context window from 4K to 16K for proper chunk processing
# v5.0: Upgraded to Gemma-4-31B (Thinking Model)
MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "gemma4:31b") 

local_llm = ChatOpenAI(
    model=MODEL_NAME,   
    temperature=0.7,      # Gemma 4 recommended setting
    base_url="http://localhost:11434/v1",  # Ollama
    api_key="sk-no-key-required",
    max_tokens=16384,     # MoE model handles larger outputs efficiently
    timeout=120,
    max_retries=2
)

