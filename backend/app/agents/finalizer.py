import os
import glob
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import RobustGemini, save_artifact
from langchain_core.runnables import RunnableConfig

# Use Gemini 3 Pro for high-quality synthesis
llm_pro = RobustGemini(temperature=0.3)

SYSTEM_PROMPT = """
You are the **Master Editor & Chief Synthesizer**.
Your task is to take multiple incremental research reports and fuse them into a single, high-quality **Master Project Report**.

**GUIDELINES:**
1. **Cohesion**: Ensure smooth transitions between chapters that were written separately.
2. **De-duplication**: Remove redundant introductions or repeated context that appeared in multiple sub-reports.
3. **Consistency**: Ensure terminology and tone are uniform throughout the entire document.
4. **Structure**: Organize the final report with a clear Table of Contents, Executive Summary, Detailed Analysis, and Conclusion.
5. **Language**: Write entirely in **KOREAN** (Professional/Academic tone).
6. **Integrity**: Do not hallucinate. Only use information provided in the input reports.
"""

def finalizer_node(state: AgentState, config: RunnableConfig):
    """
    Collects all incremental reports and synthesizes them into a final master document.
    """
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    topic = state.get('research_topic', 'Project Report')
    
    
    # 1. Identify and load the Recursive Master Report (Primary Source)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    results_dir = os.path.join(base_dir, "results", thread_id)
    recursive_report_path = os.path.join(results_dir, "Project_Recursive_Master_Report.md")
    
    if os.path.exists(recursive_report_path):
        print(f"📄 Loading Recursive Master Report from: {recursive_report_path}")
        with open(recursive_report_path, "r", encoding="utf-8") as f:
            all_content = f.read()
    else:
        # Fallback to Artifacts (Old Logic)
        print("⚠️ Recursive Report not found. Falling back to artifacts...")
        artifact_dir = os.path.join("backend", "artifacts", thread_id)
        report_files = glob.glob(os.path.join(artifact_dir, "*_report_v*.md")) # Updated glob
        report_files.sort()
        
        if report_files:
            contents = []
            for file_path in report_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    contents.append(f"--- SUB-REPORT: {os.path.basename(file_path)} ---\n" + f.read())
            all_content = "\n\n".join(contents)
        else:
            all_content = state.get('shared_knowledge', 'No consolidated research found.')

    print(f"🎓 Finalizing Project: Synthesizing Content ({len(all_content)} chars)...")

    # 2. Synthesis Prompt
    synthesis_prompt = f"""
    **Topic:** {topic}
    
    **INPUT REPORTS:**
    {all_content[:50000]} 
    
    **TASK:**
    Create the **FINAL MASTER REPORT**. 
    Merge and Polish the content into a cohesive, professional Korean document.
    Include a proper '목차(TOC)' and '핵심 요약(Executive Summary)'.
    """

    try:
        response = llm_pro.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=synthesis_prompt)
        ])
        
        # FIX: Handle List Content (Gemini/LangChain Edge Case)
        content = response.content
        if isinstance(content, list):
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            master_report = " ".join(parsed_parts)
        else:
            master_report = str(content)
            
    except Exception as e:
        print(f"⚠️ Master Synthesis Failed: {e}. Falling back to raw concatenation.")
        master_report = f"# Final Master Report: {topic}\n\n" + all_content

    # 3. Save Final Artifact
    saved_path = save_artifact("Project_Master_Report", master_report, "md", thread_id=thread_id)
    
    # 4. Convert to PDF
    if saved_path:
        from app.utils import convert_to_pdf
        print(f"📄 Converting Final Report to PDF: {saved_path}")
        convert_to_pdf(saved_path)
    
    return {
        "next": "END",
        "shared_knowledge": master_report,
        "sender": "Finalizer",
        "messages": [SystemMessage(content="🏆 All research steps completed. Final Master Report has been synthesized and saved.")]
    }
