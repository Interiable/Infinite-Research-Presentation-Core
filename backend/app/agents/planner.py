
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import RobustGemini, save_artifact, log_night_audit

# Using Robust Model for Planning (Critical Step)
# Using Robust Model for Planning (Critical Step)
llm_planner = RobustGemini(
    temperature=0.3
)

PLANNER_SYSTEM_PROMPT = """
You are the **Lead Project Planner & Chief Librarian** for an advanced AI Agent team.
Your goal is to:
1.  **Analyze the User Request** strictly.
2.  **Determine Output Scope**: Analyze the user's intent to decide HOW MUCH output is needed.
3.  **Filter the Data**: Look at the available local files. **IGNORE** unrelated files.
4.  **Select Context**: Identify ONLY the files crucial for *this specific prompt*.
5.  **Create an Adaptive Plan**: Break down the task into AS MANY OR AS FEW STEPS AS NEEDED.

**OUTPUT SCOPE ANALYSIS (CRITICAL):**
Before planning, analyze the user's prompt to determine the intended output:
-   **Brief (2-5 pages)**: Keywords like "summarize", "overview", "brief", "정리", "요약", "간단히", "현황". Create 2-4 research steps, then a final synthesis step.
-   **Moderate (10-30 pages)**: Keywords like "analyze", "compare", "분석", "비교", "조사". Create 4-7 research steps, then writing/synthesis steps.
-   **Comprehensive (50+ pages)**: Keywords like "comprehensive study", "full report", "종합 연구", "연구 보고서", "feasibility study", "deep dive". Create 8+ research steps with iterative writing.
If no explicit scope indicator is found, infer from the topic's complexity and breadth.
Add `"output_scope": "brief|moderate|comprehensive"` to your JSON output.
**The LAST step must explicitly state the target output length and format**. If the user requested a specific artifact (e.g., "Capability Map", "Matrix"), instruct the final step to present that core artifact prominently at the top, and relegate the lengthy foundational research into an Appendix/Reference section. Do NOT force a short plan if the map requires deep research; let the research take as many steps as needed, but shape the final output format to match exactly what the user wants to see at a glance.

**STRICT PLANNING RULES:**
1.  **ADAPTIVE GRANULARITY (NO FIXED LIMITS)**: Create exactly as many steps as the topic demands. A quick summary = 2-3 steps. A deep feasibility study = 15+ steps. Do NOT default to any fixed number. Let the research scope determine the plan size.
2.  **Recursive Deliberation**: Each step will be further refined into a "Sub-Plan" with as many sub-steps as needed (could be 1-2 for simple tasks, or 5-10 for complex analyses). Do NOT fix the number of sub-steps.
3.  **Web Research Priority**: If the local library is insufficient, explicitly mention "Web Search Required" in the step description. The RESEARCHER will automatically handle it.
4.  **Patent / Prior Art Research**: For UX Research, product design, technical inventions, or new product development, include a step for **patent/prior art analysis** using 'RESEARCHER'. The system will auto-invoke patent search. Mention "patent analysis" or "prior art survey" in the description.
5.  **Relevance is Key**: Only select files that directly support the user's current specific goal.
6.  **FINAL REPORT COMPILATION**: If the task requires a final synthesis, compilation, or extraction of all findings into a master report or artifact, you MUST create a final step specifically for this and assign it to `"FINALIZER"`. Do NOT assign final compilation steps to `"RESEARCHER"`.
7.  **NO SLIDES UNLESS EXPLICITLY REQUESTED**: ONLY use 'ARCHITECT' if the user explicitly asks for "slides", "presentation", "PPT", "슬라이드", or "발표자료". For text/report tasks, use ONLY 'RESEARCHER'.

**LANGUAGE RULES (STRICT):**
1.  **REASONING & DESCRIPTIONS MUST BE IN ENGLISH**. 
2.  Titles must be in English.

**OUTPUT FORMAT:**
You must output PURE JSON in the following format:
{
  "relevant_files_reasoning": "Reasoning for file selection and analysis results...",
  "selected_files": ["path/to/relevant_doc.pdf"],
  "output_scope": "brief|moderate|comprehensive",
  "steps": [
    {
      "id": "step_1",
      "title": "Step title (English)",
      "description": "Detailed description of the task to perform...",
      "assigned_to": "RESEARCHER",
      "status": "pending"
    }
  ]
}
NOTE: 'assigned_to' must be one of: 'RESEARCHER', 'ARCHITECT', 'FINALIZER'.
- Use 'RESEARCHER' for ALL research, writing, drafting, and analysis steps (including web research or academic search). 
- Use 'FINALIZER' ONLY for the very last step if compiling the final report or extracting the ultimate deliverable.
- **IMPORTANT**: NEVER assign 'DEEP_RESEARCHER' to any step. The system will automatically use the deep research engine internally when 'RESEARCHER' needs supplemental data.
- Use 'ARCHITECT' ONLY when user explicitly requests slides/presentations.
"""

from langchain_core.runnables import RunnableConfig

def planner_node(state: AgentState, config: RunnableConfig):
    """
    Generates the initial project plan.
    """
    try:
        # Extract Thread ID for Artifact Isolation
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        # Extract Project ID
        project_id = state.get('project_id', 'default')
        
        messages = state['messages']
        
        # Extract the latest human goal
        goal = "General Inquiry"
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                goal = m.content
                break
        
        # --- CONTEXT AWARENESS: RAG (Vector Search) ---
        from app.core.rag import VectorStoreManager
        from app.utils.config_manager import ConfigManager
        rag = VectorStoreManager(project_id=project_id)
        
        local_files_context = ""
        cm = ConfigManager()
        research_dirs = cm.get_project_folders(project_id)
        
        # v6.3: Skip re-ingestion if Archivist already completed it
        if state.get('rag_ready', False):
            print("🧠 Planner: RAG already ingested by Archivist. Skipping re-ingest (Fast Path).")
        else:
            print("🧠 Planner: Initializing RAG for deep context analysis...")
            # 1. Ingest All Data
            for d in research_dirs:
                d = d.strip()
                if d and os.path.exists(d):
                    print(f"   - Ingesting {d}...")
                    rag.ingest_directory(d)
                
        # 2. Semantic Search for "User Goal"
        search_results = rag.similarity_search(goal, k=100)
        
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
        
        import re
        found_files = re.findall(r"- (.+)", file_overview)
                
        print(f"📋 Generating Project Plan... (Context: {len(found_files)} files found)")
        
        response = llm_planner.invoke([
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"User Goal: {goal}{local_files_context}")
        ])
        
        # Parse JSON
        try:
            content = response.content
            
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
                
            import re
            # Try to find JSON block
            match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
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
            
            filtered_context = ""
            if selected_files:
                filtered_context = "**📚 RELEVANT SELECTED FILES (Strict Filter):**\n"
                count = 0
                for f_entry in found_files:
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
                filtered_context = local_files_context 
                
        except Exception as e:
            print(f"⚠️ Plan Parsing Failed: {e}. Raw content type: {type(response.content)}")
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
            "local_knowledge": local_files_context, 
            "messages": [SystemMessage(content=f"Planning Complete. Total Steps: {len(steps)}.")]
        }

    except Exception as e:
        print(f"⚠️ Planner Node Critical Failure: {e}")
        log_night_audit("Planner", f"Critical Failure: {str(e)}")
        # Fallback Plan
        fallback_steps = [
            {"id": "step_1", "title": "Emergency Analysis", "description": "Analyze request (Fallback)", "assigned_to": "RESEARCHER", "status": "pending"},
            {"id": "step_2", "title": "Emergency Drafting", "description": "Draft content (Fallback)", "assigned_to": "RESEARCHER", "status": "pending"}
        ]
        return {
            "sender": "Planner",
            "plan": fallback_steps,
            "current_step_index": 0,
            "local_knowledge": "Data ingestion failed. Proceeding with limited context.",
            "messages": [SystemMessage(content=f"Planning Failed: {e}. Fallback plan activated.")]
        }
