import os
import re
import glob
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import RobustGemini, save_artifact, log_night_audit
from langchain_core.runnables import RunnableConfig

# Use Gemini 3 Pro for high-quality synthesis
llm_pro = RobustGemini(temperature=0.3)
llm_flash = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"),
    temperature=0.2,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=120,
    max_retries=2
)

SYSTEM_PROMPT = """
You are the **Final Deliverable Architect** — the culmination of an extensive, multi-day autonomous research project.
Your task is to produce a beautiful, elegant, and definitive final deliverable from the aggregated research.

**GUIDELINES:**
1. **Adaptive Fulfillment**: 
   - If the user explicitly requested a specific structural deliverable (e.g., Capability Maps, system architectures, frameworks, matrices, design specifications), you MUST extract and present the EXACT, COMPLETE artifacts. Do NOT summarize or paraphrase — copy them VERBATIM from the research.
   - If the user only requested a general "research report" or "analysis" without a specific structural artifact, write a concise, high-level **Executive Summary** synthesizing the core findings.
2. **CRITICAL — VERBATIM ARTIFACT PRESERVATION**: 
   - All structured artifacts found in the research MUST be preserved EXACTLY as they appear in the original report:
     * **Markdown Tables** (| header | header |...) — copy entire tables verbatim.
     * **Code Blocks** (```...```) — preserve all code, formulas, and pseudocode exactly.
     * **Mathematical Formulas** (LaTeX, equations) — preserve exactly as written.
     * **Architecture Diagrams** (ASCII art, Mermaid, structured specs) — preserve exactly.
   - The `[KEY ARTIFACTS]` section provided contains these original artifacts extracted from the research. You MUST include them in your output in their original form.
   - You may add brief contextual introductions or strategic commentary AROUND the artifacts, but NEVER modify their content.
3. **Beautiful Presentation**: 
   - Structure the deliverable so the most important results appear FIRST.
   - Use clear section headers, logical flow, and professional formatting.
   - Add a brief executive overview at the very top summarizing key strategic insights.
4. **Accuracy & Integrity**: Do not hallucinate. Pull data directly from the most refined, finalized sections.
5. **No References**: Do not append a references section — the full research appendix already contains them.
6. **Format**: Output in clean, professional English Markdown.
"""


def standardize_citations(text: str, registry: list = None) -> tuple:
    """
    v13.0: Standardizes inline citations to academic [1], [2] format.
    Supports both new [REF-XXX] format and legacy [Type: Source] format.
    When registry is provided, maps REF-XXX to their verified source info.
    """
    unique_citations = {}
    citation_counter = 1
    
    # --- Phase 1: Process [REF-XXX] citations (v13.0 RFW system) ---
    ref_xxx_pattern = r'\[(REF-\d{3})\]'
    ref_ids_found = re.findall(ref_xxx_pattern, text)
    
    if ref_ids_found:
        # Build registry lookup
        registry_lookup = {}
        if registry:
            for r in registry:
                registry_lookup[r['ref_id']] = r
        
        def ref_replacer(match):
            nonlocal citation_counter
            ref_id = match.group(1)
            
            if ref_id not in unique_citations:
                ref_info = registry_lookup.get(ref_id, {})
                ref_type = ref_info.get('type', 'unknown').capitalize()
                ref_title = ref_info.get('title', ref_id)
                
                unique_citations[ref_id] = {
                    "number": citation_counter,
                    "type": ref_type,
                    "content": ref_title,
                    "url": ref_info.get('url', ''),
                    "patent_id": ref_info.get('patent_id', ''),
                }
                citation_counter += 1
            
            return f"[{unique_citations[ref_id]['number']}]"
        
        text = re.sub(ref_xxx_pattern, ref_replacer, text)
    
    # --- Phase 2: Process legacy [Type: Source] citations (backward compat) ---
    legacy_ref_pattern = r'\[(File|Web|Patent✓?|Paper✓?):\s*([^\]]+)\]'
    
    def legacy_replacer(match):
        nonlocal citation_counter
        ref_type = match.group(1).strip()
        ref_content = match.group(2).strip()
        
        citation_key_lower = f"{ref_type}:{ref_content}".lower()
        
        if citation_key_lower not in unique_citations:
            unique_citations[citation_key_lower] = {
                "number": citation_counter,
                "type": ref_type,
                "content": ref_content,
                "url": "",
                "patent_id": "",
            }
            citation_counter += 1
            
        return f"[{unique_citations[citation_key_lower]['number']}]"

    text = re.sub(legacy_ref_pattern, legacy_replacer, text, flags=re.IGNORECASE)
    
    # --- Phase 3: Clean up old References section ---
    ref_match = re.search(r'\n##\s*References?', text, re.IGNORECASE)
    if ref_match:
        text_clean = text[:ref_match.start()].strip()
    else:
        text_clean = text.strip()
    
    # --- Phase 4: Build clean References section ---
    if not unique_citations:
        return text_clean, ""
        
    refs_section = "\n\n## References\n\n"
    sorted_values = sorted(unique_citations.values(), key=lambda x: x["number"])
    
    for ref in sorted_values:
        ref_type = ref['type']
        ref_content = ref['content']
        url = ref.get('url', '')
        patent_id = ref.get('patent_id', '')
        
        if url:
            refs_section += f"{ref['number']}. **{ref_type}**: [{ref_content}]({url})\n"
        elif patent_id:
            refs_section += f"{ref['number']}. **{ref_type}**: {patent_id} — {ref_content}\n"
        else:
            refs_section += f"{ref['number']}. **{ref_type}**: {ref_content}\n"
        
    return text_clean, refs_section


def _extract_key_artifacts(artifact_dir: str, step_numbers: list) -> str:
    """
    v7.1: Extract ALL key structured artifacts verbatim from step report_final files.
    Handles: Markdown tables, code blocks (formulas, architecture, pseudocode), 
    and LaTeX/math expressions. This ensures deliverables are preserved exactly
    regardless of research type (UX maps, architecture specs, algorithms, etc.).
    """
    all_artifacts = []
    
    for step_num in step_numbers:
        step_files = glob.glob(os.path.join(artifact_dir, f"*_step{step_num}_sub*_report_final.md"))
        step_files = [f for f in step_files if not f.endswith('.old_backup')]
        step_files.sort()
        
        for fpath in step_files:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                source = os.path.basename(fpath)
                lines = content.split('\n')
                
                # --- 1. Extract Markdown Tables ---
                current_table = []
                table_context = ""
                
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('|') and '|' in stripped[1:]:
                        if not current_table:
                            for j in range(i-1, max(i-5, -1), -1):
                                if lines[j].strip().startswith('#'):
                                    table_context = lines[j].strip()
                                    break
                        current_table.append(line)
                    else:
                        if current_table and len(current_table) >= 3:
                            header = f"\n### 📊 Table from: {source}"
                            if table_context:
                                header += f"\n{table_context}"
                            all_artifacts.append(f"{header}\n\n" + '\n'.join(current_table))
                        current_table = []
                        table_context = ""
                
                if current_table and len(current_table) >= 3:
                    header = f"\n### 📊 Table from: {source}"
                    if table_context:
                        header += f"\n{table_context}"
                    all_artifacts.append(f"{header}\n\n" + '\n'.join(current_table))
                
                # --- 2. Extract Code Blocks (formulas, architecture, pseudocode) ---
                code_block_pattern = re.compile(r'(#{1,4}\s+[^\n]*\n)?\s*```[\w]*\n(.*?)```', re.DOTALL)
                for match in code_block_pattern.finditer(content):
                    code_content = match.group(2).strip()
                    code_header = match.group(1).strip() if match.group(1) else ""
                    # Only extract substantial code blocks (>3 lines or contains formulas/architecture keywords)
                    if len(code_content.split('\n')) >= 3 or any(kw in code_content.lower() for kw in 
                        ['def ', 'class ', 'formula', 'equation', 'architecture', 'config', 'struct', 'interface', '$$', 'alpha', 'beta', 'theta', 'lambda']):
                        header = f"\n### 💻 Code/Formula from: {source}"
                        if code_header:
                            header += f"\n{code_header}"
                        all_artifacts.append(f"{header}\n\n{match.group(0)}")
                
                # --- 3. Extract LaTeX/Math expressions (standalone $$ blocks) ---
                latex_pattern = re.compile(r'(#{1,4}\s+[^\n]*\n)?\s*(\$\$[^$]+\$\$)', re.DOTALL)
                for match in latex_pattern.finditer(content):
                    latex_header = match.group(1).strip() if match.group(1) else ""
                    header = f"\n### 📝 Formula from: {source}"
                    if latex_header:
                        header += f"\n{latex_header}"
                    all_artifacts.append(f"{header}\n\n{match.group(2)}")
                    
            except Exception as e:
                print(f"   ⚠️ Failed to extract artifacts from {os.path.basename(fpath)}: {e}")
    
    if all_artifacts:
        result = "\n\n---\n\n".join(all_artifacts)
        print(f"📋 Extracted {len(all_artifacts)} key artifacts (tables, code, formulas) from steps {step_numbers} ({len(result)} chars)")
        return result
    else:
        print(f"⚠️ No structured artifacts found in steps {step_numbers}")
        return ""


def finalizer_node(state: AgentState, config: RunnableConfig):
    """
    Collects all incremental reports and synthesizes them into a final master document.
    v6.3: Added chunked synthesis for large reports and reference deduplication.
    v6.6: Added retry counter to prevent infinite loops, and chunked synthesis for cost optimization.
    """
    try:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        topic = state.get('research_topic', 'Project Report')
        
        # v7.3: Retry counter with unconditional reset for fresh runs
        # Only preserve retries during active critique iterations (when feedback exists)
        critique_feedback_check = state.get('critique_feedback', '')
        finalizer_retries = state.get('_finalizer_retries', 0)
        if critique_feedback_check == 'APPROVED':
            # Phase 2 assembly — keep retries as-is
            pass
        elif finalizer_retries >= 3:
            # Stale retries from a previous broken run — reset
            print(f"   🔄 Resetting _finalizer_retries from {finalizer_retries} to 0 (stale retries detected)")
            finalizer_retries = 0
        
        MAX_FINALIZER_RETRIES = 5
        if finalizer_retries >= MAX_FINALIZER_RETRIES:
            print(f"🛑 Finalizer has failed {finalizer_retries} times. Terminating to prevent infinite loop.")
            log_night_audit("Finalizer", f"Max retries ({MAX_FINALIZER_RETRIES}) exceeded. Terminating.")
            return {
                "next": "SUPERVISOR",
                "shared_knowledge": "Finalizer reached maximum retry limit. Please check API keys and system configuration.",
                "messages": [SystemMessage(content="Assembly Complete. Finalizer terminated after max retries.")],
                "_finalizer_retries": 0
            }
        
        # 1. Identify and load the Recursive Master Report (Primary Source)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        results_dir = os.path.join(base_dir, "results", thread_id)
        recursive_report_path = os.path.join(results_dir, "Project_Recursive_Master_Report.md")
        
        if os.path.exists(recursive_report_path):
            print(f"📄 Loading Recursive Master Report from: {recursive_report_path}")
            with open(recursive_report_path, "r", encoding="utf-8") as f:
                all_content = f.read()
        else:
            # Fallback to Artifacts (robust merging logic)
            print("⚠️ Recursive Report not found. Falling back to artifacts...")
            artifact_dir = os.path.join(base_dir, "artifacts", thread_id)
            report_files = glob.glob(os.path.join(artifact_dir, "*_report_final.md"))
            
            if not report_files:
                report_files = glob.glob(os.path.join(artifact_dir, "*_report_v*.md"))
                
            if report_files:
                def extract_sort_key(filepath):
                    filename = os.path.basename(filepath)
                    m1 = re.search(r"Step(\d+)_Sub(\d+)_", filename, re.IGNORECASE)
                    if m1:
                        return (int(m1.group(1)), int(m1.group(2)))
                    m2 = re.search(r"step(\d+)_sub(\d+)_", filename, re.IGNORECASE)
                    if m2:
                        return (int(m2.group(1)), int(m2.group(2)))
                    return (999, 999)

                report_files.sort(key=extract_sort_key)
                
                print(f"🧹 Finalizer Merging: Found {len(report_files)} completed reports.")
                
                # --- NEW FORMATTING LOGIC START ---
                import json
                
                step_titles = {}
                master_plan_files = glob.glob(os.path.join(artifact_dir, "*_project_master_plan_raw.md"))
                if master_plan_files:
                    master_plan_files.sort()
                    try:
                        with open(master_plan_files[-1], 'r', encoding='utf-8') as f:
                            content = f.read()
                            json_str = content.split("```json")[1].split("```")[0].strip()
                            plan_data = json.loads(json_str)
                            for step in plan_data.get("steps", []):
                                s_id = str(step.get("id", "")).replace("step_", "")
                                if s_id.isdigit():
                                    step_titles[int(s_id)] = step.get("title", f"Step {s_id}")
                    except Exception as e:
                        print("Failed to parse master plan json:", e)

                substep_titles = {}
                subplan_files = glob.glob(os.path.join(artifact_dir, "*_subplan.md"))
                for sp_file in subplan_files:
                    m = re.search(r"step(\d+)_subplan", os.path.basename(sp_file), re.IGNORECASE)
                    if m:
                        step_idx = int(m.group(1))
                        with open(sp_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            sub_matches = re.findall(r"###\s*\[.*?\]\s*Sub-Step\s*(\d+):\s*(.*)", content, re.IGNORECASE)
                            for sub_match in sub_matches:
                                sub_idx = int(sub_match[0])
                                sub_title = sub_match[1].strip()
                                substep_titles[(step_idx, sub_idx)] = sub_title

                # v7.3: Fallback — extract titles from each report file's first heading
                for f_path in report_files:
                    sort_key = extract_sort_key(f_path)
                    if sort_key == (999, 999):
                        continue
                    s_idx, sub_idx = sort_key
                    if (s_idx, sub_idx) not in substep_titles:
                        with open(f_path, 'r', encoding='utf-8') as f:
                            first_lines = f.read(500)
                        title_match = re.match(r'^#\s+(.+)', first_lines.strip())
                        if title_match:
                            raw_title = title_match.group(1).strip()
                            # Remove "Step X.Y: " prefix
                            raw_title = re.sub(r'^Step\s+\d+\.\d+:\s*', '', raw_title)
                            substep_titles[(s_idx, sub_idx)] = raw_title

                # v7.3: Page number estimation
                CHARS_PER_PAGE = 3000
                current_page = 6  # After deliverable section

                toc_lines = ["# 📑 Table of Contents\n"]
                processed_contents = []
                current_step = -1
                
                for f_path in report_files:
                    filename = os.path.basename(f_path)
                    print(f"   ► Included: {filename}")
                    
                    sort_key = extract_sort_key(f_path)
                    if sort_key == (999, 999): continue
                    s_idx, sub_idx = sort_key
                    
                    with open(f_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    content = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|GEMMA4|DEEPSEEK-R1)[^\]]*\]', '', content, flags=re.IGNORECASE)

                    step_title = step_titles.get(s_idx, f"Step {s_idx}")
                    sub_title = substep_titles.get((s_idx, sub_idx), f"Sub-step {s_idx}.{sub_idx}")
                    
                    if s_idx != current_step:
                        current_step = s_idx
                        step_header = f"# {s_idx}. {step_title}"
                        processed_contents.append(step_header)
                        toc_lines.append(f"\n### Step {s_idx}: {step_title}")
                        
                    toc_lines.append(f"- {s_idx}.{sub_idx} {sub_title} ···· p.{current_page}")
                    current_page += max(1, len(content) // CHARS_PER_PAGE)
                    
                    content = re.sub(r"^#\s*Step\s*\d+\.\d+.*?(\n|$)", "", content, flags=re.IGNORECASE | re.MULTILINE)
                    content = re.sub(r"Deep Report:", "", content, flags=re.IGNORECASE)
                    
                    lines = content.split('\n')
                    new_lines = []
                    
                    for line in lines:
                        if line.strip().startswith("#"):
                            m = re.match(r"^(\s*)(#+)\s+(.*)", line)
                            if m:
                                indent = m.group(1)
                                level = m.group(2)
                                rest = m.group(3)
                                if re.match(r"^\d+\.\d+\.\d+", rest) or "Chapter " in rest:
                                    new_lines.append(f"{indent}### {rest}")
                                else:
                                    new_level_len = min(6, len(level) + 2)
                                    new_lines.append(f"{indent}{'#' * new_level_len} {rest}")
                            else:
                                new_lines.append(line)
                        else:
                            new_lines.append(line)
                            
                    chapter_content = "\n".join(new_lines).strip()
                    substep_header = f"## 📖 Step {s_idx}.{sub_idx} — {sub_title}"
                    combined_substep = f"{substep_header}\n\n{chapter_content}\n"
                    processed_contents.append(combined_substep)

                all_content = "\n".join(toc_lines) + "\n\n---\n\n" + "\n\n".join(processed_contents)
                # --- NEW FORMATTING LOGIC END ---
            else:
                all_content = state.get('shared_knowledge', 'No consolidated research found.')

        print(f"🎓 Finalizing Project: Synthesizing Content ({len(all_content)} chars)...")

        # Strip internal tags that hallucinated past negligence
        all_content = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|GEMMA4|DEEPSEEK-R1)[^\]]*\]', '', all_content, flags=re.IGNORECASE)

        # Ensure there is a blank line before markdown tables for proper PDF rendering
        all_content = re.sub(r'([^\n|])\n(\s*\|)', r'\1\n\n\2', all_content)

        # Save the raw concatenated report before synthesis
        print("📥 Saving the raw concatenated report...")
        save_artifact("Project_Raw_Concatenated_Report", all_content, "md", thread_id=thread_id)

        # v6.4: References are standardized AFTER synthesis (to catch AI generated citations)
        content_body = all_content

        critique_feedback = state.get("critique_feedback", "")
        
        # ======================================================================
        # PHASE 2: FINAL ASSEMBLY & TRANSLATION (Triggered by Supervisor Approval)
        # ======================================================================
        if critique_feedback == "APPROVED":
            print("🚀 Finalizer Approval Received. Executing Document Assembly & Translation...")
            extracted_deliverable_en = state.get('shared_knowledge', 'No approved draft found.')
            
            # Ensure there is a blank line before markdown tables for proper PDF rendering
            extracted_deliverable_en = re.sub(r'([^\n|])\n(\s*\|)', r'\1\n\n\2', extracted_deliverable_en)

            # v10.9: Web Research Whitelist URL Guard (same as researcher.py)
            # Strip any markdown links whose URL is NOT in the verified web_research/ SOURCE: whitelist
            import glob as _glob
            urls_in_final = re.findall(r'(\[.*?\])\((https?://[^\s\)]+)\)', extracted_deliverable_en)
            if urls_in_final:
                _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                _project_id = state.get('project_id', 'default')
                _WEB_RESEARCH_DIR = os.path.join(_BASE_DIR, "data", "projects", _project_id, "web_research")
                
                verified_urls = set()
                if os.path.isdir(_WEB_RESEARCH_DIR):
                    for txt_file in _glob.glob(os.path.join(_WEB_RESEARCH_DIR, "**", "*.txt"), recursive=True):
                        try:
                            with open(txt_file, 'r', encoding='utf-8', errors='ignore') as _f:
                                first_line = _f.readline().strip()
                                if first_line.startswith("SOURCE:"):
                                    src_url = first_line.replace("SOURCE:", "").strip().lower().rstrip('/#?')
                                    verified_urls.add(src_url)
                        except Exception:
                            pass
                    print(f"🔐 Finalizer URL Whitelist: Loaded {len(verified_urls)} verified URLs")
                
                stripped_count = 0
                for text_part, url_part in set(urls_in_final):
                    url_clean = url_part.strip().lower().rstrip('/#?')
                    if 'example.com' in url_clean or 'simulated' in url_clean:
                        continue
                    is_whitelisted = any(
                        url_clean.startswith(wl_url) or wl_url.startswith(url_clean)
                        for wl_url in verified_urls
                    ) if verified_urls else True  # If no whitelist available, keep all
                    if not is_whitelisted:
                        extracted_deliverable_en = extracted_deliverable_en.replace(
                            f"{text_part}({url_part})", text_part.strip('[]'))
                        stripped_count += 1
                if stripped_count > 0:
                    print(f"🛡️ Finalizer URL Guard: Stripped {stripped_count} unverified link(s) from final deliverable.")

            master_report_en = f"# 🎯 Primary Deliverable\n\n{extracted_deliverable_en}\n\n---\n\n# 📚 Full Research Appendix\n\n{content_body}"

            # 3. Save English Artifact
            saved_path_en = save_artifact("Project_Master_Report_EN", master_report_en, "md", thread_id=thread_id)
            
            # 4. Local LLM Chunked Korean Translation Pass
            master_report_ko = ""
            saved_path_ko = ""
            try:
                from langchain_ollama import ChatOllama
                print("🌐 Starting Local LLM Translation to Korean Data Chunking...")
                
                # Initialize local translator
                local_translator = ChatOllama(
                    model=os.getenv("LOCAL_LLM_MODEL", "qwen3:32b"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                    temperature=0.0,
                    timeout=300 # Generous timeout for translation
                )
                
                # Smart chunking logic
                
                # Split by Top Level headers to keep context, if chunk is too big, split by ##
                # First, simply split by double newline to be safe and build blocks up to max_chars
                CHUNKS = []
                MAX_CHUNK_CHARS = 4000
                
                # We want to keep code blocks and tables together if possible.
                paragraphs = re.split(r'\n\n(?=#+ )', master_report_en) # Split at new headers
                
                current_chunk = ""
                for p in paragraphs:
                    if len(current_chunk) + len(p) > MAX_CHUNK_CHARS and current_chunk:
                        CHUNKS.append(current_chunk)
                        current_chunk = p
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + p
                        else:
                            current_chunk = p
                if current_chunk:
                    CHUNKS.append(current_chunk)
                
                print(f"📦 Total chunks to translate: {len(CHUNKS)} over {len(master_report_en)} characters.")
                
                translated_chunks = []
                for idx, chunk in enumerate(CHUNKS):
                    print(f"   ► Translating chunk {idx+1}/{len(CHUNKS)}... ({len(chunk)} chars)")
                    
                    trans_sys = "You are an expert Technical Translator. Your ONLY job is to translate the provided English Markdown text into perfectly natural, professional Korean. You MUST preserve ALL Markdown formatting (tables, headers, bold, code blocks, bullet points) EXACTLY as they are. Do NOT add any extra conversational text."
                    trans_prompt = f"TRANSLATE THE FOLLOWING TEXT TO KOREAN:\n\n{chunk}"
                    
                    try:
                        res = local_translator.invoke([
                            SystemMessage(content=trans_sys),
                            HumanMessage(content=trans_prompt)
                        ])
                        # Ensure it doesn't wrap output in generic markdown code blocks if the original didn't have it
                        out_text = str(res.content)
                        if out_text.startswith("```markdown\n") and not chunk.startswith("```markdown\n"):
                            out_text = out_text[12:]
                            if out_text.endswith("```"):
                                out_text = out_text[:-3]
                                
                        translated_chunks.append(out_text.strip())
                    except Exception as chunk_err:
                        print(f"   ⚠️ Chunk {idx+1} Translation Failed: {chunk_err}. Falling back to English for this chunk.")
                        translated_chunks.append(chunk) # Fallback to original
                
                master_report_ko = "\n\n".join(translated_chunks)
                print("✅ Local LLM Translation Complete.")
                
            except Exception as e:
                print(f"⚠️ Korean Translation Failed completely: {e}.")
                master_report_ko = f"# 번역 실패 (Translation Failed)\n\n로컬 번역 프로세스 중 오류가 발생했습니다: {e}\n\n" + master_report_en

            # 5. Save Korean Artifact
            if master_report_ko:
                saved_path_ko = save_artifact("Project_Master_Report_KO", master_report_ko, "md", thread_id=thread_id)

            # 6. Convert to PDF (Both Versions)
            from app.utils import convert_to_pdf
            
            if saved_path_en:
                print(f"📄 Converting English Report to PDF: {saved_path_en}")
                convert_to_pdf(saved_path_en)
                
            if saved_path_ko:
                print(f"📄 Converting Korean Report to PDF: {saved_path_ko}")
                convert_to_pdf(saved_path_ko)
            
            return {
                "next": "SUPERVISOR",
                "shared_knowledge": f"English Report:\n{master_report_en[:500]}...\n\nKorean Report:\n{master_report_ko[:500]}...",
                "sender": "Finalizer",
                "messages": [SystemMessage(content="Assembly Complete. All master reports synthesized, translated, and saved as PDFs.")]
            }

        # ======================================================================
        # PHASE 1: DRAFTING & EXTRACTION
        # v7.3: Full-context Pro synthesis — trust Pro's judgment completely
        # ======================================================================
        original_goal = state.get('messages', [])[0].content if state.get('messages') else "Provide the complete final results."
        
        # v7.3: Pass FULL content directly to Gemini Pro (1M+ token context)
        # No chunked synthesis, no pre-filtering. Pro reads everything and decides.
        synthesis_input = content_body
        print(f"   📊 Passing FULL research content to Gemini Pro ({len(synthesis_input)} chars, ~{len(synthesis_input)//4000}K tokens)")

        synthesis_prompt = f"""
**Original User Goal (What they explicitly asked for):** 
{original_goal}

**PREVIOUS SUPERVISOR CRITIQUE (Fix these issues if any):**
{critique_feedback if critique_feedback else "None (First Draft)"}

**FULL INPUT RESEARCH REPORT:**
{synthesis_input}

{'='*80}
**YOUR TASK:**

You have just read the COMPLETE research report above — the result of an extensive, multi-day autonomous investigation by 11 specialized AI agents.

Now produce a **FINAL DELIVERABLE** that the user can immediately read, understand, and apply to their work.

**Structure:**
1. **Executive Overview** — Concisely summarize the most important strategic insights and conclusions from the entire research.
2. **Key Deliverables** — Present the core results that directly fulfill the user's Original Goal. Use your own judgment to determine what these are based on the full research content. They could be:
   - Capability Maps, matrices, comparison tables
   - System architectures, design specifications
   - Formulas, algorithms, frameworks
   - Strategic recommendations, taxonomies
   
   You may merge, reorganize, or restructure deliverables if it makes the final output clearer and more useful — but **preserve the substantive content and data verbatim**. Do NOT abbreviate or summarize table cells, formulas, or specifications. If multiple related artifacts should be consolidated into one comprehensive artifact, do so.

3. **Strategic Commentary** — Add brief contextual analysis and actionable takeaways around each deliverable.

**Quality Standards:**
- The output must be immediately actionable — a practitioner should be able to read this and apply it directly.
- Beautiful, elegant, professional Markdown formatting.
- Clear, logical structure with descriptive section headers.
- No fluff or filler — every sentence should add value.
- Do NOT include a references section (the full research appendix handles that).
"""

        try:
            print("🎓 Extracting Final Deliverables via Gemini Pro (full context)...")
            response_en = llm_pro.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=synthesis_prompt)
            ])
            
            content_en = response_en.content
            if isinstance(content_en, list):
                parsed_parts = []
                for c in content_en:
                    if isinstance(c, dict) and 'text' in c:
                        parsed_parts.append(c['text'])
                    elif hasattr(c, 'text'):
                        parsed_parts.append(c.text)
                    else:
                        parsed_parts.append(str(c))
                extracted_deliverable_en = " ".join(parsed_parts)
            else:
                extracted_deliverable_en = str(content_en)
                
        except Exception as e:
            print(f"⚠️ Extraction Failed: {e}. Falling back.")
            extracted_deliverable_en = f"# Deliverable Extraction Failed\n\n{e}"

        # v7.3: Save each draft as MD for review
        draft_num = finalizer_retries + 1
        print(f"📝 Saving Finalizer Deliverable Draft #{draft_num} ({len(extracted_deliverable_en)} chars)")
        save_artifact(f"Finalizer_Deliverable_Draft_{draft_num}", extracted_deliverable_en, "md", thread_id=thread_id)

        return {
            "next": "SUPERVISOR",
            "shared_knowledge": extracted_deliverable_en,
            "messages": [SystemMessage(content="Finalizer Draft Submitted for Critique.")],
            "_finalizer_retries": finalizer_retries + 1
        }

    except Exception as e:
        print(f"⚠️ Finalizer Node Critical Failure: {e}")
        log_night_audit("Finalizer", f"Critical Failure: {str(e)}")
        finalizer_retries = state.get('_finalizer_retries', 0) + 1
        if finalizer_retries >= MAX_FINALIZER_RETRIES:
            print(f"🛑 Finalizer critical failure after {finalizer_retries} retries. Terminating.")
            return {
                "next": "END",
                "shared_knowledge": f"Finalizer failed after {finalizer_retries} retries: {e}",
                "sender": "Finalizer",
                "messages": [SystemMessage(content=f"Finalizer terminated: {e}")],
                "_finalizer_retries": finalizer_retries
            }
        return {
            "next": "SUPERVISOR",
            "shared_knowledge": f"Finalizer failed (attempt {finalizer_retries}/{MAX_FINALIZER_RETRIES}): {e}",
            "sender": "Finalizer",
            "messages": [SystemMessage(content=f"Finalizer Failure (retry {finalizer_retries}): {e}")],
            "_finalizer_retries": finalizer_retries
        }
