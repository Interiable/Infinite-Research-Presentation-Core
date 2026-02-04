import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.agents.local_model import local_llm
from app.utils import RobustGemini

# --- CONFIGURATION ---
# Using Robust Polyglot Wrapper for Critical Operations if needed
# But for orchestration, we use Flash for speed/cost.
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# Robust Wrapper for Final Polish or strictly following instruction if Local fails HARD
# Standard Pro Orchestration
llm_robust = RobustGemini(temperature=0.3)

# SPECIALIZED DEEP RESEARCH ENGINE
from app.utils import DeepResearcher
deep_research_engine = DeepResearcher(temperature=0.4)

SYSTEM_PROMPT = """
You are the **Deep Researcher & Technical Writer**.
Your goal is to build a **Comprehensive, Long-Form Report** on the user's topic.

**LANGUAGE RULE (CRITICAL):**
1. **WRITE IN KOREAN**: The main body, explanations, and descriptions MUST be in **Korean** (Hangul).
2. **Technical Terms**: English allowed for accuracy (e.g., 'Transformer', 'LLM').
3. **Professional Tone**: Logical, expansive, and detailed.

**WRITING STYLE:**
- **Accumulate**: Do not summarize. Explain deeply.
- **Evidence**: Cite specific data from the provided local files.
"""

def read_full_docs(file_paths, research_dirs):
    """
    Reads full content of specific files for deep analysis.
    Supports PDF and Text formats.
    """
    full_text = ""
    for rel_path in file_paths:
        file_found = False
        target_path = ""
        
        # Resolve absolute path
        for d in research_dirs:
            potential_path = os.path.join(d.strip(), rel_path.strip())
            if os.path.exists(potential_path):
                target_path = potential_path
                file_found = True
                break
        
        if not file_found:
            continue
            
        try:
            content = ""
            if target_path.lower().endswith('.pdf'):
                import pypdf
                reader = pypdf.PdfReader(target_path)
                for page in reader.pages:
                    content += page.extract_text() + "\n"
            elif target_path.lower().endswith('.docx'):
                try:
                    import docx
                    doc = docx.Document(target_path)
                    for para in doc.paragraphs:
                        content += para.text + "\n"
                except ImportError:
                     content = "[Error: python-docx library not installed. Cannot read DOCX]"
            else:
                # Text files
                with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            full_text += f"\n\n--- FILE: {rel_path} ---\n{content[:30000]}..." # Cap at 30k chars per file to fit context
        except Exception as e:
            full_text += f"\nError reading {rel_path}: {e}"
            
    return full_text

from langchain_core.runnables import RunnableConfig

def researcher_node(state: AgentState, config: RunnableConfig):
    """
    Recursive Drafting Mode:
    1. Plan Sections (TOC).
    2. Iterate Sections (Read Full Files -> Draft -> Review).
    3. Assemble.
    """
    # Extract Thread ID
    thread_id = config.get("configurable", {}).get("thread_id", None)
    
    topic = state.get('research_topic', 'Unknown Topic')
    mode = state.get('research_mode', 'deep') 
    
    # 0. Context Preparation
    # Context Injection
    local_context = state.get('local_knowledge', '')
    critique = state.get('critique_feedback', '') # UPDATED: Unified key from Supervisor
    previous_summary = state.get('shared_knowledge', '') or state.get('web_knowledge', '')
    
    # Extract Plan details for Scope Enforcement
    plan = state.get('plan', [])
    current_step_idx = state.get('current_step_index', 0)
    current_step_details = "No specific step details found."
    
    if plan and isinstance(plan, list) and len(plan) > current_step_idx:
        current_step_details = str(plan[current_step_idx])
    
    context_prompt = ""
    if local_context:
        context_prompt += f"\n\n**Internal Knowledge (Local Files):**\n{local_context}\n\n**Instruction:** Integrate this local knowledge."
        
    if critique:
        context_prompt += f"\n\n**Create Critique (Reason for Revision):**\n{critique}\n\n**PREVIOUS DRAFT:**\n{previous_summary}"

    # 'local_knowledge' from planner contains "Filepath (Snippet)..." strings.
    # We need to extract clean filenames to map them to chapters.
    planner_context = state.get('local_knowledge', '')
    
    # Extract filenames from Planner's context list for the LLM to choose from
    # Updated Regex to be more permissive of file paths including spaces/dots
    # We strip potential trailing context like " (Snippet...)" immediately
    raw_files = re.findall(r"- (.+)", planner_context)
    available_files = []
    for f in raw_files:
        # Cleanup: remove trailing parenthesis context if present
        clean_f = f.split(' (')[0].strip()
        available_files.append(clean_f)
    
    # 0.5. DEEP RESEARCH CHECK
    # If topic requires external web search or is very complex, use Deep Research Engine
    if "web search" in topic.lower() or "external" in topic.lower() or mode == "deep_web":
        print(f"🌍 Activating Deep Research Engine for: {topic}")
        deep_res = deep_research_engine.invoke([HumanMessage(content=topic)])
        return {
            "web_knowledge": deep_res.content,
            "shared_knowledge": f"Web Research:\n{deep_res.content}",
            "messages": [SystemMessage(content=f"Deep Web Research Complete.")]
        }

    print(f"📚 Recursive Writer Started. Topic: {topic}")
    print(f"📂 Full Library Access: {len(available_files)} files found.")

    # 1. BLUEPRINTING (TOC Generation)
    toc_prompt = f"""
    You are the Lead Editor.
    **CURRENT TASK:** Create a Table of Contents for a report on: "{topic}".
    
    **CURRENT STEP DETAILS (PRIMARY TRUTH):**
    "{current_step_details}"

    **SCOPE CONSTRAINT (CRITICAL):**
    - You must focus **ONLY** on the "Current Step Details" above.
    - **SUB-STEP BREAKDOWN**: Breakdown the "Current Step" into 2-5 detailed sub-steps (chapters).
    - **NEGATIVE CONSTRAINT**: DO NOT generate chapters for future steps (e.g., Implementation, Optimization) if the current step is about Analysis/Definition.
    - **REJECTION WARNING**: If you include out-of-scope chapters, the system will REJECT your work.
    
    **Available Local Files (Full Library):**
    {", ".join(available_files)}
    
    **Instruction:**
    - Select ANY file from the list above that is relevant to the CURRENT STEP.
    - **START AT CHAPTER 1**.
    - **TITLES MUST BE IN KOREAN**.
    - Output JSON ONLY.
    
    Format:
    {{
      "chapters": [
        {{ "title": "1.1 Analysis of [File Name]", "files": ["path/to/relevant_doc.pdf"] }},
        {{ "title": "1.2 Synthesizing [Concept]", "files": ["path/to/relevant_doc.pdf"] }}
      ]
    }}
    """
    
    try:
        # Use Standard Pro model for structure (Gemini 3 Role)
        toc_response = llm_robust.invoke([HumanMessage(content=toc_prompt)])
        
        # Handle Multipart/List Content
        content = toc_response.content
        if isinstance(content, list):
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            content = " ".join(parsed_parts)
            
        toc_content = str(content).replace("```json", "").replace("```", "").strip()
        start = toc_content.find('{')
        end = toc_content.rfind('}') + 1
        if start != -1 and end != -1:
            toc_content = toc_content[start:end]
            
        toc_data = json.loads(toc_content)
        chapters = toc_data.get('chapters', [])
    except Exception as e:
        print(f"⚠️ TOC Generation Failed: {e}. Fallback to single chapter.")
        chapters = [{"title": "Analysis Report", "files": available_files}]

    import time
    start_time = time.time()

    # 2. WRITING LOOP
    full_report = f"# {topic} \n\n"
    research_dirs = os.getenv("LOCAL_RESEARCH_DIR", "").split(",")
    
    for i, chap in enumerate(chapters):
        title = chap.get('title', f"Chapter {i+1}")
        files = chap.get('files', [])
        
        print(f"✍️ Drafting Chapter {i+1}: {title} (Refs: {len(files)} files)...")
        
        # A. Deep Read (Load Full Content)
        chapter_context = read_full_docs(files, research_dirs)
        
        # B. Draft (Local LLM) - Hybrid Cost Saving
        draft_prompt = f"""
        **Write Chapter {i+1}: {title}**
        
        **Context (Full File Contents):**
        {chapter_context}
        
        **Previous Chapter Summary:**
        {(full_report[-500:] if len(full_report) > 500 else "Start of Report")}
        
        **ORIGINAL USER GOAL (North Star):**
        "{state['messages'][0].content[:2000] if state.get('messages') else topic}"
        
        **Instructions:**
        - Write in **Korean**.
        - **MANDATORY**: You MUST directly quote the content from the Context files.
        - **EVIDENCE**: If you claim a feature exists, state the filename and line/key where you found it.
        - **NO HALLUCINATION**: If the context is empty, state "No relevant data found in provided files."
        - **SCOPE**: Stick to the chapter title. Do not wander into other topics.
        """
        
        try:
            # Local LLM Drafting
            local_res = local_llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=draft_prompt)
            ])
            draft_text = local_res.content
            
            # C. Quick Check (Gemini Flash)
            check_prompt = f"Review this Korean text. Ensure it quotes local files and stays on topic. Text:\n{draft_text[:10000]}"
            check_res = llm_flash.invoke([HumanMessage(content=check_prompt)])
            
            if len(draft_text) < 50: 
               final_text = check_res.content 
            else:
               final_text = draft_text
               
        except Exception as e:
            print(f"⚠️ Local Draft Failed for {title}: {e}. Using Flash.")
            fallback_res = llm_flash.invoke([
                SystemMessage(content=SYSTEM_PROMPT), 
                HumanMessage(content=draft_prompt)
            ])
            final_text = fallback_res.content

        full_report += f"\n## {title}\n\n{final_text}\n\n"

    # 3. SAVE & RETURN
    from app.utils import save_artifact
    save_artifact("research_final_report", full_report, "md", thread_id=thread_id)
    
    end_time = time.time()
    elapsed = end_time - start_time
    duration_str = f"{elapsed:.1f}s"
    if elapsed > 60:
        duration_str = f"{elapsed/60:.1f}min"

    return {
        "sender": "Researcher",
        "web_knowledge": full_report,
        "shared_knowledge": f"Deep Report:\n{full_report}", 
        "messages": [SystemMessage(content=f"Recursive Research Complete. {len(chapters)} Chapters generated. (Duration: {duration_str})")]
    }
