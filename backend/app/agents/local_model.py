import os
from langchain_openai import ChatOpenAI

# Centralized Local LLM Definition (llama.cpp)
MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "llama4-scout") 

local_llm = ChatOpenAI(
    model=MODEL_NAME,   
    temperature=0.1,
    base_url="http://localhost:8080/v1",
    api_key="sk-no-key-required"
)
