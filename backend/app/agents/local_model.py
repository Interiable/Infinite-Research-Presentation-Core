import os
from langchain_openai import ChatOpenAI

# ============================================================
# Centralized Local LLM Definitions (Ollama)
#
# local_llm        → Qwen3.6 27B  — 번역·합성·필터링·포맷체크 전반
# local_science_llm → Gemma 4 31B — 과학/수학 추론 전용
# ============================================================

# Ollama base URL (supports remote GPU server via OLLAMA_BASE_URL)
_ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_URL = (_ollama_base.rstrip("/") + "/v1") if not _ollama_base.rstrip("/").endswith("/v1") else _ollama_base

# ------------------------------------------------------------------
# General LLM — Qwen3.6 27B (Dense)
# Roles: 한국어 번역, 문서 합성/요약, 웹 필터링, pre-critique, Warden, Archivist
# ------------------------------------------------------------------
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3.6:27b")

local_llm = ChatOpenAI(
    model=LOCAL_LLM_MODEL,
    temperature=0.7,
    base_url=OLLAMA_URL,
    api_key="sk-no-key-required",
    max_tokens=16384,
    timeout=180,
    max_retries=2
)

# ------------------------------------------------------------------
# Science LLM — Gemma 4 31B
# Roles: 과학·수학·공학 추론, 수식 분석, Scientific Notes 생성
# ------------------------------------------------------------------
LOCAL_SCIENCE_MODEL = os.getenv("LOCAL_SCIENCE_MODEL", "gemma4:31b")

local_science_llm = ChatOpenAI(
    model=LOCAL_SCIENCE_MODEL,
    temperature=0.3,        # 과학 추론은 낮은 temperature
    base_url=OLLAMA_URL,
    api_key="sk-no-key-required",
    max_tokens=16384,
    timeout=300,            # 복잡한 추론은 더 긴 timeout
    max_retries=2
)
