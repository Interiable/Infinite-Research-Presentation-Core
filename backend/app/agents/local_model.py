import os
from langchain_openai import ChatOpenAI

# Centralized Local LLM Definition (Ollama)
# v4.0: Upgraded from qwen3-research (32B) to llama3.3 (70B) for superior drafting intelligence
# v4.4: Extended context window from 4K to 16K for proper chunk processing
# v5.0: Upgraded to Gemma-4-31B (Thinking Model)
MODEL_NAME   = os.getenv("LOCAL_LLM_MODEL",  "qwen3-32k:30b-a3b")
OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434/v1")

local_llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=0.7,
    base_url=OLLAMA_URL,
    api_key="sk-no-key-required",
    max_tokens=16384,
    timeout=120,
    max_retries=2
)

