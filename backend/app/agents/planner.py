
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import RobustGemini, save_artifact

# Using Robust Model for Planning (Critical Step)
# Using Robust Model for Planning (Critical Step)
llm_planner = RobustGemini(
    temperature=0.3
)

PLANNER_SYSTEM_PROMPT = """
You are the **Lead Project Planner & Chief Librarian** for an advanced AI Agent team.
Your goal is to:
1.  **Analyze the User Request** strictly.
2.  **Filter the Data**: Look at the available local files. **IGNORE** files that are unrelated (e.g., general yearly plans, other teams' work) unless they are specifically needed for this task.
3.  **Select Context**: Identify ONLY the files that are crucial for *this specific prompt*.
4.  **Create a Plan**: Break down the task into 5-8 detailed steps.

**STRICT PLANNING RULES:**
1.  **NO SHORTCUTS**: Do NOT create a simple 3-step plan unless the task is trivial.
2.  **Adaptive Granularity**: Create as many steps as necessary (2-3 for simple, 10+ for complex).
3.  **Recursive Deliberation**: Explicitly state that each step will be further refined into a "Sub-Plan" (3-5 granular sub-steps) before execution.
4.  **Web Research Priority**: If the local library is insufficient or specialized terms (like DMP, LMA, ToM) need grounding, prioritize `DEEP_RESEARCHER` for web-searching.
5.  **Relevance is Key**: Only select files that directly support the user's current specific goal.
6.  **NO SLIDES UNLESS EXPLICITLY REQUESTED**: ONLY use 'ARCHITECT' if the user explicitly asks for "slides", "presentation", "PPT", "슬라이드", or "발표자료". For text/report tasks, use ONLY 'RESEARCHER' or 'DEEP_RESEARCHER'.

**LANGUAGE RULES (STRICT):**
1.  **REASONING & DESCRIPTIONS MUST BE IN KOREAN**. 
2.  Titles can be English or Korean.

**OUTPUT FORMAT:**
You must output PURE JSON in the following format:
{
  "relevant_files_reasoning": "선정 이유 및 분석 결과 (한국어로 작성)...",
  "selected_files": ["path/to/relevant_doc.pdf"],
  "steps": [
    {
      "id": "step_1",
      "title": "단계 제목 (Korean/English)",
      "description": "수행할 작업에 대한 상세 설명 (한국어로 작성)...",
      "assigned_to": "RESEARCHER",
      "status": "pending"
    }
  ]
}
NOTE: 'assigned_to' must be one of: 'RESEARCHER', 'ARCHITECT', 'DEEP_RESEARCHER'.
- Use 'RESEARCHER' for ALL writing, drafting, analysis, and report generation tasks. 
- Use 'DEEP_RESEARCHER' ONLY for "Investigation", "Data Gathering", or "Web Search" steps. DO NOT assign "Drafting" or "Writing" to Deep Researcher.
- Use 'ARCHITECT' ONLY when user explicitly requests slides/presentations.
"""

from langchain_core.runnables import RunnableConfig

def planner_node(state: AgentState, config: RunnableConfig):
    """
    Generates the initial project plan.
    """
    # Extract Thread ID for Artifact Isolation
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    
    messages = state['messages']
    
    # Extract the latest human goal
    goal = "General Inquiry"
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            goal = m.content
            break
    
    # --- CONTEXT AWARENESS: RAG (Vector Search) ---
    from app.core.rag import VectorStoreManager
    rag = VectorStoreManager()
    
    local_files_context = ""
    research_dirs = os.getenv("LOCAL_RESEARCH_DIR", "").split(",")
    
    print("🧠 Planner: Initializing RAG for deep context analysis...")
    
    # 1. Ingest All Data
    for d in research_dirs:
        d = d.strip()
        if d and os.path.exists(d):
            print(f"   - Ingesting {d}...")
            rag.ingest_directory(d)
            
    # 2. Semantic Search for "User Goal"
    # We retrieve key chunks to understand what data exists related to the request
    search_results = rag.similarity_search(goal, k=10)  # Reduced from 20 to 10 for token optimization
    
    # 3. File Overview (List of ALL files)
    file_overview = rag.get_file_overviews()
    
    # Construct Context
    local_files_context = f"""
    
    **📂 LOCAL FILE INDEX (RAG):**
    {file_overview}
    
    **🔍 SEMANTIC SEARCH RESULTS (Deep Content Match):**
    {search_results}
    
    **INSTRUCTION:**
    - Use the Semantic Search Results to check if specific files contain relevant details.
    - Use the File Index to select files for the plan.
    """
    
    # Pass 'found_files' list for compatibility with downstream regex logic
    # We reconstruct a simple list string from the file overview for the regex to work
    import re
    # REGEX UPDATE: Capture everything after "- " until end of line or specific delimiter
    found_files = re.findall(r"- (.+)", file_overview)
            
    print(f"📋 Generating Project Plan... (Context: {len(found_files)} files found)")
    
    response = llm_planner.invoke([
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"User Goal: {goal}{local_files_context}")
    ])
    
    # Parse JSON
    try:
        content = response.content
        
        # Handle Multipart/List Content (fix for Gemini 3 Flash)
        if isinstance(content, list):
            print(f"📦 Detected List Content. Parsing...")
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            content = " ".join(parsed_parts)
            
        # Noisy raw output print removed
        
        import re
        # Try to find JSON block
        match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Try finding just brace-enclosed content
            match = re.search(r"(\{.*\})", content, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = content

        plan_data = json.loads(json_str)
        steps = plan_data.get('steps', [])
        
        # --- STRICT LIBRARIAN FILTERING ---
        selected_files = plan_data.get('selected_files', [])
        reasoning = plan_data.get('relevant_files_reasoning', 'No reasoning provided')
        
        print(f"🧐 Librarian Logic: Selected {len(selected_files)} files.")
        print(f"📝 Reasoning: {reasoning}")
        
        # Filter the original context to include ONLY selected files
        # We need to reconstruct the string or just make a new one.
        # Ideally, we map filenames to their original snippet.
        filtered_context = ""
        if selected_files:
            filtered_context = "**📚 RELEVANT SELECTED FILES (Strict Filter):**\n"
            count = 0
            for f_entry in found_files:
                # f_entry looks like "path/to/file.py (Snippet...) (in data)"
                # We check if any selected file path is in this entry string
                is_match = False
                for sel in selected_files:
                    if sel in f_entry:
                        is_match = True
                        break
                
                if is_match:
                    filtered_context += f"- {f_entry}\n"
                    count += 1
            
            if count == 0:
                filtered_context = "**⚠️ No files matched the strict filter.** Fallback to full list:\n" + local_files_context
            else:
                filtered_context += f"\n(Filtered from {len(found_files)} total files based on: {reasoning})"
        else:
            filtered_context = local_files_context # Fallback if none selected
            
    except Exception as e:
        print(f"⚠️ Plan Parsing Failed: {e}. Raw content type: {type(response.content)}")
        print("Fallback to default plan.")
        steps = [
            {"id": "step_1", "title": "Research", "description": "Analyze request", "assigned_to": "RESEARCHER", "status": "pending"},
            {"id": "step_2", "title": "Drafting", "description": "Draft content", "assigned_to": "RESEARCHER", "status": "pending"},
            {"id": "step_3", "title": "Finalize", "description": "Generate Output", "assigned_to": "ARCHITECT", "status": "pending"}
        ]
        filtered_context = local_files_context

    # Initialize State
    save_artifact("Project_Master_Plan_Raw", f"# 📋 Raw Project Data\n\n{content}", "md", thread_id=thread_id)
    
    # Create Human-Readable Plan
    readable_plan = f"# 📋 Project Master Plan: {goal[:100]}\n\n"
    readable_plan += f"## 🧐 Librarian Reasoning\n{reasoning}\n\n"
    readable_plan += "## 📚 Selected Key Files\n"
    for f in selected_files:
        readable_plan += f"- {f}\n"
    
    readable_plan += "\n## 🛠️ Execution Strategy\n"
    for i, step in enumerate(steps):
        readable_plan += f"### Step {i+1}: {step.get('title', 'Unknown')}\n"
        readable_plan += f"- **Goal**: {step.get('description', '')}\n"
        readable_plan += f"- **Agent**: {step.get('assigned_to', 'RESEARCHER')}\n\n"
    
    save_artifact("Project_Master_Plan", readable_plan, "md", thread_id=thread_id)
    
    return {
        "sender": "Planner",
        "plan": steps,
        "current_step_index": 0,
        "local_knowledge": local_files_context, # UPDATED: Pass FULL library so Researcher isn't blinded
        "messages": [SystemMessage(content=f"Planning Complete. Total Steps: {len(steps)}. (Librarian selected {len(selected_files)} key files, but full library passed to Researcher).")]
    }
