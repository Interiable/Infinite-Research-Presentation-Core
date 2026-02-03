import os
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.core.rag import VectorStoreManager

# Qwen 3 (32B) via Ollama
llm = ChatOllama(
    model="qwen3:32b", 
    temperature=0.1
)

SYSTEM_PROMPT = """
You are the **Local Archivist**.
Your job is to read local files and extract relevant information for the project.
You have access to the user's private documents via a Semantic Search Engine (RAG).
Summarize what you find in the local context.
"""

# Initialize RAG Manager (Persistent)
rag_manager = VectorStoreManager()

def archivist_node(state: AgentState):
    """
    Scans local research directory using Vector Search (RAG).
    """
    topic = state.get('research_topic', 'General Project Context')
    local_dir = os.getenv("LOCAL_RESEARCH_DIR", "/workspace/data")
    
    print(f"📂 Archivist: Checking directory {local_dir}...")
    
    # 1. Ingest Data (MVP: Simple check or reliable re-ingest)
    # For a robust production app, we would check hashes.
    # For now, we attempt to ingest. expected overhead is acceptable for small local sets.
    # Optimization: We could add a flag in state to skip ingestion if done once.
    if local_dir and os.path.exists(local_dir):
        rag_log = rag_manager.ingest_directory(local_dir)
        print(rag_log)
    else:
        return {
            "local_knowledge": "No local research directory configured.",
            "messages": [SystemMessage(content="Skipping Local Scan: Directory not found.")]
        }

    # 2. Semantic Search & Holistic Overview
    file_overview = rag_manager.get_file_overviews()
    search_results = rag_manager.similarity_search(topic, k=8)
    
    # 3. Synthesize with Qwen 3
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Research Topic: {topic}\n\n**Holistic File Overview (What we have):**\n{file_overview}\n\n**Retrieved Deep Context (Focused):**\n{search_results}\n\n**Task:** Synthesize these findings to answer the topic. Use the File Overview to understand the scope, and Deep Context for details.")
    ]
    
    try:
        response = llm.invoke(messages)
        summary = response.content
    except Exception as e:
        summary = f"Local LLM (Ollama) failed. Raw Context:\n{search_results[:500]}..."
    
    return {
        "local_knowledge": summary,
        "shared_knowledge": f"\n\nLocal RAG Archives:\n{summary}", 
        "messages": [SystemMessage(content=f"Local Analysis Complete (RAG). Found {len(search_results)} context chunks.")]
    }
