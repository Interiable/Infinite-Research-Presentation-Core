import os
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.core.rag import VectorStoreManager
from app.agents.local_model import local_llm
from app.utils import log_night_audit

# Llama 4 Scout (17B MoE) via llama.cpp for deep local document synthesis
llm = local_llm

SYSTEM_PROMPT = """
You are the **Local Archivist & Knowledge Synthesizer**.
Your job is to deeply analyze local research documents and create a comprehensive knowledge base.

**CRITICAL RULES:**
1. **NEVER SUMMARIZE TOO BRIEFLY**: Include ALL relevant technical details, formulas, and specific data points.
2. **PRESERVE ORIGINAL CONTENT**: When you find important passages, quote them directly rather than paraphrasing.
3. **CITE SOURCES**: Always mention which file/document each piece of information comes from.
4. **ENGLISH OUTPUT**: Write the final synthesis in English.
5. **STRUCTURE**: Organize by topic/theme, not by file.
"""

# Removed global VectorStoreManager instance

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
    
    project_id = state.get('project_id', 'default')
    
    from app.utils.config_manager import ConfigManager
    cm = ConfigManager()
    local_dirs = cm.get_project_folders(project_id)
    
    rag_manager = VectorStoreManager(project_id=project_id)
    
    print(f"📂 Archivist {project_id}: Scanning directories {local_dirs} for topic: {topic[:100]}...")
    
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

    # 2. ENHANCED: Get balanced context (k=30 to fit in 32k context window)
    # k=30 * 2000 chars = 60,000 chars (~24k tokens), leaving 8k for instructions/output.
    file_overview = rag_manager.get_file_overviews()
    search_results = rag_manager.similarity_search(topic, k=30) 
    
    # 3. Synthesize with Qwen 3 - Deep Analysis
    synthesis_prompt = f"""
**연구 주제:** {topic}

**파일 목록 (Local Library):**
{file_overview}

**검색된 원문 내용 (Retrieved Content - Top 45 Chunks):**
{search_results}

**지시사항:**
1. 위 내용을 기반으로 연구 주제와 관련된 모든 정보를 **최대한 방대하고 포괄적으로** 정리하세요.
2. **절대 요약하지 마세요.** 모든 기술적 세부사항, 공식, 수치, 방법론, 그리고 각 파일의 핵심 논점들을 빠짐없이 포함하세요. 답변이 매우 길어져도 괜찮으니 압도적인 디테일을 보여주세요.
3. 각 정보의 출처 파일(Source)을 본문 내에 명시하세요 (예: [파일명.pdf]).
4. Write in English, maintaining a professional technical report format.
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
        
        # --- Standardized Night Audit Logging ---
        log_night_audit("Archivist", f"LLM Synthesis Failed: {e}")
        
        # Fallback: Return raw search results instead of failing
        summary = f"**[Raw Local Context - LLM Synthesis Failed]**\n\n{search_results}"
    
    return {
        "local_knowledge": summary,
        "shared_knowledge": f"\n\n=== LOCAL ARCHIVES (Synthesized by Archivist) ===\n{summary}", 
        "next": "PLANNER",  # CRITICAL: Route to PLANNER after archiving
        "sender": "Archivist",
        "rag_ready": True,  # v6.3: Signal Planner to skip re-ingestion
        "messages": [SystemMessage(content=f"📚 Local Document Analysis Complete. {len(summary)} characters of knowledge synthesized.")]
    }
