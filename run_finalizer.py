#!/usr/bin/env python3
"""
v7.3 Standalone Finalizer Script
Directly runs the Finalizer without LangGraph checkpoint system.
Reads the 25 completed report_final.md files, synthesizes via Gemini Pro,
runs critique loop, then assembles final report + Korean translation + PDF.

Usage: python run_finalizer.py [thread_id]
"""
import os
import sys
import re
import glob
from datetime import datetime

# Set up path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.utils import RobustGemini, save_artifact

# --- Configuration ---
THREAD_ID = sys.argv[1] if len(sys.argv) > 1 else "u6ejcd"
MAX_ITERATIONS = 3
ARTIFACT_DIR = os.path.join("artifacts", THREAD_ID)

print(f"🎓 Standalone Finalizer v7.3")
print(f"   Thread ID: {THREAD_ID}")
print(f"   Artifact Dir: {os.path.abspath(ARTIFACT_DIR)}")
print(f"   Max Iterations: {MAX_ITERATIONS}")
print(f"=" * 80)

# --- 1. Load and merge all report_final.md files ---
report_files = glob.glob(os.path.join(ARTIFACT_DIR, "*_report_final.md"))
report_files = [f for f in report_files if not f.endswith('.old_backup')]

def extract_sort_key(filepath):
    filename = os.path.basename(filepath)
    m = re.search(r'step(\d+)_sub(\d+)', filename, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (999, 999)

report_files.sort(key=extract_sort_key)

if not report_files:
    print(f"❌ No report_final.md files found in {ARTIFACT_DIR}")
    sys.exit(1)

print(f"\n📚 Loading {len(report_files)} completed reports...")

# v7.3: Extract step titles from master plan JSON
import json
step_titles = {}
master_plan_files = glob.glob(os.path.join(ARTIFACT_DIR, "*_project_master_plan_raw.md"))
if master_plan_files:
    master_plan_files.sort()
    try:
        with open(master_plan_files[-1], 'r', encoding='utf-8') as f:
            raw = f.read()
            json_str = raw.split("```json")[1].split("```")[0].strip()
            plan_data = json.loads(json_str)
            for step in plan_data.get("steps", []):
                s_id = str(step.get("id", "")).replace("step_", "")
                if s_id.isdigit():
                    step_titles[int(s_id)] = step.get("title", f"Step {s_id}")
    except Exception as e:
        print(f"   ⚠️ Could not parse master plan: {e}")

# v7.3: Extract substep titles from subplan files + report headings (fallback)
substep_titles = {}
subplan_files = glob.glob(os.path.join(ARTIFACT_DIR, "*_subplan.md"))
for sp_file in subplan_files:
    m = re.search(r"step(\d+)_subplan", os.path.basename(sp_file), re.IGNORECASE)
    if m:
        step_idx = int(m.group(1))
        with open(sp_file, 'r', encoding='utf-8') as f:
            sp_content = f.read()
        sub_matches = re.findall(r"###\s*\[.*?\]\s*Sub-Step\s*(\d+):\s*(.*)", sp_content, re.IGNORECASE)
        for sub_match in sub_matches:
            substep_titles[(step_idx, int(sub_match[0]))] = sub_match[1].strip()

# Fallback: extract titles from report file headings
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
            raw_title = re.sub(r'^Step\s+\d+\.\d+:\s*', '', raw_title)
            substep_titles[(s_idx, sub_idx)] = raw_title

# v7.3: Build ToC with proper titles and page numbers
CHARS_PER_PAGE = 3000
current_page = 6  # After deliverable section
all_content_parts = []
toc_lines = ["# 📑 Table of Contents\n"]
current_step = -1

for fpath in report_files:
    fname = os.path.basename(fpath)
    sort_key = extract_sort_key(fpath)
    if sort_key == (999, 999):
        continue
    s_idx, sub_idx = sort_key

    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    step_title = step_titles.get(s_idx, f"Step {s_idx}")
    sub_title = substep_titles.get((s_idx, sub_idx), f"Sub-step {s_idx}.{sub_idx}")
    
    # Add step header on first encounter
    if s_idx != current_step:
        current_step = s_idx
        all_content_parts.append(f"# {s_idx}. {step_title}")
        toc_lines.append(f"\n### Step {s_idx}: {step_title}")
    
    toc_lines.append(f"- {s_idx}.{sub_idx} {sub_title} ···· p.{current_page}")
    current_page += max(1, len(content) // CHARS_PER_PAGE)

    # Clean internal tags
    content = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|DEEPSEEK-R1)[^\]]*\]', '', content, flags=re.IGNORECASE)
    content = re.sub(r"^#\s*Step\s*\d+\.\d+.*?(\n|$)", "", content, flags=re.IGNORECASE | re.MULTILINE)
    
    # Shift headers down to avoid conflicts
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            level_match = re.match(r'^(\s*)(#+)', line)
            if level_match:
                indent = level_match.group(1)
                level = level_match.group(2)
                rest = line[len(indent) + len(level):]
                new_level_len = min(6, len(level) + 2)
                new_lines.append(f"{indent}{'#' * new_level_len} {rest}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    substep_header = f"## 📖 Step {s_idx}.{sub_idx} — {sub_title}"
    chapter_content = "\n".join(new_lines).strip()
    all_content_parts.append(f"{substep_header}\n\n{chapter_content}\n")
    print(f"   ► Loaded: {fname} ({len(content)} chars)")

content_body = "\n".join(toc_lines) + "\n\n---\n\n" + "\n\n".join(all_content_parts)
print(f"\n✅ Total merged content: {len(content_body)} chars (~{len(content_body)//4000}K tokens)")

# Save raw merged report
save_artifact("Project_Raw_Concatenated_Report", content_body, "md", thread_id=THREAD_ID)

# --- 2. Load original user goal ---
goal_files = glob.glob(os.path.join(ARTIFACT_DIR, "*_project_master_plan.md"))
original_goal = "Provide the complete final results of this research."
if goal_files:
    goal_files.sort()
    with open(goal_files[-1], 'r', encoding='utf-8') as f:
        plan_content = f.read()
    # Try to extract the goal from the plan
    goal_match = re.search(r'(?:goal|objective|topic|mission)[:\s]*(.+?)(?:\n|$)', plan_content, re.IGNORECASE)
    if goal_match:
        original_goal = goal_match.group(1).strip()
print(f"\n🎯 User Goal: {original_goal[:200]}...")

# --- 3. System Prompt ---
SYSTEM_PROMPT = """
You are the **Final Deliverable Architect** — the culmination of an extensive, multi-day autonomous research project.
Your task is to produce a beautiful, elegant, and definitive final deliverable from the aggregated research.

**GUIDELINES:**
1. **Adaptive Fulfillment**: 
   - If the user explicitly requested a specific structural deliverable (e.g., Capability Maps, system architectures, frameworks, matrices), you MUST extract and present the EXACT, COMPLETE artifacts. Do NOT summarize — copy them VERBATIM from the research.
   - If the user only requested a general "research report" or "analysis", write a concise, high-level Executive Summary.
2. **CRITICAL — VERBATIM ARTIFACT PRESERVATION**: 
   - All structured artifacts MUST be preserved EXACTLY as they appear:
     * Markdown Tables, Code Blocks, Mathematical Formulas, Architecture Diagrams — all verbatim.
   - You may add commentary AROUND artifacts, but NEVER modify their content.
3. **Beautiful Presentation**: Most important results appear FIRST. Clear headers, logical flow.
4. **Accuracy & Integrity**: Do not hallucinate. Pull data directly from the research.
5. **No References section** — the full research appendix handles that.
6. **Format**: Clean, professional English Markdown.
"""

# --- 4. Iteration Loop ---
llm_pro = RobustGemini(temperature=0.3)
critique_feedback = ""
deliverable = ""

for iteration in range(1, MAX_ITERATIONS + 1):
    print(f"\n{'=' * 80}")
    print(f"🔄 Finalizer Iteration {iteration}/{MAX_ITERATIONS}")
    print(f"{'=' * 80}")
    
    synthesis_prompt = f"""
**Original User Goal (What they explicitly asked for):** 
{original_goal}

**PREVIOUS SUPERVISOR CRITIQUE (Fix these issues if any):**
{critique_feedback if critique_feedback else "None (First Draft)"}

**FULL INPUT RESEARCH REPORT:**
{content_body}

{'=' * 80}
**YOUR TASK:**

You have just read the COMPLETE research report above — the result of an extensive, multi-day autonomous investigation by 11 specialized AI agents.

Now produce a **FINAL DELIVERABLE** that the user can immediately read, understand, and apply to their work.

**Structure:**
1. **Executive Overview** — Concisely summarize the most important strategic insights and conclusions.
2. **Key Deliverables** — Present the core results that directly fulfill the user's Original Goal. Use your own judgment to determine what these are. You may merge, reorganize, or restructure deliverables for clarity — but **preserve the substantive content and data verbatim**. Do NOT abbreviate table cells, formulas, or specifications.
3. **Strategic Commentary** — Add brief contextual analysis and actionable takeaways around each deliverable.

**Quality Standards:**
- Immediately actionable — a practitioner should be able to apply this directly.
- Beautiful, elegant, professional Markdown formatting.
- No fluff or filler — every sentence should add value.
- Do NOT include a references section.
"""
    
    print(f"   📊 Sending {len(content_body)} chars to Gemini Pro...")
    try:
        response = llm_pro.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=synthesis_prompt)
        ])
        
        content_en = response.content
        if isinstance(content_en, list):
            parts = []
            for c in content_en:
                if isinstance(c, dict) and 'text' in c:
                    parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parts.append(c.text)
                else:
                    parts.append(str(c))
            deliverable = " ".join(parts)
        else:
            deliverable = str(content_en)
        
        print(f"   ✅ Deliverable generated: {len(deliverable)} chars")
        
    except Exception as e:
        print(f"   ⚠️ Gemini Pro failed: {e}")
        print(f"   Retrying...")
        continue
    
    # Save draft
    print(f"   📝 Saving Draft #{iteration}...")
    save_artifact(f"Finalizer_Deliverable_Draft_{iteration}", deliverable, "md", thread_id=THREAD_ID)
    
    # --- 5. Critique ---
    print(f"\n   🕵️ Running Supervisor Critique...")
    critique_prompt = f"""
    You are the **Chief Editor & Publisher**.
    Evaluate the Finalizer's ultimate project deliverable.
    
    **Original User Goal:** "{original_goal[:8000]}"
    
    **FINAL DRAFT TO EVALUATE:**
    {deliverable[:500000]}
    
    **CRITERIA:**
    1. Does it perfectly answer the original user goal?
    2. Are the key deliverable artifacts (tables, maps, architectures) present and correctly formatted?
    3. Are there any internal tags, placeholders, or messy formatting?
    4. Is it immediately actionable and professional?
    
    If perfect, output "APPROVED: [praise]".
    If it needs fixing, output "REJECTED: [Numbered list of fixes]".
    """
    
    if iteration >= MAX_ITERATIONS:
        critique_result = "APPROVED: Forced approval after max iterations."
    else:
        try:
            critique_response = llm_pro.invoke([HumanMessage(content=critique_prompt)])
            content = critique_response.content
            if isinstance(content, list):
                critique_result = " ".join(str(c.get('text', c) if isinstance(c, dict) else c) for c in content)
            else:
                critique_result = str(content).strip()
        except Exception as e:
            print(f"   ⚠️ Critique failed: {e}. Auto-approving.")
            critique_result = "APPROVED: Critique failed, auto-approved."
    
    # Save critique
    save_artifact(f"Finalizer_Critique_{iteration}", f"# Finalizer Critique #{iteration}\n\n**Result:** {critique_result}", "md", thread_id=THREAD_ID)
    
    if critique_result.startswith("APPROVED"):
        print(f"\n   ✅ APPROVED: {critique_result[:200]}")
        break
    else:
        print(f"\n   ❌ REJECTED: {critique_result[:500]}")
        critique_feedback = critique_result

# --- 6. Assemble Final Report ---
print(f"\n{'=' * 80}")
print(f"📦 Assembling Final Master Report...")
print(f"{'=' * 80}")

master_report_en = f"# 🎯 Primary Deliverable\n\n{deliverable}\n\n---\n\n# 📚 Full Research Appendix\n\n{content_body}"
saved_path_en = save_artifact("Project_Master_Report_EN", master_report_en, "md", thread_id=THREAD_ID)
print(f"   ✅ English Report saved: {saved_path_en} ({len(master_report_en)} chars)")

# --- 7. Korean Translation ---
print(f"\n🌐 Starting Korean Translation...")
try:
    from langchain_ollama import ChatOllama
    local_translator = ChatOllama(
        model="qwen3-32k:30b-a3b",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.0,
        timeout=300
    )
    
    # Smart chunking
    MAX_CHUNK_CHARS = 4000
    paragraphs = re.split(r'\n\n(?=#+ )', master_report_en)
    CHUNKS = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) > MAX_CHUNK_CHARS and current_chunk:
            CHUNKS.append(current_chunk)
            current_chunk = p
        else:
            current_chunk = current_chunk + "\n\n" + p if current_chunk else p
    if current_chunk:
        CHUNKS.append(current_chunk)
    
    print(f"   📦 Total chunks: {len(CHUNKS)}")
    
    translated_chunks = []
    for idx, chunk in enumerate(CHUNKS):
        print(f"   ► Translating chunk {idx+1}/{len(CHUNKS)}... ({len(chunk)} chars)")
        trans_sys = "You are an expert Technical Translator. Translate the provided English Markdown text into perfectly natural, professional Korean. Preserve ALL Markdown formatting exactly."
        try:
            res = local_translator.invoke([
                SystemMessage(content=trans_sys),
                HumanMessage(content=f"TRANSLATE TO KOREAN:\n\n{chunk}")
            ])
            out_text = str(res.content)
            if out_text.startswith("```markdown\n"):
                out_text = out_text[12:]
                if out_text.endswith("```"):
                    out_text = out_text[:-3]
            translated_chunks.append(out_text.strip())
        except Exception as chunk_err:
            print(f"   ⚠️ Chunk {idx+1} failed: {chunk_err}. Using English.")
            translated_chunks.append(chunk)
    
    master_report_ko = "\n\n".join(translated_chunks)
    saved_path_ko = save_artifact("Project_Master_Report_KO", master_report_ko, "md", thread_id=THREAD_ID)
    print(f"   ✅ Korean Report saved: {saved_path_ko}")
    
except Exception as e:
    print(f"   ⚠️ Korean Translation Failed: {e}")
    master_report_ko = f"# 번역 실패\n\n{e}\n\n" + master_report_en
    saved_path_ko = save_artifact("Project_Master_Report_KO", master_report_ko, "md", thread_id=THREAD_ID)

# --- 8. PDF Conversion ---
print(f"\n📄 Converting to PDF...")
try:
    from app.utils import convert_to_pdf
    if saved_path_en:
        convert_to_pdf(saved_path_en)
        print(f"   ✅ English PDF created")
    if saved_path_ko:
        convert_to_pdf(saved_path_ko)
        print(f"   ✅ Korean PDF created")
except Exception as e:
    print(f"   ⚠️ PDF conversion failed: {e}")

print(f"\n{'=' * 80}")
print(f"🏁 Finalizer Complete!")
print(f"{'=' * 80}")
