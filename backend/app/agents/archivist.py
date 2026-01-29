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
    
    supported_exts = ('.md', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.html', '.css', '.java', '.c', '.cpp', '.h', '.go', '.rs')
    
    found_files = []
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Skipping non-existent directory: {directory}")
            continue
            
        print(f"Scanning directory: {directory}")
        for root, _, files in os.walk(directory):
            # Skip hidden folders like .git, node_modules, __pycache__
            if any(part.startswith('.') or part in ['node_modules', 'venv', 'dist', 'build'] for part in root.split(os.sep)):
                continue

            for file in files:
                if file.endswith(supported_exts):
                    try:
                        path = os.path.join(root, file)
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # relevance score: crude count of query terms
                            score = 0
                            if query:
                                score = content.lower().count(query.lower())
                                # boost for filename match
                                if query.lower() in file.lower():
                                    score += 10
                            else:
                                score = 1 # No query -> treat all as equal
                                
                            found_files.append({
                                "path": path,
                                "name": file,
                                "content": content,
                                "score": score
                            })
                    except Exception as e:
                        print(f"Error reading {file}: {e}")
                        
    if not found_files:
        return f"No relevant local files found in paths: {directory_input}"
        
    # Sort by relevance (descending)
    found_files.sort(key=lambda x: x['score'], reverse=True)
    
    # Take top 15 relevant files
    top_files = found_files[:15]
    
    result_text = []
    for f in top_files:
        # Truncate large files to save tokens, preserving head and tail if really big
        content_preview = f['content']
        if len(content_preview) > 3000:
            content_preview = content_preview[:1500] + "\n...[SNIPPED]...\n" + content_preview[-1000:]
            
        result_text.append(f"File: {f['name']} (Path: {f['path']})\nContent:\n{content_preview}")
        
    return "\n" + "="*40 + "\n".join(result_text)

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
