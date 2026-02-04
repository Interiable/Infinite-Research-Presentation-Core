import os
from langchain_ollama import ChatOllama

# Centralized Local LLM Definition
# This allows us to easily switch the local model or config globally.
# User should ensure Ollama is running with this model.

MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "llama4") 

local_llm = ChatOllama(
    model=MODEL_NAME,   
    temperature=0.1,
    keep_alive="5m"      # Keep model in VRAM for 5 mins to speed up sequential agent steps
)
