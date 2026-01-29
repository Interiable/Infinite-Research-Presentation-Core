import os
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState

# Qwen 3 (32B) via Ollama
# Ensure user has run: `ollama run qwen3:32b`
llm = ChatOllama(
    model="qwen3:32b", # Using the requested model name
    temperature=0.1
)

SYSTEM_PROMPT = """
You are the **Local Archivist**.
Your job is to read local files and extract relevant information for the project.
You have access to the user's private documents.
Summarize what you find in the local context.
"""

def scan_local_files(directory_input: str, query: str) -> str:
    """
    Recursively scans valid files in the provided directory(ies).
    Supports multiple directories separated by commas.
    """
    if not directory_input:
        return "No local directory configured."
    
    # Split by comma and strip whitespace
    directories = [d.strip() for d in directory_input.split(',') if d.strip()]
    
    found_content = []
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Skipping non-existent directory: {directory}")
            continue
            
        print(f"Scanning directory: {directory}")
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.md', '.txt', '.py', '.js', '.ts', '.tsx')):
                    # Added code extensions for broader context
                    try:
                        path = os.path.join(root, file)
                        # Simple text read for now - max 2000 chars per file
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if len(content) > 2000: content = content[:2000] + "..."
                            found_content.append(f"File: {file} (Path: {path})\nContent: {content}")
                    except Exception as e:
                        print(f"Error reading {file}: {e}")
                    
    if not found_content:
        return f"No relevant local files found in paths: {directory_input}"
        
    # Heuristic to return most relevant or top N files
    # For now, we return up to 5 files to fit context
    return "\n---\n".join(found_content[:5])
                    
    if not found_content:
        return "No relevant local files found."
        
    return "\n---\n".join(found_content[:5]) # Limit to top 5 for context window

def archivist_node(state: AgentState):
    """
    Scans local research directory.
    """
    topic = state.get('research_topic', '')
    local_dir = os.getenv("LOCAL_RESEARCH_DIR", "/workspace/data")
    
    raw_data = scan_local_files(local_dir, topic)
    
    # Synthesize with Qwen 3
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Context from local files:\n{raw_data}\n\nTask: Summarize this considering the topic '{topic}'.")
    ]
    
    # We try/except because Ollama might not be running in the user's environment yet
    try:
        response = llm.invoke(messages)
        summary = response.content
    except Exception as e:
        summary = f"Local LLM (Ollama) failed or not running. Raw scan result: {raw_data[:200]}..."
    
    return {
        "local_knowledge": summary,
        "shared_knowledge": f"\n\nLocal Archives Summary:\n{summary}", # Keep appending for history
        "messages": [SystemMessage(content="Local Scanning Complete.")]
    }
