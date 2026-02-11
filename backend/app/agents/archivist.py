import os
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.core.rag import VectorStoreManager
from app.agents.local_model import local_llm

# Llama 4 Scout (17B MoE) via llama.cpp for deep local document synthesis
llm = local_llm

SYSTEM_PROMPT = """
You are the **Local Archivist & Knowledge Synthesizer**.
Your job is to deeply analyze local research documents and create a comprehensive knowledge base.

**CRITICAL RULES:**
1. **NEVER SUMMARIZE TOO BRIEFLY**: Include ALL relevant technical details, formulas, and specific data points.
2. **PRESERVE ORIGINAL CONTENT**: When you find important passages, quote them directly rather than paraphrasing.
3. **CITE SOURCES**: Always mention which file/document each piece of information comes from.
4. **KOREAN OUTPUT**: Write the final synthesis in Korean.
5. **STRUCTURE**: Organize by topic/theme, not by file.
"""

# Initialize RAG Manager (Persistent)
rag_manager = VectorStoreManager()

def archivist_node(state: AgentState):
    """
    Scans local research directory using Vector Search (RAG) and synthesizes with Qwen 3.
    Returns comprehensive local_knowledge to be used by PLANNER.
    """
    topic = state.get('research_topic', '')
    messages = state.get('messages', [])
    
    # Extract user goal from messages if topic is not set
    if not topic and messages:
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                topic = m.content[:500]  # Use first 500 chars of user request
                break
    
    if not topic:
        topic = 'General Project Context'
    
    local_dirs_raw = os.getenv("LOCAL_RESEARCH_DIR", "/workspace/data")
    local_dirs = [d.strip() for d in local_dirs_raw.split(',') if d.strip()]
    
    print(f"📂 Archivist: Scanning directories {local_dirs} for topic: {topic[:100]}...")
    
    # 1. Ingest Data (Iterate through all configured paths)
    valid_dirs_found = 0
    for local_dir in local_dirs:
        if os.path.exists(local_dir):
            print(f"   - Ingesting {local_dir}...")
            rag_log = rag_manager.ingest_directory(local_dir)
            print(rag_log)
            valid_dirs_found += 1
        else:
            print(f"⚠️ Warning: Directory not found: {local_dir}")

    if valid_dirs_found == 0:
        return {
            "local_knowledge": "No valid local research directories found.",
            "next": "PLANNER",  # Still proceed to PLANNER
            "sender": "Archivist",
            "messages": [SystemMessage(content="Skipping Local Scan: No valid directories found. Proceeding to Planning.")]
        }

    # 2. ENHANCED: Get balanced context (k=15 to fit in 16k context window)
    file_overview = rag_manager.get_file_overviews()
    search_results = rag_manager.similarity_search(topic, k=15) 
    
    # 3. Synthesize with Llama 4 Scout - Deep Analysis
    synthesis_prompt = f"""
**연구 주제:** {topic}

**파일 목록 (Local Library):**
{file_overview}

**검색된 원문 내용 (Retrieved Content):**
{search_results}

**지시사항:**
1. 위 내용을 기반으로 연구 주제와 관련된 모든 정보를 포괄적으로 정리하세요.
2. 기술적 세부사항, 공식, 수치, 방법론 등을 최대한 구체적으로 포함하세요.
3. 각 정보의 출처 파일을 명시하세요.
4. 한국어로 작성하세요.
"""
    
    llm_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=synthesis_prompt)
    ]
    
    try:
        response = llm.invoke(llm_messages)
        summary = response.content
        print(f"✅ Archivist: Synthesis complete ({len(summary)} chars)")
    except Exception as e:
        print(f"⚠️ Local LLM (Llama 4 Scout) failed: {e}. Using raw context.")
        
        # --- NEW: Night Audit Logging ---
        from app.utils import save_artifact
        audit_log = f"## 🚨 Archivist Failure Detected\n- **Topic**: {topic}\n- **Error**: {e}\n- **Action**: Fallback to raw context."
        save_artifact("night_audit_log", audit_log, "md", thread_id=state.get('thread_id', 'system'))
        
        # Fallback: Return raw search results instead of failing
        summary = f"**[Raw Local Context - LLM Synthesis Failed]**\n\n{search_results}"
    
    return {
        "local_knowledge": summary,
        "shared_knowledge": f"\n\n=== LOCAL ARCHIVES (Synthesized by Archivist) ===\n{summary}", 
        "next": "PLANNER",  # CRITICAL: Route to PLANNER after archiving
        "sender": "Archivist",
        "messages": [SystemMessage(content=f"📚 Local Document Analysis Complete. {len(summary)} characters of knowledge synthesized.")]
    }
