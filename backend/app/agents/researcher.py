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

# v3.7 Adaptive Output Mode
CONCISE_SYSTEM_PROMPT = """
You are the **Efficient Content Specialist**.
Your goal is to produce **concise, high-impact content** optimized for presentations and quick reference.

**LANGUAGE RULE:**
1. **WRITE IN KOREAN**: Use Korean for all text.
2. **Technical Terms**: English allowed for accuracy.

**OUTPUT STYLE:**
- **Be Concise**: Focus on key insights only. No fluff.
- **Match the Purpose**: If it's for slides/PPT, use short phrases and key points.
- **Adapt Length**: Output should be as short as the task requires - could be a few words, a sentence, or a short paragraph.
- **Evidence**: Still cite sources, but briefly.
"""

def get_adaptive_prompt(user_goal: str) -> str:
    """
    Detects if user wants concise output (PPT, slides, etc.) vs detailed report.
    Returns appropriate system prompt.
    """
    goal_lower = user_goal.lower()

    # 1. Detailed Mode Triggers (Priority)
    # If user explicitly asks for report, deep analysis, or architecture, always use Detailed.
    detailed_keywords = ['보고서', '상세', '논문', '분석', '리포트', 'detailed', 'analysis', 
                         'architecture', '아키텍처', 'deep', 'technical', '수식']
    
    for d_word in detailed_keywords:
        if d_word in goal_lower:
            return SYSTEM_PROMPT

    # 2. Concise Mode Triggers
    # Keywords that imply presentation or extreme brevity.
    concise_keywords = ['ppt', 'slide', 'slıde', '슬라이드', '간단', '요약', '짧게', 
                        'bullet', 'point', '한줄', '발표용', '발표자료']
    
    for c_word in concise_keywords:
        if c_word in goal_lower:
            return CONCISE_SYSTEM_PROMPT
    
    return SYSTEM_PROMPT

def chunk_text(text, limit=30000, overlap=1000):
    """
    Splits text into overlapping chunks for safe LLM processing.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start += (limit - overlap)
        if start >= len(text):
            break
    return chunks

def read_full_docs(file_paths, research_dirs, max_chars=10_000_000):
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
                # Suppress pypdf/pdfminer noise locally just in case
                import logging
                import warnings
                warnings.filterwarnings("ignore")
                logging.getLogger("pypdf").setLevel(logging.ERROR)
                logging.getLogger("pdfminer").setLevel(logging.ERROR)
                
                # Try pdfminer.six first (more robust for text/hex issues)
                try:
                    from pdfminer.high_level import extract_text
                    content = extract_text(target_path)
                    print(f"📄 Robust PDF Read (pdfminer): {rel_path}")
                except Exception as e1:
                    print(f"⚠️ pdfminer failed: {e1}. Falling back to pypdf.")
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(target_path)
                        for page in reader.pages:
                            content += (page.extract_text() or "") + "\n"
                        print(f"📄 Standard PDF Read (pypdf): {rel_path}")
                    except Exception as e2:
                        content = f"[Error reading PDF {rel_path}: {e1}, {e2}]"
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
            
            # --- No Truncation (User Request) ---
            # We let the Rolling Chunk Logic handle safety.
            
            full_text += f"\n\n--- FILE: {rel_path} ---\n{content}"  
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
    current_sub_idx = state.get('current_sub_step_index', 0)
    iteration = state.get('iteration_count', 0)
    current_step_details = "No specific step details found."
    
    # --- v3.7 Adaptive Output Mode ---
    original_goal = state.get('messages', [])[0].content if state.get('messages') else ""
    active_prompt = get_adaptive_prompt(original_goal)
    if active_prompt == CONCISE_SYSTEM_PROMPT:
        print("⚡ Adaptive Mode: CONCISE output detected (PPT/슬라이드/간단/요약)")
    else:
        print("📝 Adaptive Mode: DETAILED output mode")
    
    if plan and isinstance(plan, list) and len(plan) > current_step_idx:
        current_step_details = str(plan[current_step_idx])
    
    # --- v3.4 Recursive Master Report Injection ---
    master_report_content = ""
    incremental_path = state.get('incremental_report_path', '')
    if incremental_path and os.path.exists(incremental_path):
        try:
            with open(incremental_path, "r") as f:
                master_report_content = f.read()
            print(f"📖 Loaded Incremental Master Report ({len(master_report_content)} chars)")
        except Exception as e:
            print(f"⚠️ Failed to read incremental report: {e}")

    context_prompt = ""
    if master_report_content:
        context_prompt += f"\n\n**누적 마스터 보고서 (이전 결과물 - 중요):**\n{master_report_content}\n\n**Instruction**: 이 보고서는 이전 단계에서 완성된 결과물입니다. 중복을 피하고, 이 내용을 기반으로 현재 단계를 확장하세요."

    if local_context:
        context_prompt += f"\n\n**Internal Knowledge (Local Files):**\n{local_context}\n\n**Instruction:** Integrate this local knowledge."
        
    if critique:
        context_prompt += f"\n\n**Create Critique (Reason for Revision):**\n{critique}\n\n**PREVIOUS DRAFT:**\n{previous_summary}"

    # --- v3.5 Context Warden Strategic Brief Injection ---
    warden_brief = ""
    shared_knowledge = state.get('shared_knowledge', '')
    if "--- WARDEN STRATEGIC BRIEF ---" in shared_knowledge:
        # Extract the brief block
        parts = shared_knowledge.split("--- WARDEN STRATEGIC BRIEF ---")
        if len(parts) > 1:
            warden_brief = parts[1].split("\n\n")[0] # Simple extraction
            context_prompt = f"\n\n**[중요] 전략 브리핑 (Warden Strategic Brief):**\n{warden_brief}\n\n**Instruction**: 위 브리핑의 가이드라인을 최우선으로 준수하세요." + context_prompt
            print("👁️ Warden Strategic Brief detected and injected.")

    # --- v3.8 LIVE-SCAN: Real-time File Ingestion ---
    research_dirs = os.getenv("LOCAL_RESEARCH_DIR", "").split(",")
    available_files = []
    
    for d in research_dirs:
        d = d.strip()
        if os.path.exists(d):
            # Recursively find all files in the directory
            for root, dirs, files in os.walk(d):
                # --- FILTERING (Fix Token Overflow) ---
                dirs[:] = [d for d in dirs if d not in ['node_modules', 'venv', 'dist', 'build', '__pycache__', '.git', '.idea', '.vscode']]
                
                for f in files:
                    if f.endswith(('.py', '.js', '.ts', '.tsx', '.md', '.json', '.html', '.css', '.pdf', '.txt', '.docx')):
                        # Get relative path from research_dir for the LLM to use
                        rel_path = os.path.relpath(os.path.join(root, f), d)
                        available_files.append(rel_path)
    
    # --- BATCHED RELEVANCE FILTERING (Smart List Processing) ---
    if len(available_files) > 500:
        print(f"⚠️ Too many files ({len(available_files)}). Activating Optimized Batched Filtering...")
        
        # 1. OPTIMIZATION: Heuristic Pre-Filtering (Exclusion Mode)
        # Exclude only what is DEFINITELY not content.
        # This is safer than an allow-list, as it catches edge cases.
        heuristic_files = [
            f for f in available_files 
            if not any(x in f.lower() for x in ['test', 'spec', 'mock', 'assets', 'public', 'locales', 'e2e', 'config', 'node_modules', 'dist', 'build'])
            and not f.endswith(('.css', '.html', '.json', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.map', '.lock'))
        ]
        
        if len(heuristic_files) > 0:
            print(f"⚡ Heuristic Filter applied: Reduced {len(available_files)} -> {len(heuristic_files)} candidates (Focused on Logic/Docs).")
            available_files = heuristic_files
        
        filtered_files = []
        batch_size = 200 # Balanced: Faster than 100, Safer than 500
        total_batches = (len(available_files) + batch_size - 1) // batch_size
        
        for i in range(total_batches):
            batch = available_files[i*batch_size : (i+1)*batch_size]
            print(f"   ► Filtering Batch {i+1}/{total_batches} ({len(batch)} files)...")
            
            filter_prompt = f"""
            **Files Filter Task**
            **Topic:** "{topic}"
            
            **Candidate Files:**
            {json.dumps(batch)}
            
            **Instruction:**
            Select content files that are RELEVANT to the topic.
            Exclude irrelevant utils/configs unless critical.
            Return JSON list of strings.
            Example: ["backend/main.py", "frontend/App.tsx"]
            """
            
            try:
                res = local_llm.invoke([HumanMessage(content=filter_prompt)])
                content = res.content.strip()
                
                # Robust JSON Extraction
                # 1. Remove markdown fences
                content = content.replace("```json", "").replace("```", "").strip()
                
                # 2. Extract list structure
                start = content.find("[")
                end = content.rfind("]") + 1
                
                if start != -1 and end != -1:
                    json_str = content[start:end]
                    try:
                        batch_selected = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Fallback: simple eval for python-like list or regex
                        import ast
                        try:
                            batch_selected = ast.literal_eval(json_str)
                        except:
                             print(f"⚠️ Batch {i+1} JSON repair failed. Content: {json_str[:50]}...")
                             batch_selected = []
                    
                    if isinstance(batch_selected, list):
                        filtered_files.extend(batch_selected)
                else:
                     print(f"⚠️ Batch {i+1} parse failed (No list found). Skipping batch.")
            except Exception as e:
                print(f"⚠️ Batch {i+1} filtering failed: {e}")
        
        # Remove duplicates if any
        available_files = list(set(filtered_files))
        print(f"✅ Batched Filtering Complete. Reduced from {len(available_files) * total_batches if total_batches else 0} to {len(available_files)} relevant files.")

    # Final Safety Net (if filtering still leaves too many)
    if len(available_files) > 1000:
         print(f"⚠️ Still too many files ({len(available_files)}) after filtering. Truncating to top 1000.")
         available_files = available_files[:1000]
    
    print(f"📂 Live Library Scan: {len(available_files)} files available (Live).")
    
    # Still keep Planner's context for those specific snippets, 
    # but available_files is now the TRUTH.
    
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
        # Use Local LLM for structure (Max Token Efficiency)
        toc_response = local_llm.invoke([HumanMessage(content=toc_prompt)])
        
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
        
        # --- OOM SAFEGUARD: CONTEXT LIMIT ---
        if len(chapter_context) > 50000:
             print(f"⚠️ Chapter Context too large ({len(chapter_context)} chars). Truncating to 50,000 chars safely.")
             chapter_context = chapter_context[:50000] + "\n... [Remaining Context Truncated for Safety] ..."
        
        # B. Draft (Local LLM) - Hybrid Cost Saving
        # Reduced threshold to 12,000 chars to avoid 16k token overflow (17k tokens seen with 30k chars + prompts)
        if len(chapter_context) > 12000:
             # --- SMART CHUNKING STRATEGY ---
             print(f"⚠️ Context Large ({len(chapter_context)} chars). Activating Rolling Draft Loop...")
             # Reduced chunk limit to 10,000 chars per request to be safe
             chunks = chunk_text(chapter_context, limit=10000, overlap=1000)
             final_text = ""
             
             for i, chunk in enumerate(chunks):
                 print(f"   ► Processing Chunk {i+1}/{len(chunks)}...")
                 
                 chunk_prompt = f"""
                 **Write Chapter {i+1} (Part {i+1}/{len(chunks)}): {title}**
                 
                 **Global Context / Instructions:**
                 {context_prompt}
                 
                 **Current Data Chunk:**
                 {chunk}
                 
                 **Context from Previous Parts (Connect smoothy):**
                 {final_text[-1000:] if final_text else "(Start of Chapter)"}
                 
                 **Instruction:**
                 1. Continue drafting the report using the 'Current Data Chunk'.
                 2. **FLOW**: Ensure the text connects naturally to the 'Previous Content'.
                 3. **COMPLETENESS**: Extract all key details from this chunk.
                 4. **LANGUAGE**: Korean.
                 """
                 
                 try:
                     res = local_llm.invoke([
                         SystemMessage(content=active_prompt), 
                         HumanMessage(content=chunk_prompt)
                     ])
                     final_text += res.content + "\n\n"
                 except Exception as e:
                     print(f"⚠️ Chunk {i+1} failed: {e}")
                     final_text += f"\n[Chunk {i+1} Failed: {e}]\n"
                     
             print(f"✅ Rolling Draft Complete for '{title}'. Total Length: {len(final_text)}")
             
        else:
            # --- STANDARD SINGLE-SHOT ---
            # Define draft_prompt here as it's only needed for single-shot
            draft_prompt = f"""
            **Write Chapter: {title}**
            
            **Research Data:**
            {chapter_context}
            
            **Instruction:**
            1. Write a comprehensive chapter based on the provided research data.
            2. **Language**: Korean.
            3. **Style**: Professional, detailed, and evidence-based.
            """
            try:
                # Local LLM Drafting
                local_res = local_llm.invoke([
                    SystemMessage(content=active_prompt),
                    HumanMessage(content=draft_prompt + "\n" + context_prompt) # Add context to drawer
                ])
                draft_text = local_res.content
                
                # C. Intelligent Flash Verification Loop (v3.7)
                verification_prompt = f"""
    You are a **Quality Assurance Reviewer**.
    Evaluate the following Korean research text and determine its quality.
    
    **EVALUATION CRITERIA:**
    1. Does it properly cite local files/sources?
    2. Does it stay on the assigned topic/chapter?
    3. Is it detailed enough with specific data points?
    4. Are there any factual errors or hallucinations?
    
    **TEXT TO REVIEW:**
    {draft_text[:15000]}
    
    **OUTPUT FORMAT (STRICT):**
    Choose ONE of the following verdicts and explain briefly:
    - "APPROVED" - The text meets all quality standards.
    - "MINOR_FIX: [specific issue]" - The text needs minor corrections (e.g., missing citations, minor factual issues).
    - "DEEP_RESEARCH_NEEDED: [missing topic]" - The text lacks critical information that requires external web research.
    
    Respond with your verdict first, then a brief explanation in Korean.
    """
                # C. Intelligent Verification Loop (Local LLM)
                check_res = local_llm.invoke([HumanMessage(content=verification_prompt)])
                verdict = check_res.content.strip()
                
                print(f"🔍 Local Verdict for '{title}': {verdict[:100]}...")
                
                # Branch based on verdict
                if "APPROVED" in verdict.upper():
                    final_text = draft_text
                    print(f"✅ Chapter '{title}' APPROVED")
                    
                elif "MINOR_FIX" in verdict.upper():
                    # Extract feedback and ask Local LLM to revise
                    print(f"🔧 Minor Fix Required for '{title}'. Re-drafting...")
                    revision_prompt = f"""
    **REVISION REQUIRED**
    The reviewer found the following issue:
    {verdict}
    
    **ORIGINAL DRAFT:**
    {draft_text}
    
    **INSTRUCTIONS:**
    1. Fix ONLY the specific issue mentioned above.
    2. Keep all other content intact.
    3. Maintain Korean language output.
    4. Ensure proper citations remain.
    """
                    revision_res = local_llm.invoke([
                        SystemMessage(content=active_prompt),
                        HumanMessage(content=revision_prompt)
                    ])
                    final_text = revision_res.content
                    print(f"✅ Chapter '{title}' revised successfully")
                    
                elif "DEEP_RESEARCH" in verdict.upper():
                    # Flag for deep research - add marker that SUPERVISOR can detect
                    print(f"🌍 Deep Research Needed for '{title}'. Enriching with web search...")
                    
                    # Perform inline web search using the deep research engine
                    try:
                        missing_topic = verdict.split("DEEP_RESEARCH_NEEDED:")[-1].strip() if ":" in verdict else title
                        deep_res = deep_research_engine.invoke([HumanMessage(content=f"Research: {missing_topic}")])
                        web_context = deep_res.content[:10000]
                        
                        # Re-draft with enriched context
                        enriched_prompt = f"""
    **ENRICHED DRAFT REQUIRED**
    Original draft lacked critical information. The Intelligence Officer has provided a Research Note.
    
    **RESEARCH NOTE (From Intelligence Officer):**
    {web_context}
    
    **ORIGINAL DRAFT:**
    {draft_text}
    
    **INSTRUCTIONS:**
    1. Use the **Research Note** to fill gaps in the Original Draft.
    2. **MAINTAIN** the existing indexing (1.1, 1.2...) and writing style.
    3. **INTEGRATE** the new facts/formulas naturally.
    4. **CITE** the new sources from the note.
    """
                        enriched_res = local_llm.invoke([
                            SystemMessage(content=active_prompt),
                            HumanMessage(content=enriched_prompt)
                        ])
                        final_text = enriched_res.content
                        print(f"✅ Chapter '{title}' enriched with web research")
                    except Exception as e:
                        print(f"⚠️ Deep research failed: {e}. Using original draft.")
                        final_text = draft_text
                else:
                    # Default: use original draft
                    final_text = draft_text
                   
            except Exception as e:
                print(f"⚠️ Local Draft Failed for {title}: {e}. Retrying with local fallback.")
                
                # Define fallback prompt if not already defined (Robustness)
                fallback_prompt = f"""
                **Retry Chapter: {title}**
                **Context:** {chapter_context[:20000]}
                **Instruction:** Write a detailed chapter in Korean.
                """
                
                fallback_res = local_llm.invoke([
                    SystemMessage(content=active_prompt), 
                    HumanMessage(content=fallback_prompt)
                ])
                final_text = fallback_res.content

        full_report += f"\n## {title}\n\n{final_text}\n\n"

    # 3. SAVE & RETURN
    from app.utils import save_artifact
    filename = f"Step{current_step_idx+1}_Sub{current_sub_idx+1}_Report_v{iteration+1}"
    save_artifact(filename, full_report, "md", thread_id=thread_id)
    
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
