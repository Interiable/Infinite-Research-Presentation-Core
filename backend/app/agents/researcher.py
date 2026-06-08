import os
import json
import re

def save_dialogue_message(thread_id, sender, content):
    """Lazy-import wrapper to avoid circular dependency with endpoints.py."""
    try:
        from app.api.endpoints import save_dialogue_message as _sdm
        _sdm(thread_id, sender, content)
    except Exception:
        pass  # Silently fail — dialogue is non-critical
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.agents.local_model import local_llm
from app.utils import RobustGemini, log_night_audit

# --- CONFIGURATION ---
# Using Robust Polyglot Wrapper for Critical Operations if needed
# But for orchestration, we use Flash for speed/cost.
llm_flash = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"), 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=300,
    max_retries=3
)

# Robust Wrapper for Final Polish or strictly following instruction if Local fails HARD
# Standard Pro Orchestration
llm_robust = RobustGemini(temperature=0.3)

# SPECIALIZED DEEP RESEARCH ENGINE
from app.utils import DeepResearcher
deep_research_engine = DeepResearcher(temperature=0.4)

# --- v5.0 GEMMA 4 INTEGRATION ---
# Initialize Gemma 4 for Math/Logic/Engineering tasks
try:
    local_deepseek = local_llm # Unified integration
    print("✅ Gemma-4 Strategy Engine Initialized.")
except Exception as e:
    print(f"⚠️ Failed to initialize Gemma-4: {e}. Fallback to local_llm.")
    local_deepseek = local_llm


SYSTEM_PROMPT = """
You are the **Deep Researcher & Technical Writer**.
Your goal is to build a **Comprehensive, Long-Form Report** on the user's topic.

**LANGUAGE RULE (CRITICAL):**
1. **WRITE IN ENGLISH**: All sections, explanations, and descriptions MUST be in **English**.
2. **Professional Tone**: Logical, expansive, and detailed.

**WRITING STYLE:**
- **Accumulate**: Do not summarize. Explain deeply.
- **Evidence & Citation (STRICT)**: You MUST include inline citations for every factual claim, data point, or formula. Use formats like `[File: filename.pdf]`, `[Web: Source Title]`, `[Patent: US1234]`, or `[Paper: ArXiv Title]`.
- **References Section (STRICT)**: At the very end of your report, you MUST include a "## References" section listing all sources cited in your text. For web sources, include the actual URL as a clickable markdown link: `[Web: Title](https://url)`.
- **CRITIQUE COMPLIANCE (HIGHEST PRIORITY)**: If the Supervisor's critique tells you to change your tone, audience level, remove math, add UX focus, or any other adjustment — YOU MUST OBEY. The Supervisor's critique overrides all other writing preferences. Do not stubbornly keep content the Supervisor told you to remove.
- **ADAPTIVE DEPTH**: Match the technical depth to the research topic. For engineering research, include formulas and derivations. For UX/business research, focus on insights and practical value without complex math. If Scientific Notes are provided, use them as reference but adapt their presentation to the target audience.
- **NO INTERNAL TAGS**: Never include internal markers like `[Scientific Notes]`, `[GEMMA4]`, `[DEEPSEEK-R1]`, `TODO`, or `DEEP_RESEARCH_REQUIRED` in your output. Your output must be clean and professional.
"""

# v3.7 Adaptive Output Mode
CONCISE_SYSTEM_PROMPT = """
You are the **Efficient Content Specialist**.
Your goal is to produce **concise, high-impact content** optimized for presentations and quick reference.

**LANGUAGE RULE:**
1. **WRITE IN ENGLISH**: Use English for all text.

**OUTPUT STYLE:**
- **Be Concise**: Focus on key insights only. No fluff.
- **Match the Purpose**: If it's for slides/PPT, use short phrases and key points.
- **Adapt Length**: Output should be as short as the task requires.
- **Evidence**: Still cite sources, but briefly.
- **CLEAN OUTPUT**: No placeholder tags, TODO markers, or internal notes in the output.
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


# ==============================================================================
# v11.0: FULL-TEXT DEEP READ — Extract details from original papers/patents
# ==============================================================================
def extract_from_fulltext_papers(paper_sources: list, topic: str, max_papers: int = 3, max_chars_per_paper: int = 30000) -> str:
    """
    Reads full original PDFs of high-relevance papers and extracts topic-specific details.
    Uses local LLM (Qwen3) for extraction to avoid API costs.
    
    Args:
        paper_sources: List of dicts with {title, score, source_path}
        topic: Current research topic for targeted extraction
        max_papers: Maximum papers to deep-read (default: 3)
        max_chars_per_paper: Max chars to read from each PDF (default: 30k)
    
    Returns: Extracted details as markdown string
    """
    if not paper_sources:
        return ""
    
    extracted_parts = []
    papers_read = 0
    
    for source in paper_sources[:max_papers]:
        source_path = source.get('source_path', '')
        title = source.get('title', 'Unknown')
        score = source.get('score', 0)
        
        if not os.path.exists(source_path):
            continue
        
        try:
            print(f"   📖 Full-Text Deep Read: {title} (score: {score:.2f})")
            
            # Read full PDF content
            content = ""
            if source_path.lower().endswith('.pdf'):
                try:
                    import pymupdf4llm
                    content = pymupdf4llm.to_markdown(source_path)
                except Exception:
                    try:
                        from pdfminer.high_level import extract_text
                        content = extract_text(source_path)
                    except Exception as e2:
                        print(f"      ⚠️ PDF read failed: {e2}")
                        continue
            else:
                with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            if not content or len(content) < 100:
                continue
            
            # Truncate to max chars
            content = content[:max_chars_per_paper]
            
            # Extract relevant details using local LLM
            extraction_prompt = f"""You are a Technical Content Extractor.

**PAPER TITLE**: "{title}"
**RESEARCH TOPIC**: "{topic}"

**FULL PAPER CONTENT** (may be truncated):
{content}

**YOUR TASK — EXTRACT ONLY THE FOLLOWING (in English):**
1. **Formulas & Equations**: ALL mathematical formulas, derivations, and their parameters (use LaTeX notation)
2. **Algorithms & Methods**: Specific algorithms, pseudocode, step-by-step methods
3. **Technical Parameters**: Specific numbers, thresholds, dimensions, configurations
4. **Key Claims & Findings**: Core technical contributions with supporting data
5. **Relevant Diagrams/Tables**: Describe any critical figures or table data in text form

**RULES:**
- ONLY extract content directly relevant to "{topic}"
- Skip general introductions, literature reviews, and conclusions
- Preserve exact values, units, and notation
- Use markdown formatting with clear section headers
- If the paper is not relevant to the topic, just write "NOT RELEVANT" and skip

**OUTPUT**: Structured extraction in markdown (max ~2000 words):
"""
            response = local_llm.invoke([HumanMessage(content=extraction_prompt)])
            extraction = response.content
            
            if isinstance(extraction, list):
                extraction = " ".join([str(c.get('text', str(c))) if isinstance(c, dict) else str(c) for c in extraction])
            
            # Skip if paper was deemed irrelevant by LLM
            if extraction and "NOT RELEVANT" not in extraction[:50]:
                # Cap extraction to 5000 chars
                if len(extraction) > 5000:
                    extraction = extraction[:5000] + "\n...[truncated]"
                
                extracted_parts.append(
                    f"### 📄 Deep Read: {title} (Relevance: {score:.2f})\n"
                    f"**Source**: {os.path.basename(source_path)}\n\n"
                    f"{extraction}\n"
                )
                papers_read += 1
                print(f"      ✅ Extracted {len(extraction)} chars of detailed content")
            else:
                print(f"      ⏭️ Paper not relevant to current topic, skipped")
                
        except Exception as e:
            print(f"      ⚠️ Full-text extraction failed for {title}: {e}")
    
    if extracted_parts:
        total_chars = sum(len(p) for p in extracted_parts)
        print(f"   🔬 Full-Text Extraction Complete: {papers_read} papers, {total_chars} chars total")
        return "\n---\n".join(extracted_parts)
    return ""


def extract_from_fulltext_patents(patent_sources: list, topic: str, max_patents: int = 3) -> str:
    """
    Reads full original JSONs of high-relevance patents and extracts topic-specific details.
    Patent JSONs contain: abstract, claims, description (from Google Patents scraping).
    
    Args:
        patent_sources: List of dicts with {patent_id, title, score, source_path}
        topic: Current research topic for targeted extraction
        max_patents: Maximum patents to deep-read (default: 3)
    
    Returns: Extracted details as markdown string
    """
    import json as _json
    
    if not patent_sources:
        return ""
    
    extracted_parts = []
    patents_read = 0
    
    for source in patent_sources[:max_patents]:
        source_path = source.get('source_path', '')
        patent_id = source.get('patent_id', 'Unknown')
        title = source.get('title', 'Unknown')
        score = source.get('score', 0)
        
        if not os.path.exists(source_path):
            continue
        
        try:
            print(f"   📖 Full-Text Deep Read: Patent {patent_id} — {title} (score: {score:.2f})")
            
            with open(source_path, 'r', encoding='utf-8') as f:
                patent_data = _json.load(f)
            
            claims = patent_data.get('claims', '')[:15000]
            description = patent_data.get('description', '')[:15000]
            abstract = patent_data.get('abstract', '')
            
            if not claims and not description:
                print(f"      ⚠️ Patent JSON has no claims/description, skipped")
                continue
            
            # Build patent content for extraction
            patent_content = f"Patent: {title}\nPatent ID: {patent_id}\n\n"
            if abstract:
                patent_content += f"Abstract:\n{abstract}\n\n"
            if claims:
                patent_content += f"Claims:\n{claims}\n\n"
            if description:
                patent_content += f"Description:\n{description}\n\n"
            
            extraction_prompt = f"""You are a Patent Analysis Expert.

**PATENT**: "{title}" ({patent_id})
**RESEARCH TOPIC**: "{topic}"

**FULL PATENT CONTENT**:
{patent_content[:30000]}

**YOUR TASK — EXTRACT ONLY THE FOLLOWING (in English):**
1. **Key Claims**: The independent claims most relevant to "{topic}" (verbatim or paraphrased)
2. **Technical Methods**: Specific mechanisms, architectures, or systems described
3. **Novel Contributions**: What makes this patent unique compared to prior art
4. **Technical Parameters**: Specific measurements, configurations, thresholds
5. **Applicable Insights**: How this patent's approach could inform the research topic

**RULES:**
- ONLY extract content directly relevant to "{topic}"
- Preserve claim numbers and exact technical language
- If the patent is not relevant, write "NOT RELEVANT" and skip

**OUTPUT**: Structured extraction in markdown (max ~1500 words):
"""
            response = local_llm.invoke([HumanMessage(content=extraction_prompt)])
            extraction = response.content
            
            if isinstance(extraction, list):
                extraction = " ".join([str(c.get('text', str(c))) if isinstance(c, dict) else str(c) for c in extraction])
            
            if extraction and "NOT RELEVANT" not in extraction[:50]:
                if len(extraction) > 5000:
                    extraction = extraction[:5000] + "\n...[truncated]"
                
                extracted_parts.append(
                    f"### 📋 Deep Read: Patent {patent_id} — {title} (Relevance: {score:.2f})\n\n"
                    f"{extraction}\n"
                )
                patents_read += 1
                print(f"      ✅ Extracted {len(extraction)} chars from patent {patent_id}")
            else:
                print(f"      ⏭️ Patent not relevant to current topic, skipped")
                
        except Exception as e:
            print(f"      ⚠️ Full-text patent extraction failed for {patent_id}: {e}")
    
    if extracted_parts:
        total_chars = sum(len(p) for p in extracted_parts)
        print(f"   🔬 Full-Text Patent Extraction Complete: {patents_read} patents, {total_chars} chars total")
        return "\n---\n".join(extracted_parts)
    return ""


# v13.0: REFERENCE-FIRST WRITING (RFW) — Build Verified Reference Registry
def build_reference_registry(
    available_files, research_dirs,
    paper_sources, patent_sources,
    project_id, topic,
    deep_research_sources=None,
    web_sources=None,
    existing_registry=None
):
    """
    Reads actual source files/DB entries and builds a Verified Reference Registry.
    Only sources with physically confirmed existence are registered.
    
    Returns:
        registry: List[Dict] — Each entry has { ref_id, type, title, path/url/id, key_content, verified }
        all_source_content: str — Combined text of all registered sources for Fact Sheet compression
    """
    import glob as _glob
    
    registry = list(existing_registry) if existing_registry else []
    ref_counter = 1
    
    if registry:
        for r in registry:
            num_part = r['ref_id'].replace("REF-", "")
            if num_part.isdigit():
                val = int(num_part)
                if val >= ref_counter:
                    ref_counter = val + 1

    all_source_content = ""
    # Only newly discovered sources will populate all_source_content for incremental compression

    existing_titles = {r.get('title', '').lower() for r in registry}
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # --- 1. Local Files (project docs) ---
    for file_path in available_files:
        title_lower = os.path.basename(file_path).lower()
        if title_lower in existing_titles:
            continue
            

        content = ""
        file_found = False
        actual_path = ""
        
        for d in research_dirs:
            potential = os.path.join(d.strip(), file_path.strip())
            if os.path.exists(potential):
                actual_path = potential
                file_found = True
                break
        
        if not file_found:
            continue
        
        try:
            _, ext = os.path.splitext(actual_path.lower())
            if ext == '.pdf':
                try:
                    from pdfminer.high_level import extract_text
                    content = extract_text(actual_path)[:50000]
                except Exception:
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(actual_path)
                        content = "\n".join([(p.extract_text() or "") for p in reader.pages])[:50000]
                    except Exception:
                        content = ""
            elif ext in ('.html', '.htm'):
                with open(actual_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_html = f.read()
                content = re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()[:50000]
            elif ext not in {'.css', '.js', '.jsx', '.ts', '.tsx', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.mp4', '.mp3', '.wav', '.zip', '.tar', '.gz', '.pyc'}:
                with open(actual_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:50000]
        except Exception:
            continue
        
        if content and len(content) > 50:
            ref_id = f"REF-{ref_counter:03d}"
            registry.append({
                "ref_id": ref_id,
                "type": "file",
                "title": os.path.basename(file_path),
                "path": file_path,
                "key_content": content[:500],
                "verified": True
            })
            existing_titles.add(title_lower)
            all_source_content += f"\n[{ref_id}] FILE: {file_path}\n{content}\n"
            ref_counter += 1
    
    print(f"📂 Registry: {ref_counter - 1} local files registered (including existing)")
    
    # --- 2. Paper Library sources ---
    if paper_sources:
        for paper in paper_sources:
            if isinstance(paper, dict):
                p_title = paper.get('title', paper.get('metadata', {}).get('source', 'Unknown Paper'))
                if p_title.lower() in existing_titles:
                    continue

                ref_id = f"REF-{ref_counter:03d}"
                p_title = paper.get('title', paper.get('metadata', {}).get('source', 'Unknown Paper'))
                p_content = paper.get('content', paper.get('page_content', ''))
                registry.append({
                    "ref_id": ref_id,
                    "type": "paper",
                    "title": p_title,
                    "score": paper.get('score', 0),
                    "key_content": p_content[:500],
                    "verified": True
                })
                existing_titles.add(p_title.lower())
                all_source_content += f"\n[{ref_id}] PAPER: {p_title}\n{p_content[:3000]}\n"
                ref_counter += 1
    
    # --- 3. Patent Library sources ---
    if patent_sources:
        for patent in patent_sources:
            if isinstance(patent, dict):
                pat_title = patent.get('title', 'Unknown Patent')
                if pat_title.lower() in existing_titles:
                    continue

                ref_id = f"REF-{ref_counter:03d}"
                pat_title = patent.get('title', 'Unknown Patent')
                pat_id = patent.get('patent_id', patent.get('metadata', {}).get('patent_id', ''))
                pat_content = patent.get('content', patent.get('page_content', ''))
                registry.append({
                    "ref_id": ref_id,
                    "type": "patent",
                    "title": pat_title,
                    "patent_id": pat_id,
                    "key_content": pat_content[:500],
                    "verified": True
                })
                existing_titles.add(pat_title.lower())
                all_source_content += f"\n[{ref_id}] PATENT {pat_id}: {pat_title}\n{pat_content[:3000]}\n"
                ref_counter += 1
    
    # --- 4. Web Research files (Semantic Search from ChromaDB) ---
    web_count = 0
    if web_sources:
        for web_src in web_sources:
            if isinstance(web_src, dict):
                source_title = web_src.get('title', 'Unknown Web Source')
                if source_title.lower() in existing_titles:
                    continue

                ref_id = f"REF-{ref_counter:03d}"
                source_title = web_src.get('title', 'Unknown Web Source')
                source_url = web_src.get('url', '')
                body_content = web_src.get('content', '')
                txt_file = web_src.get('source_file', '')
                
                registry.append({
                    "ref_id": ref_id,
                    "type": "web",
                    "title": source_title,
                    "url": source_url,
                    "source_file": txt_file,
                    "key_content": body_content[:500],
                    "verified": True
                })
                existing_titles.add(source_title.lower())
                all_source_content += f"\n[{ref_id}] WEB: {source_title} ({source_url})\n{body_content[:2000]}\n"
                ref_counter += 1
                web_count += 1
                
    print(f"🌐 Registry: {web_count} web sources registered")
    
    # --- 5. Deep Research Sources (freshly discovered this session) ---
    deep_count = 0
    if deep_research_sources:
        for src in deep_research_sources:
            # Only register if source has a verified file/DB entry
            source_file = src.get('source_file', '')
            is_verified = src.get('verified', False) or (source_file and os.path.exists(source_file))
            
            if is_verified:
                # Check if duplicate (same title already in registry)
                if src.get('title', '').lower() not in existing_titles:
                    ref_id = f"REF-{ref_counter:03d}"
                    entry = {
                        "ref_id": ref_id,
                        "type": src['type'],
                        "title": src.get('title', 'Unknown'),
                        "key_content": src.get('content', '')[:500],
                        "verified": True
                    }
                    if src['type'] == 'web':
                        entry['url'] = src.get('url', '')
                        entry['source_file'] = source_file
                    elif src['type'] == 'paper':
                        entry['arxiv_id'] = src.get('arxiv_id', '')
                    elif src['type'] == 'patent':
                        entry['patent_id'] = src.get('patent_id', '')
                    
                    registry.append(entry)
                    existing_titles.add(src.get('title', '').lower())
                    src_content = src.get('content', '')
                    all_source_content += f"\n[{ref_id}] {src['type'].upper()}: {src.get('title', 'Unknown')}\n{src_content[:2000]}\n"
                    ref_counter += 1
                    deep_count += 1
    
    print(f"🔬 Registry: {deep_count} deep research sources registered")
    
    # v13.1 Strict Deduplication by Title
    deduped_registry = []
    seen_titles = set()
    deduped_source_content = ""
    for r in registry:
        title_lower = r.get('title', 'Unknown').strip().lower()
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            deduped_registry.append(r)
            # Reconstruct source string to eliminate duplicate texts
            src_tag = f"[{r['ref_id']}] {r['type'].upper()}: {r.get('title', 'Unknown')} {r.get('url', r.get('path', ''))}"
            deduped_source_content += f"\n{src_tag}\n{r.get('key_content', '')[:2000]}\n"
            
    registry = deduped_registry
    all_source_content = deduped_source_content

    print(f"✅ TOTAL VERIFIED REFERENCE REGISTRY: {len(registry)} sources")
    
    return registry, all_source_content

def read_full_docs(file_paths, research_dirs, max_chars=10_000_000):
    """
    Reads full content of specific files for deep analysis.
    Supports PDF and Text formats.
    """
    full_text = ""
    # v4.2b: Skip only pure binary/media/code files. HTML is TEXT-EXTRACTED (not skipped).
    SKIP_EXTENSIONS = {'.css', '.js', '.jsx', '.ts', '.tsx',
                       '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
                       '.mp4', '.mp3', '.wav', '.zip', '.tar', '.gz', '.pyc'}
    
    for rel_path in file_paths:
        # Skip binary/code file types
        _, ext = os.path.splitext(rel_path.lower())
        if ext in SKIP_EXTENSIONS:
            print(f"   ⏭️ Skipping binary/code file: {rel_path}")
            continue
        
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
            elif target_path.lower().endswith(('.html', '.htm')):
                # v4.2b: Extract TEXT ONLY from HTML (strip all tags, CSS, JS)
                with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_html = f.read()
                # Remove <style> and <script> blocks entirely
                import re as _re
                raw_html = _re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=_re.DOTALL | _re.IGNORECASE)
                raw_html = _re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=_re.DOTALL | _re.IGNORECASE)
                # Strip remaining HTML tags, keep text
                content = _re.sub(r'<[^>]+>', ' ', raw_html)
                # Clean up excessive whitespace
                content = _re.sub(r'\s+', ' ', content).strip()
                print(f"🌐 HTML Text Extracted: {rel_path} ({len(content)} chars)")
            else:
                # Text files (.md, .txt, .csv, etc.)
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
    try:
        # Extract Thread ID
        thread_id = config.get("configurable", {}).get("thread_id", None)
        
        # --- v3.14 DEFINITIVE SCOPE FIX ---
        context_prompt = "" # Initialized here to prevent ANY UnboundLocalError
        
        # Initialize critical variables FIRST
        project_id = state.get('project_id', 'default')
        topic = state.get('research_topic')
        if not topic or topic == 'Unknown Topic':
            tmp_idx = state.get('current_step_index', 0)
            tmp_plan = state.get('plan', [])
            topic = tmp_plan[tmp_idx].get('title', 'Deep Investigation') if tmp_plan and tmp_idx < len(tmp_plan) else 'Deep Investigation'
        mode = state.get('research_mode', 'deep')
        
        # --- v3.18 SCIENTIFIC SPECIALIST PATTERN ---
        # Lead Writer is always Qwen3 for consistent tone
        selected_llm = local_llm 
        model_name = "Qwen3:30b"
        
        # 1. Detect if High-Logic Reasoning is required
        try:
            current_step_desc = ""
            if state.get("plan") and state["current_step_index"] < len(state["plan"]):
                current_step_desc = state["plan"][state["current_step_index"]].get('description', '')
            
            task_desc = current_step_desc.lower()
            topic_desc = topic.lower() # Use already extracted topic
            
            # Technical Keywords for DeepSeek Trigger
            tech_keywords = [
                "formula", "equation", "optimization", "algorithm", "calculation", "derivation", 
                "kinematics", "dynamics", "dmp", "physics", "engineering", "modeling", "simulation", 
                "urdf", "joint limit", "constraint", "torque", "velocity", "acceleration", "stiffness",
                "수식", "공식", "계산", "증명", "기구학", "역학", "제약조건", "한계값"
            ]
            
            # Robust Extraction
            critique_val = state.get('critique_feedback', '')
            critique_feedback = str(critique_val).lower() if not isinstance(critique_val, list) else " ".join([str(m) for m in critique_val]).lower()
            
            shared_val = state.get('shared_knowledge', '')
            research_notes = str(shared_val).lower()
            
            # 💡 Supervisor Priority Override: If critique explicitly demands math/physics, we FORCE DeepSeek.
            force_keywords = ["수식", "공식", "계산", "물리", "physics", "formula", "derivation", "kinematics", "urdf", "제약조건"]
            force_reasoning = any(k in critique_feedback for k in force_keywords)
            
            # Debug keyword hits
            hitting_keywords = [k for k in tech_keywords if k in task_desc or k in critique_feedback or k in research_notes]
            if hitting_keywords:
                print(f"🔍 Tech Keywords Hit: {hitting_keywords}")

            # Expanded detection logic
            requires_reasoning = (
                any(k in task_desc for k in tech_keywords) or 
                any(k in topic_desc for k in ["physics", "math", "engineering", "robotics"]) or
                any(k in critique_feedback for k in tech_keywords) or
                any(k in research_notes for k in ["formula", "derivation", "proof", "계산", "수식"])
            )
            
            # If keywords match, double check with Flash to avoid over-use (UNLESS FORCED)
            if requires_reasoning:
                if force_reasoning:
                    print("🔥 Supervisor Force Override: Technical requirement detected in critique. Activating Gemma4.")
                else:
                    print("🧠 Tech keywords detected. Validating with Flash...")
                    # Add critique context to Flash check for higher accuracy
                    complexity_check = f"""
                    **Task**: "{current_step_desc}"
                    **Critique**: "{critique_feedback[:1000]}"
                    **Context**: "{topic_desc}"
                    **Question**: Does this task require complex mathematical derivation, scientific reasoning, or algorithmic optimization? 
                    If the critique asks for formulas, calculations, or physical constraint proofs, respond 'YES'.
                    Respond with 'YES' or 'NO' followed by a brief reason.
                    """
                    check_res = llm_flash.invoke([HumanMessage(content=complexity_check)])
                    
                    # UBER-ROBUST PARSING
                    raw_content = check_res.content
                    if isinstance(raw_content, list):
                        check_content = " ".join([str(c) for c in raw_content]).upper()
                    else:
                        check_content = str(raw_content).upper()
                        
                    print(f"🤔 Flash Validation Result: {check_content[:150]}...")
                    
                    import re
                    if not re.search(r'\bYES\b', check_content):
                        requires_reasoning = False
                        print("🍃 Reasoning bypass: Task determined as descriptive/general by Flash.")

            scientific_notes = ""
            if requires_reasoning:
                print(f"🧪 Activating Scientific Specialist (Gemma-4-31B) for '{topic}'...")
                
                # MIRROR CONTEXT: Gemma4 gets everything Qwen3 sees
                # (We will build the mirrored_context after context preparation below)
                pass # Logic will be inserted after context_prompt is built
        except Exception as e:
            print(f"⚠️ Reasoning Detection Failed: {e}")
            requires_reasoning = False
        
        
        topic = state.get('research_topic')
        if not topic or topic == 'Unknown Topic':
            tmp_idx = state.get('current_step_index', 0)
            tmp_plan = state.get('plan', [])
            topic = tmp_plan[tmp_idx].get('title', 'Deep Investigation') if tmp_plan and tmp_idx < len(tmp_plan) else 'Deep Investigation'
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
        
        sub_plan = state.get('sub_plan', [])
        if sub_plan and isinstance(sub_plan, list) and len(sub_plan) > current_sub_idx:
            current_step_details = str(sub_plan[current_sub_idx])
        elif plan and isinstance(plan, list) and len(plan) > current_step_idx:
            current_step_details = str(plan[current_step_idx])
        
        # --- v3.20 Strict Context Handover (Previous Step Output) ---
        last_completed_path = state.get('last_completed_step_path', '')
        if last_completed_path and os.path.exists(last_completed_path):
            try:
                with open(last_completed_path, "r") as f:
                    last_completed_content = f.read()
                recent_last_completed = last_completed_content[-15000:] if len(last_completed_content) > 15000 else last_completed_content
                context_prompt += f"\n\n**[PREVIOUS STEP COMPLETED RESULT]:**\n{recent_last_completed}\n\n**CRITICAL INSTRUCTION**: You MUST build upon this logically. Do not rewrite it. Proceed explicitly to the requirements of the CURRENT step.\n"
                print(f"📖 Loaded Previous Step Completed Output ({len(last_completed_content)} chars)")
            except Exception as e:
                print(f"⚠️ Failed to read previous step output: {e}")

        # --- v3.4 Recursive Master Report Injection (TOC Only) ---
        master_report_content = ""
        incremental_path = state.get('incremental_report_path', '')
        if incremental_path and os.path.exists(incremental_path):
            try:
                with open(incremental_path, "r") as f:
                    master_report_content = f.read()
            except Exception as e:
                print(f"⚠️ Failed to read incremental report: {e}")

        if master_report_content:
            # Inject Master Report (Full Context up to 500,000 chars) for Gemini 1.5 Flash
            report_head = master_report_content[:500000] if len(master_report_content) > 500000 else master_report_content
            context_prompt += f"\n\n**Master Project Context (Full Historical Goals & Taxonomy):**\n{report_head}\n\n"

        if local_context:
            # v3.12: Qwen3 32k Mode - 10,000 chars background
            safe_local_context = local_context[:20000] if len(local_context) > 20000 else local_context
            context_prompt += f"\n\n**Background Knowledge Summary:**\n{safe_local_context}\n\n**Instruction:** Use the information above for drafting."

        # --- PERSISTENT DEEP RESEARCH RECOVERY ---
        # If Supervisor rejected the draft, 'previous_summary' might just contain the rejected Chapter output.
        # So we MUST recover the latest Research Notes from the artifacts directory!
        try:
            import glob
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            artifacts_dir = os.path.join(base_dir, "artifacts", thread_id)
            
            # Look for the latest research notes for THIS specific step/sub-step
            # Note: save_artifact() converts filenames to lowercase, so we search lowercase
            search_pattern = os.path.join(artifacts_dir, f"*_step{current_step_idx+1}_sub{current_sub_idx+1}_research_notes_v*.md")
            note_files = glob.glob(search_pattern)
            
            if note_files:
                latest_note_file = max(note_files, key=os.path.getmtime)
                with open(latest_note_file, "r") as f:
                    recovered_notes = f.read()
                
                # Inject it directly into previous_summary so downstream logic catches it
                previous_summary = f"RESEARCH NOTES\n\n{recovered_notes}\n\n" + str(previous_summary)
                print(f"🔄 Memory Integration: Recovered previous Deep Research Notes ({len(recovered_notes)} chars).")
        except Exception as e:
            print(f"⚠️ Artifact Recovery Failed for Research Notes: {e}")

        # --- v3.16 DATA SYNERGY: Ingest Research Findings ---
        if previous_summary:
            if "RESEARCH NOTES" in previous_summary:
                safe_research = previous_summary[:25000] if len(previous_summary) > 25000 else previous_summary
                context_prompt += f"""\n\n**🔬 NEW RESEARCH FINDINGS (From Deep Investigator) — PRIMARY SOURCE FOR THIS UPDATE:**
{safe_research}

**⚠️ TARGETED UPDATE INSTRUCTIONS (CRITICAL):**
The Supervisor requested additional research because your previous draft lacked depth in specific areas. The findings above are the result of that targeted research (papers, web, patents).
1. **USE THESE FINDINGS AS YOUR PRIMARY SOURCE**: When updating sections that were flagged as insufficient, cite from these new research findings using `[Web: ...]`, `[Paper: ...]`, or `[Patent: ...]` — NOT from existing local `[File: ...]` sources.
2. **DO NOT DO A FULL REWRITE**: Only update the specific sections/claims that the Supervisor's critique identified as needing more research. Preserve everything else from your previous draft.
3. **CITATION PRIORITY**: For any NEW content you add, prefer `[Web: ...]`, `[Paper: ...]`, `[Patent: ...]` over `[File: ...]`. Local files are project specs — the new research findings are the external evidence the Supervisor wanted.
4. **If the new findings contradict a local file claim**, note the discrepancy and prefer the peer-reviewed or recent source."""
                print(f"🧬 Synergy: Injected Deep Research Notes ({len(safe_research)} chars)")
            elif not critique:
                # v3.16+: Ingest general web research if no critique (Revision mode) is active
                safe_web = previous_summary[:15000] if len(previous_summary) > 15000 else previous_summary
                context_prompt += f"""\n\n**🌐 LATEST RESEARCH FINDINGS (Web/Papers/Patents):**
{safe_web}

**Instruction**: Use these findings to enrich your report sections that lack external evidence. When adding new claims from these findings, cite them with `[Web: ...]`, `[Paper: ...]`, or `[Patent: ...]` — prefer these over `[File: ...]` for newly added content."""
                print(f"🌐 Synergy: Injected Web Research Findings ({len(safe_web)} chars)")

        if critique:
            # v5.3: CRITIQUE MUST BE AT THE TOP of context (prepend, not append)
            # Qwen3 pays most attention to the beginning of context
            critique_block = f"\n\n**[MANDATORY] SUPERVISOR CRITIQUE — YOU MUST ADDRESS EVERY POINT BELOW:**\n{critique}\n"
            
            if "RESEARCH NOTES" not in previous_summary:
                safe_previous = previous_summary[:15000] if len(previous_summary) > 15000 else previous_summary
                critique_block += f"\n**PREVIOUS DRAFT (Sample — Fix the issues above):**\n{safe_previous}\n"
            else:
                recovered_draft = "No previous draft found."
                if state.get('messages'):
                    for msg in reversed(state['messages']):
                        if hasattr(msg, 'name') and msg.name == "Researcher":
                             recovered_draft = msg.content
                             break
                safe_recovered = recovered_draft[:10000] if len(recovered_draft) > 10000 else recovered_draft
                critique_block += f"\n**PREVIOUS DRAFT (Recovered — Fix the issues above):**\n{safe_recovered}\n"
                print(f"🔄 Memory Integration: Recovered previous draft ({len(safe_recovered)} chars) for synthesis.")
            
            # PREPEND critique to context_prompt so it's read FIRST
            context_prompt = critique_block + context_prompt
            print(f"📌 Critique injected at TOP of context ({len(critique)} chars).")

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

        # --- v3.18 SCIENTIFIC NOTES INJECTION (MIRRORED CONTEXT) ---
        if requires_reasoning:
            try:
                # Build Mirrored Context for DeepSeek
                # (Includes local files, master report history, and latest research notes)
                mirrored_context = f"""
**FULL DATA CONTEXT FOR REASONING:**

**1. LOCAL KNOWLEDGE (Files):**
{local_context[:20000]}

**2. MASTER REPORT PROGRESS (Incremental):**
{master_report_content[-20000:] if len(master_report_content) > 20000 else master_report_content}

**3. LATEST RESEARCH FINDINGS (Deep Investigator):**
{previous_summary[:15000] if "RESEARCH NOTES" in str(previous_summary) else "No new research notes."}

**TECHNICAL GOAL:**
Analyze the engineering/mathematical logic for sub-step: "{current_step_desc}"
Focus on deriving formulas, logical proofs, and technical parameters.

**WRITING RULE**: 
1. Think deeply (Chain-of-Thought).
2. PROVIDE CONCRETE FORMULAS, PARAMETERS, and LOGICAL DERIVATIONS.
3. Language: English (for technical precision).
"""
                print("🧠 Gemma-4-31B is thinking with full mirrored context...")
                reasoning_res = local_deepseek.invoke([
                    SystemMessage(content="You are a Scientific Reasoning Specialist. Solve technical/mathematical puzzles based on provided context."),
                    HumanMessage(content=mirrored_context)
                ])
                scientific_notes = reasoning_res.content
                
                # v5.2: Save Scientific Notes as artifact for auditability
                from app.utils import save_artifact
                import time as _time
                sci_filename = f"Step{current_step_idx+1}_Sub{current_sub_idx+1}_Scientific_Notes_v{iteration+1}"
                save_artifact(sci_filename, scientific_notes, "md", thread_id=thread_id)
                
                # Inject findings into Qwen3's context
                context_prompt = f"\n\n**[CRITICAL] SCIENTIFIC SPECIALIST NOTES (From Gemma-4-31B):**\n{scientific_notes}\n\n**HOW TO USE THESE NOTES:**\n1. READ and UNDERSTAND the logic, derivations, and parameters above.\n2. ASSESS YOUR AUDIENCE: Look at the research topic and the Supervisor's critique. Is this engineering research or UX/business research?\n3. FOR ENGINEERING/SCIENTIFIC RESEARCH: Include formulas, derivations, and technical parameters.\n4. FOR UX/BUSINESS/STRATEGY RESEARCH: Do NOT copy any math formulas ($, \\\\, equations) into your report. Instead, translate the underlying insight into UX value. Example: Instead of writing '$v(t) = A \\cdot \\sin(2\\pi f t)$', write 'An organic breathing rhythm at 0.5Hz creates the illusion of biological vitality, building subconscious trust.'\n5. NEVER include the tag '[Scientific Notes]' or '[DEEPSEEK-R1]' in your output." + context_prompt
                print(f"🧪 Scientific Notes successfully injected ({len(scientific_notes)} chars).")
                save_dialogue_message(thread_id, "Gemma4 (Science)", f"🧪 Scientific analysis complete ({len(scientific_notes)} chars). Key findings injected into Researcher's context.")

                # --- v5.1 DYNAMIC SCOPE GUARD ---
                scope_guard_instruction = f"""
                
**[STRICT BOUNDARY GUARD - Step {current_step_idx + 1}.{current_sub_idx + 1}]**
The current task is STRICTLY limited to: "{current_step_desc}"
1. Write ONLY about topics directly required by the current step description above.
2. If the PREVIOUS DRAFT contains sections outside this scope, **DELETE THEM COMPLETELY**.
3. If a concept connects to a future step, mention the connection in ONE sentence maximum, then move on.
4. Do NOT elaborate on topics that will be covered in subsequent steps.
"""
                context_prompt = scope_guard_instruction + context_prompt
                print(f"🛡️ Scope Guard Activated: Step {current_step_idx + 1}.{current_sub_idx + 1} boundaries enforced.")

            except Exception as e:
                print(f"⚠️ Scientific reasoning fail: {e}. Qwen3 will proceed solo.")

        # --- v3.8 LIVE-SCAN: Real-time File Ingestion ---
        from app.utils.config_manager import ConfigManager
        cm = ConfigManager()
        research_dirs = cm.get_project_folders(project_id)
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
        
        # 0.5. DEEP RESEARCH CHECK (UPDATED: LOCAL-FIRST STRATEGY)
        # Only trigger Deep Research if:
        # 1. Supervisor EXPLICITLY requested "deep_web" mode (due to missing data).
        # 2. Or if we found ZERO relevant local files (Critical data gap).
        # 3. User explicitly asked for "external" search in the topic string.
        # 4. User enabled Web/Media search in the UI (supplemental research even with local files).
        
        already_researched = (previous_summary and "RESEARCH NOTES" in previous_summary) or bool(critique)
        
        search_options = state.get('search_options', {})
        force_web_mode = (mode == "deep_web") and not already_researched
        insufficient_local_data = (len(available_files) == 0) and not already_researched
        explicit_user_request = ("external search" in topic.lower() or "search web" in topic.lower()) and not already_researched
        user_enabled_web_search = (search_options.get('web', False) or search_options.get('media', False)) and not already_researched

        if force_web_mode or insufficient_local_data or explicit_user_request or user_enabled_web_search:
            if user_enabled_web_search and not (force_web_mode or insufficient_local_data or explicit_user_request):
                reason = "User Enabled Web/Media Search"
            else:
                reason = "Supervisor Request" if force_web_mode else ("No Local Files" if insufficient_local_data else "User Request")
            print(f"📡 Delegating to Deep Researcher ({reason}) for: {topic}")
            
            # Delegate to the full DEEP_RESEARCHER node via the Supervisor.
            # This activates the complete pipeline: keyword optimization, media search,
            # web library indexing, full page scraping, academic/patent search.
            return {
                "sender": "Researcher",
                "research_topic": topic,
                "research_mode": "deep_web",
                "iteration_count": iteration,
                "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                "messages": [SystemMessage(content=f"DELEGATE_DEEP_RESEARCH: {topic}. Reason: {reason}. Full Deep Research pipeline required.")]
            }

        print(f"📚 Recursive Writer Started. Topic: {topic}")
        print(f"📂 Full Library Access: {len(available_files)} files found.")

        # v4.5 + v11.0: Search Local Paper Library + Full-Text Deep Read
        local_paper_context = ""
        fulltext_paper_extraction = ""
        try:
            from app.core.rag import PaperLibrary
            paper_lib = PaperLibrary(project_id=project_id)
            local_paper_context, paper_sources = paper_lib.search_papers_with_sources(topic, k=30)
            if local_paper_context:
                print(f"📚 Local Paper Library: Injecting {len(local_paper_context)} chars of academic context.")
                save_dialogue_message(thread_id, "Archivist (RAG)", f"📚 Found relevant papers from local library. Injecting {len(local_paper_context)} chars of academic context.")
            
            # v11.0: Full-Text Deep Read for high-relevance papers
            if paper_sources:
                fulltext_paper_extraction = extract_from_fulltext_papers(paper_sources, topic, max_papers=3)
                if fulltext_paper_extraction:
                    local_paper_context += f"\n\n--- DEEP READ: FULL-TEXT PAPER EXTRACTIONS ---\n{fulltext_paper_extraction}"
                    print(f"📖 Full-Text Paper Extraction: +{len(fulltext_paper_extraction)} chars of detailed content added.")
                    save_dialogue_message(thread_id, "Archivist (Deep Read)", f"📖 Read {len(paper_sources[:3])} full papers. Extracted {len(fulltext_paper_extraction)} chars of formulas/details.")
        except Exception as e:
            print(f"⚠️ Paper Library search skipped: {e}")

        # v9.2 + v11.0: Patent Library Injection + Full-Text Deep Read
        local_patent_context = ""
        fulltext_patent_extraction = ""
        search_options = state.get("search_options", {})
        
        if search_options.get("patent", True):
            try:
                from app.core.rag import PatentLibrary
                patent_lib = PatentLibrary(project_id=project_id)
                local_patent_context, patent_sources = patent_lib.search_patents_with_sources(topic, k=20)
                if local_patent_context:
                    print(f"📋 Patent Library: Injecting {len(local_patent_context)} chars of patent context.")
                    save_dialogue_message(thread_id, "Archivist (RAG)", f"📋 Found relevant patents from patent library. Injecting {len(local_patent_context)} chars of patent context.")
                
                # v11.0: Full-Text Deep Read for high-relevance patents
                if patent_sources:
                    fulltext_patent_extraction = extract_from_fulltext_patents(patent_sources, topic, max_patents=3)
                    if fulltext_patent_extraction:
                        local_patent_context += f"\n\n--- DEEP READ: FULL-TEXT PATENT EXTRACTIONS ---\n{fulltext_patent_extraction}"
                        print(f"📖 Full-Text Patent Extraction: +{len(fulltext_patent_extraction)} chars of claims/details added.")
                        save_dialogue_message(thread_id, "Archivist (Deep Read)", f"📖 Read {len(patent_sources[:3])} full patents. Extracted {len(fulltext_patent_extraction)} chars of claims/details.")
            except Exception as e:
                print(f"⚠️ Patent Library injection skipped: {e}")
        else:
            print(f"⚠️ Patent Library injection skipped: user explicitly disabled patent search.")

        # v12.0: Web Search Library Injection (Previously found web results from chroma_web_library)
        local_web_context = ""
        try:
            from app.core.rag import WebSearchLibrary
            web_lib = WebSearchLibrary(project_id=project_id)
            local_web_context = web_lib.search(topic, k=15)
            if local_web_context:
                print(f"🌐 Web Search Library: Injecting {len(local_web_context)} chars of previously found web data.")
                save_dialogue_message(thread_id, "Archivist (Web DB)", f"🌐 Found relevant web results from Web Search Library DB. Injecting {len(local_web_context)} chars.")
        except Exception as e:
            print(f"⚠️ Web Search Library injection skipped: {e}")

        # 1. BLUEPRINTING (TOC Generation)
        toc_prompt = f"""
        You are the Lead Editor.
        **CURRENT TASK:** Create a Table of Contents for a report on: "{topic}".
        
        **CURRENT STEP DETAILS (PRIMARY TRUTH):**
        "{current_step_details}"

        **NEWLY RESEARCHED CONTEXT (DEEP RESEARCH RESULTS):**
        {previous_summary[:10000] if previous_summary else "No new research data."}
        
        **DB KNOWLEDGE BASE (HISTORICAL PAPERS/PATENTS/WEB):**
        {local_paper_context[:5000] if local_paper_context else "No DB paper data."}
        {local_patent_context[:5000] if local_patent_context else "No DB patent data."}
        {local_web_context[:5000] if local_web_context else "No DB web data."}

        **SCOPE CONSTRAINT (ULTRA-STRICT):**
        - You are currently only responsible for **Step {current_step_idx + 1}.{current_sub_idx + 1}**.
        - Focus **ONLY** on the "Current Step Details" and the "Newly Researched Context". 
        - **REDUNDANCY CHECK**: If a topic is already covered in the report intro or summary (provided in context), DO NOT create a new chapter for it. 
        - **NEGATIVE CONSTRAINT**: DO NOT generate chapters for future steps like Theory of Mind (ToM) or Laban (LMA) if the current step is 1.1 (10 Principles). 
        - Output 3-6 chapters that each cover ONE focused aspect of the current step.
        - **SCOPE PROPORTIONALITY (CRITICAL):** Remember that each chapter is a subdivision of a sub-plan, NOT an independent report.
          Adjust each chapter's scope based on its topic's importance and complexity.
          If a single chapter's scope feels too large to cover thoroughly in one writing pass, split it into multiple smaller chapters.
          Each chapter must be a focused, manageable slice — not a comprehensive survey of the entire sub-step.
        
        **Available Local Files (Full Library):**
        {", ".join(available_files)}
        
        **Instruction:**
        - **HOLISTIC SYNTHESIS (CRITICAL)**: You MUST systematically synthesize both the "CURRENT STEP DETAILS" and the "NEWLY RESEARCHED CONTEXT" to design the overall chapter plan. The new findings and SOTA papers must organically shape the core narrative and structure of the chapters, rather than just being isolated into a separate section.
        - Select ANY file from the 'Available Local Files' that is relevant to the CURRENT STEP.
        - Whenever a chapter relies on insights, data, or SOTA concepts from the Newly Researched Context, you MUST include "Deep_Research_Results" as an item in its "files" array to explicitly cite it.
        - **GLOBAL NUMBERING**: Use chapter numbers starting with **{current_step_idx + 1}.{current_sub_idx + 1}** as the prefix.
          For example, if this is Step 2, Sub-Step 1, chapters should be numbered 2.1.1, 2.1.2, 2.1.3, etc.
        - **TITLES MUST BE IN ENGLISH**.
        - Output JSON ONLY.
        
        Format:
        {{
          "chapters": [
            {{ "title": "{current_step_idx + 1}.{current_sub_idx + 1}.1 Analysis of [File Name]", "files": ["path/to/relevant_doc.pdf"] }},
            {{ "title": "{current_step_idx + 1}.{current_sub_idx + 1}.2 Synthesizing [Concept]", "files": ["Deep_Research_Results"] }}
          ]
        }}
        """
        
        # v5.4: PERSISTENT CHAPTER PLANNING
        # If chapter_plan already exists in state, reuse it. Otherwise generate.
        chapters = state.get('chapter_plan', [])
        
        if chapters:
            print(f"♻️ Reusing existing Chapter Plan ({len(chapters)} chapters).")
        else:
            try:
                print("⚡ Structuring Chapter Plan with Gemini Flash...")
                # Use llm_flash (Gemini Flash) for structuring massive context rapidly
                toc_response = llm_flash.invoke([HumanMessage(content=toc_prompt)])
                
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
                print(f"📊 New Chapter Plan Generated: {len(chapters)} chapters.")
                
                # v5.4.1: Save Chapter Plan as visible artifact
                from app.utils import save_artifact
                toc_md = f"# 📋 Chapter Plan for Step {current_step_idx+1}.{current_sub_idx+1}\n\n"
                toc_md += "Researcher has structured the following chapters for this sub-step:\n\n"
                for idx, ch in enumerate(chapters):
                    toc_md += f"### Chapter {idx+1}: {ch.get('title')}\n"
                    toc_md += f"- **Sources**: {', '.join(ch.get('files', []))}\n\n"
                
                save_artifact(f"Step{current_step_idx+1}_Sub{current_sub_idx+1}_Chapter_Plan", toc_md, "md", thread_id=thread_id)
                print(f"📖 Chapter Plan saved as artifact: Step{current_step_idx+1}_Sub{current_sub_idx+1}_Chapter_Plan")
                
            except Exception as e:
                print(f"⚠️ TOC Generation Failed: {e}. Fallback to single chapter.")
                chapters = [{"title": "Analysis Report", "files": available_files}]

            # v10.9: New Sub-Step started -> Clear the Fact Sheet Cache
            cached_master_fact_sheet = ""

        import time
        start_time = time.time()

        # --- v13.0 REFERENCE-FIRST WRITING: SOURCE READING & REGISTRY ---
        # Instead of ad-hoc pre-digestion, we build a VERIFIED Reference Registry
        # that enumerates every citable source BEFORE writing begins.
        from app.utils.config_manager import ConfigManager
        cm = ConfigManager()
        research_dirs = cm.get_project_folders(project_id)
        
        # Pull from AgentState to avoid re-reading for every chapter
        cached_master_fact_sheet = state.get('cached_master_fact_sheet', "")
        registry = state.get('verified_reference_registry', [])
        
        # v13.1: Strict Registry Deduplication by Title (Fix for Checkpoint Accumulation)
        if registry:
            dedup_reg = []
            seen_titles = set()
            for r in registry:
                title_lower = r.get('title', 'Unknown').strip().lower()
                if title_lower not in seen_titles:
                    seen_titles.add(title_lower)
                    dedup_reg.append(r)
            registry = dedup_reg

        
        # ALWAYS evaluate new RAG and Deep Sources to continuously augment the registry
        try:
            # Collect all unique files from chapter plan
            all_required_files = set()
            for chap in chapters:
                for f in chap.get('files', []):
                    all_required_files.add(f)
            
            # Get paper and patent source metadata for registry
            paper_sources_meta = []
            try:
                from app.core.rag import PaperLibrary
                paper_lib = PaperLibrary(project_id=project_id)
                _, paper_sources_meta = paper_lib.search_papers_with_sources(topic, k=30)
            except Exception:
                pass
            
            patent_sources_meta = []
            try:
                from app.core.rag import PatentLibrary
                patent_lib = PatentLibrary(project_id=project_id)
                _, patent_sources_meta = patent_lib.search_patents_with_sources(topic, k=20)
            except Exception:
                pass
            
            web_sources_meta = []
            try:
                from app.core.rag import WebSearchLibrary
                web_lib = WebSearchLibrary(project_id=project_id)
                _, web_sources_meta = web_lib.search_web_with_sources(topic, k=30)
            except Exception:
                pass
            
            # Get Deep Research sources (from Deep Researcher if available)
            deep_sources = state.get('deep_research_sources', [])
            
            print(f"📋 Incrementally Updating Verified Reference Registry...")
            # Append new discoveries to existing registry
            registry, new_source_content = build_reference_registry(
                available_files=sorted(list(all_required_files)), # Ensure deterministic mapping
                research_dirs=research_dirs,
                paper_sources=paper_sources_meta,
                patent_sources=patent_sources_meta,
                project_id=project_id,
                topic=topic,
                deep_research_sources=deep_sources,
                web_sources=web_sources_meta,
                existing_registry=registry
            )
            
            # Also read RAG context for fact sheet enrichment (only if new_source_content has data)
            if local_paper_context:
                new_source_content += f"\n\n--- ACADEMIC PAPERS RAG CONTEXT ---\n{local_paper_context}"
            if local_patent_context:
                new_source_content += f"\n\n--- PATENT RAG CONTEXT ---\n{local_patent_context}"
            if local_web_context:
                new_source_content += f"\n\n--- WEB SEARCH RAG CONTEXT ---\n{local_web_context}"
            
            # Compress into Master Fact Sheet with registry awareness (Incremental Append)
            if new_source_content.strip():
                if len(new_source_content) > 3000:
                    # Build registry summary for the compression prompt
                    registry_listing = "\n".join([
                        f"[{r['ref_id']}] {r['type'].upper()}: {r['title']}" 
                        for r in registry
                    ])
                    
                    compression_prompt = f"""
                    **Task: Extract Core Facts from NEW Data Sources**
                    You are adding findings from new documents to an ongoing research database.
                    
                    **Topic:** "{topic}"
                    
                    **VERIFIED REFERENCE REGISTRY (Available to cite):**
                    {registry_listing}
                    
                    **NEW SOURCE DATA:**
                    {new_source_content[:500000]}
                    
                    **Instruction (CRITICAL):**
                    1. Extract ALL concrete data points, numbers, technical constraints, formulas, and code logic.
                    2. For EACH extracted fact, preserve the [REF-XXX] tag so the writer knows which source it came from.
                    3. Compress densely. Remove fluff, keep facts with their source tags.
                    4. Example output line: "DMP achieves 4659x speedup via closed-form basis functions [REF-003]"
                    """
                    
                    try:
                        compress_res = llm_flash.invoke([SystemMessage(content="You are an expert data distillation engine. Always preserve [REF-XXX] source tags."), HumanMessage(content=compression_prompt)])
                        raw_content = compress_res.content
                        compressed_str = ""
                        if isinstance(raw_content, list):
                            parts = []
                            for c in raw_content:
                                if isinstance(c, dict) and 'text' in c:
                                    parts.append(c['text'])
                                elif hasattr(c, 'text'):
                                    parts.append(c.text)
                                else:
                                    parts.append(str(c))
                            compressed_str = " ".join(parts)
                        else:
                            compressed_str = str(raw_content)
                        
                        cached_master_fact_sheet += f"\n\n--- NEW FACTS (Incremental Update) ---\n{compressed_str}\n"
                        print(f"✅ Incremental Fact Sheet Augmented: appended {len(compressed_str)} chars. Total Registry: {len(registry)} sources.")
                    except Exception as e:
                        print(f"⚠️ Fact Sheet Augmentation Failed: {e}")
                else:
                    cached_master_fact_sheet += f"\n\n--- NEW FINDINGS ---\n{new_source_content}\n"
                    print("⚡ Minor new content appended raw to Fact Sheet.")
                    
        except Exception as e:
            print(f"⚠️ Registry Building Failed: {e}.")
            
        print(f"🚀 Registry ready ({len(registry)} sources) and continuously growing!")

        # 2. CHAPTER-LEVEL WRITING (v5.4)
        # Instead of writing ALL chapters at once, write ONE chapter per call.
        # Supervisor reviews each chapter individually before moving to the next.
        
        current_chapter_idx = state.get('current_chapter_index', 0)
        approved_chapters = state.get('approved_chapters', []) or []
        
        # If all chapters are already approved, signal completion (assembly is done by Supervisor)
        if current_chapter_idx >= len(chapters):
            print(f"✅ All {len(chapters)} chapters already approved. Signaling Supervisor for assembly.")
            return {
                "sender": "Researcher",
                "iteration_count": iteration,
                "current_chapter_index": current_chapter_idx,
                "approved_chapters": approved_chapters,
                "chapter_plan": chapters,
                "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                "cached_master_fact_sheet": cached_master_fact_sheet,
                "verified_reference_registry": registry,
                "messages": [SystemMessage(content=f"APPROVED: All {len(chapters)} chapters are already approved. Please assemble and advance.")]
            }
        
        # --- Write ONLY the current chapter ---
        chap = chapters[current_chapter_idx]
        title = chap.get('title', f"Chapter {current_chapter_idx+1}")
        files = chap.get('files', [])
        
        print(f"📝 Writing Chapter {current_chapter_idx+1}/{len(chapters)}: {title}")
        
        # Build context from previously approved chapters (read-only reference)
        approved_context = ""
        if approved_chapters:
            for idx, ac in enumerate(approved_chapters):
                snippet = ac[-800:] if len(ac) > 800 else ac
                approved_context += f"\n---\n**[APPROVED Chapter {idx+1}] (Read-Only Reference, do NOT repeat):**\n{snippet}\n"
            print(f"   📖 {len(approved_chapters)} approved chapter(s) provided as context.")
        
        # --- Chapter Data Gathering ---
        raw_chapter_context = ""
        
        if files:
            for file_path in files:
                try:
                    if file_path.lower().endswith('.pdf'):
                        try:
                            import pdfminer.high_level
                            # Using the first research dir as a base, ideally should check all dirs
                            base_dir = research_dirs[0] if research_dirs else ""
                            with open(os.path.join(base_dir, file_path), "rb") as pdf_file:
                                content = pdfminer.high_level.extract_text(pdf_file)
                            content = content[:50000]
                            print(f"📄 Robust PDF Read (pdfminer): {file_path}")
                        except:
                            content = f"[PDF: {file_path} - extraction failed]"
                    else:
                        base_dir = research_dirs[0] if research_dirs else ""
                        full_path = os.path.join(base_dir, file_path)
                        if os.path.exists(full_path):
                            with open(full_path, "r", errors='ignore') as f:
                                content = f.read()[:50000]
                        else:
                            content = f"[File not found: {file_path}]"
                    raw_chapter_context += f"\n\n--- SOURCE: {file_path} ---\n{content}\n"
                except Exception as e:
                    raw_chapter_context += f"\n\n--- SOURCE: {file_path} ---\n[Error reading: {e}]\n"
        
        # Build chapter-specific context
        chapter_context = ""
        
        if cached_master_fact_sheet:
            safe_raw_context = raw_chapter_context[:25000]
            if len(raw_chapter_context) > 25000:
                safe_raw_context += "\n\n... [Remaining Raw Text Truncated] ..."
            
            chapter_context = f"""
**GLOBAL MASTER FACT SHEET (Pre-Digested by Gemini Flash):**
{cached_master_fact_sheet}

**RAW SOURCE DATA (For this chapter's referenced files):**
{safe_raw_context}
"""
            print(f"   ♻️ Using Hybrid Context (Fact Sheet + {len(safe_raw_context)} chars of Raw Data).")
        else:
            chapter_context = raw_chapter_context[:30000]
        
        # v12.0: Inject Web Search Library data (available regardless of local files)
        if local_web_context and "WEB SEARCH LIBRARY" not in chapter_context:
            safe_web = local_web_context[:15000] if len(local_web_context) > 15000 else local_web_context
            chapter_context += f"\n\n**🌐 PREVIOUSLY FOUND WEB RESEARCH (From Web Search Library DB):**\n{safe_web}\n"
            print(f"   🌐 Web Search Library context injected ({len(safe_web)} chars).")
        
        # Add global instructions
        chapter_context += f"\n\n**Global Context / Instructions:**\n{context_prompt}\n"
        
        # Add approved chapters as read-only reference
        if approved_context:
            chapter_context += f"\n\n**PREVIOUSLY APPROVED CHAPTERS (Do NOT repeat any content from these):**\n{approved_context}\n"
        
        # --- Gemini 1.5 Flash Primary Drafting (v5.5) ---
        # Gemini Flash's huge context window allows us to skip chunking entirely.
        # We pass up to 300k chars of raw data + fact sheets in one shot.
        
        # v13.0: Build VERIFIED REFERENCE REGISTRY instruction for Writer
        registry_instruction = ""
        if registry:
            registry_instruction = "\n**📋 VERIFIED REFERENCE REGISTRY (You may ONLY cite from this list using [REF-XXX] format):**\n"
            for ref in registry:
                type_label = ref['type'].upper()
                extra = ""
                if ref['type'] == 'web':
                    extra = f" — {ref.get('url', '')}"
                elif ref['type'] == 'patent':
                    extra = f" — {ref.get('patent_id', '')}"
                elif ref['type'] == 'paper':
                    extra = f" — Score: {ref.get('score', 'N/A')}"
                registry_instruction += f"  [{ref['ref_id']}] {type_label}: {ref['title']}{extra}\n"
            registry_instruction += "\n**🚫 ABSOLUTE RULE: You MUST cite using ONLY [REF-XXX] format from the list above.**\n"
            registry_instruction += "**ANY citation NOT using a [REF-XXX] ID from this list (e.g., [Web: ...], [Paper: ...], [Patent: ...], [File: ...]) will be AUTOMATICALLY DELETED.**\n"
        
        print(f"⚡ Gemini 1.5 Flash leading Chapter {current_chapter_idx+1}: {title} (Registry: {len(registry)} refs)")
        
        # Increase context limits for Gemini (it can handle it)
        gemini_raw_context = raw_chapter_context[:100000] 
        
        # Get previous draft to enable targeted editing
        previous_report = state.get('shared_knowledge', '')
        
        # If there's a critique, we are in revision mode
        revision_context = ""
        if critique:
            revision_context = f"""
**=== REVISION MODE ACTIVE ===**
**SUPERVISOR CRITIQUE TO ADDRESS:**
{critique}

**YOUR PREVIOUS DRAFT (Preserve this as much as possible):**
{previous_report[:50000]}

**TARGETED EDIT INSTRUCTION:**
You MUST NOT rewrite the entire draft from scratch. Keep your previous structure, depth, and [REF-XXX] citations. ONLY modify the specific sentences, formulas, or formatting rules flagged in the Supervisor Critique.
==============================
"""
        
        full_draft_prompt = f"""
**TASK: CHAPTER WRITER (FOCUSED SCOPE)**
**CHAPTER {current_chapter_idx+1} of {len(chapters)}: {title}**

**⚠️ SCOPE BOUNDARY (CRITICAL):**
This is a chapter within a sub-plan, NOT a standalone report.
Your scope is ONLY the topic described in this chapter's title. Do NOT cover material belonging to other chapters.
Adjust your depth and length based on the topic's importance — be thorough where it matters, concise where it doesn't.
Be focused and dense. Avoid padding or unnecessary repetition.

**SOURCES OF TRUTH (tagged with [REF-XXX] IDs):**
1. **SCIENTIFIC NOTES (DEEPSEEK-R1)**: 
{state.get('web_knowledge', '')}

2. **REGISTRY-AWARE FACT SHEET (Facts are tagged with [REF-XXX] source IDs)**:
{cached_master_fact_sheet}

3. **RAW DOCUMENTATION SNIPPETS**:
{gemini_raw_context}

{revision_context}

{registry_instruction}

**WRITING CONSTRAINTS:**
- **CRITIQUE COMPLIANCE (PRIORITY 1)**: If a critique is provided above, you MUST address every point. If it says remove math, remove ALL math. If it says add citations, add them. 
- **PRESERVE GOOD CONTENT**: If this is a revision, do NOT destroy the depth of your previous draft. Edit surgically.
- **AUDIENCE ADAPTATION**: Match your writing style to what the Supervisor and task require. Do NOT default to engineering-heavy writing if the task is UX/business focused.
- **NO HALLUCINATIONS**: Do not invent sensors, statistics, or data not found in the source documentation.
- **DENSE AND ACTIONABLE**: Keep content focused and substantive. Avoid filler prose.
- **APPROVED CONTEXT**: Ensure continuity with previously approved chapters without repeating them.
- **🚫🚫🚫 NO INTERNAL CITE TAGS (ZERO TOLERANCE) 🚫🚫🚫**: NEVER include `[Pre-Digested Facts]`, `[Scientific Notes]`, or `[GEMMA4]`, `[DEEPSEEK-R1]` in your output. Use [REF-XXX] tags from the registry.
- **🚫🚫🚫 NO FREE-FORM CITATIONS (ZERO TOLERANCE) 🚫🚫🚫**: NEVER write `[File: ...]`, `[Web: ...]`, `[Paper: ...]`, or `[Patent: ...]`. ALL of these formats are BANNED. Use ONLY `[REF-XXX]` IDs from the VERIFIED REFERENCE REGISTRY above. Any free-form citation will be AUTOMATICALLY STRIPPED.

**⚠️ MANDATORY CITATION RULES (YOUR SUBMISSION WILL BE REJECTED WITHOUT THESE):**
1. **INLINE CITATIONS**: Every factual claim, data point, metric, or formula MUST have an inline citation using `[REF-XXX]` format.
   Example: "The ProDMP achieves 4659x speedup via closed-form basis functions [REF-003]."
   Example: "The system uses ROS2 DDS for middleware [REF-001] [REF-012]."
2. **REFERENCES SECTION**: At the very end of your chapter, you MUST include:
   ```
   ## References
   [REF-001] FILE: document_name.pdf — Description of content used
   [REF-003] PAPER: Paper Title — Key finding cited
   [REF-012] WEB: Web Page Title — Relevant data used
   ```
   List ONLY the [REF-XXX] entries you actually cited in the text.
   If you omit inline citations or the References section, your work WILL BE REJECTED.

**ACTION:**
Write the full technical specification for "{title}" based on the sources above.
"""
        final_text = ""
        try:
            # --- v10.5 EMPTY RESPONSE GUARD: Retry up to 3 times if Gemini returns empty ---
            max_draft_retries = 3
            for draft_attempt in range(max_draft_retries):
                try:
                    res = llm_flash.invoke([
                        SystemMessage(content=active_prompt),
                        HumanMessage(content=full_draft_prompt)
                    ])
                    final_text = res.content
                    if isinstance(final_text, list):
                        final_text = " ".join([c.get('text', str(c)) if isinstance(c, dict) else str(c) for c in final_text])
                    else:
                        final_text = str(final_text)
                    
                    # Guard: Check if response is substantive (>200 chars of actual content)
                    stripped_text = final_text.strip()
                    if len(stripped_text) > 200:
                        print(f"✅ Gemini Draft Complete (attempt {draft_attempt+1}). Length: {len(final_text)} chars.")
                        break  # Good response, exit retry loop
                    else:
                        print(f"⚠️ Gemini returned near-empty response (attempt {draft_attempt+1}/{max_draft_retries}): {len(stripped_text)} chars. {'Retrying...' if draft_attempt < max_draft_retries-1 else 'Falling back to Qwen3.'}")
                        if draft_attempt < max_draft_retries - 1:
                            import time as _retry_time
                            _retry_time.sleep(3)  # Brief delay before retry
                            final_text = ""  # Reset for retry
                except Exception as inner_e:
                    print(f"⚠️ Gemini attempt {draft_attempt+1} failed: {inner_e}")
                    if draft_attempt < max_draft_retries - 1:
                        import time as _retry_time
                        _retry_time.sleep(3)
                    final_text = ""
            
            # Emergency: If Gemini still produced empty after all retries, PAUSE system and alert user
            if len(final_text.strip()) <= 200:
                pause_msg = f"🚨 SYSTEM PAUSED: Gemini Flash returned empty response {max_draft_retries} consecutive times. Possible API issue (rate limit, quota, or network). Please check API status and restart the system."
                print(f"\n{'='*80}")
                print(pause_msg)
                print(f"{'='*80}\n")
                save_dialogue_message(thread_id, "🚨 SYSTEM ALERT", pause_msg)
                log_night_audit("Researcher", f"PAUSED: Gemini empty response x{max_draft_retries}. Chapter: {title}")
                # Raise to halt the graph execution — user must restart
                raise Exception(pause_msg)
            
            save_dialogue_message(thread_id, "Gemini Flash (Writer)", f"✍️ Chapter draft complete ({len(final_text)} chars). Sending for review.")
            chapter_output = final_text
            import re
            # Aggressively strip any citation brackets containing internal tags
            chapter_output = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|GEMMA4|DEEPSEEK-R1)[^\]]*\]', '', chapter_output, flags=re.IGNORECASE)
            
        except Exception as e:
            print(f"❌ Gemini Drafting Failed: {e}. Falling back to Qwen emergency mode.")
            chapter_output = f"[Gemini drafting failed: {e}]"
        
        # --- Post-processing sanitization ---
        import re
        final_text = final_text.replace('🚨 DEEP_RESEARCH_REQUIRED', '')
        final_text = final_text.replace('🚨 DEEP_RESEARCH_NEEDED', '')
        final_text = re.sub(r'#+ Chapter \d+ \(Part \d+/\d+\)[:\s]*.*\n?', '', final_text)
        final_text = re.sub(r'\(Continued\)', '', final_text)
        final_text = re.sub(r'\(continued\)', '', final_text)
        
        # Build the chapter output with header
        chapter_output = f"## {title}\n\n{final_text}"
        
        # --- Flash Refinement on single chapter (much more effective!) ---
        try:
            print(f"✨ Flash Refinement for Chapter {current_chapter_idx+1} ({len(chapter_output)} chars)...")
            
            critique_context = ""
            if critique:
                critique_context = f"\n\n**SUPERVISOR CRITIQUE (Must address ALL points):**\n{critique}\n"
            
            # v6.5: In revision mode, Flash Refinement should preserve targeted edits
            preservation_rule = ""
            if critique:
                preservation_rule = """
**⚠️ REVISION MODE — PRESERVATION PRIORITY:**
This draft is a TARGETED REVISION of a previously rejected chapter. The writer has carefully edited specific sections to address the Supervisor's feedback while preserving the rest.
- DO NOT aggressively delete or shorten content that was intentionally preserved.
- ONLY remove content that is clearly hallucinated, off-topic, or contains internal tags.
- Your primary job in revision mode is POLISH, not PURGE.
"""
            
            refinement_prompt = f"""
**TASK: Restructure and polish this single chapter of a research report.**

**SOURCES OF TRUTH (Reference these for hallucination checking):**
{state.get('web_knowledge', '')}
{cached_master_fact_sheet}
{gemini_raw_context}

**YOUR GOAL IS TO PURGE HALLUCINATIONS. If a sentence is not backed by the 'SOURCES OF TRUTH' above, DELETE IT.**
{critique_context}
{preservation_rule}

**CRITICAL RULES:**
1. **SUPERVISOR CRITIQUE IS LAW**: If the Supervisor's critique above says to remove math, remove ALL formulas. If it says to change tone, change it. The critique overrides ALL rules below.
2. **PURGE HALLUCINATIONS**: If a specific statistic, percentage, sensor name, or technology claim is NOT found in the provided Scientific Notes, Source Data, or Pre-Digested Facts, DELETE IT. Do not invent data.
3. **🚫🚫🚫 PURGE ALL HALLUCINATED PATENTS (MANDATORY)**: Scan the ENTIRE draft for `[Patent: ...]` citations. For EACH one, search the Scientific Notes, Source Data, and Pre-Digested Facts for that exact patent number. If the patent number does NOT appear verbatim in any source provided to you, you MUST: (a) DELETE the `[Patent: ...]` citation, (b) DELETE or rephrase the specific claim it was supposed to support. This is NON-NEGOTIABLE. When in doubt, DELETE the patent citation.
3b. **🚫🚫🚫 PURGE ALL HALLUCINATED PAPERS (MANDATORY)**: Scan the ENTIRE draft for `[Paper: ...]` citations. For EACH one, check if that exact paper title appears in the Academic Papers section or Source Data. If the paper title does NOT appear in any source provided to you, you MUST: (a) DELETE the `[Paper: ...]` citation, (b) Keep the factual claim if it is supported by other sources, otherwise DELETE it. When in doubt, DELETE the paper citation.
4. **PRESERVE INLINE CITATIONS (EXCEPT PATENTS AND PAPERS)**: The draft contains inline citations like `[File: ...]`, `[Web: ...]`, `[Patent✓: ...]`, `[Paper✓: ...]`. YOU MUST PRESERVE THESE EXACTLY AS WRITTEN. Do not delete them while polishing. Do not alter their formatting. NOTE: Unverified `[Patent: ...]` and `[Paper: ...]` citations are NOT protected by this rule — they are governed by Rules 3 and 3b above.
5. **FORMULAS**: If the Supervisor's critique does NOT mention removing formulas, keep them with clear dimensions. If the critique DOES say to remove formulas, DELETE THEM and replace with plain-English descriptions.
6. **PURGE ACADEMIC FLUFF**: Delete introductory filler, repetitive transitions, and "word salad".
7. **SCOPE CHECK**: This chapter is "{title}". Remove ANY content not directly about this topic.
8. **NO INTERNAL TAGS**: Remove any `[Scientific Notes]`, `[GEMMA4]`, `[DEEPSEEK-R1]`, or other internal markers.

**CHAPTER TO REFINE:**
{chapter_output}

**OUTPUT**: The complete restructured chapter in Markdown format. Start directly with the content.
"""
            
            refined_response = llm_flash.invoke([
                SystemMessage(content="You are a Senior Editor. You follow the Supervisor's critique above all else. Adapt your editing style to match the document's target audience."),
                HumanMessage(content=refinement_prompt)
            ])
            
            refined_content = refined_response.content
            if isinstance(refined_content, list):
                parts = []
                for c in refined_content:
                    if isinstance(c, dict) and 'text' in c:
                        parts.append(c['text'])
                    elif hasattr(c, 'text'):
                        parts.append(c.text)
                    else:
                        parts.append(str(c))
                refined_content = " ".join(parts)
            else:
                refined_content = str(refined_content)
            
            # v5.4.1: RELIGIOUSLY ACCEPT FLASH OUTPUT (NO MINIMUM LENGTH)
            # Since Qwen3 hallucinates a lot, we TRUST Flash's deletions.
            if len(refined_content) > 200:
                print(f"✅ Flash Refinement Complete (Purged Hallucinations)! {len(chapter_output)} → {len(refined_content)} chars.")
                chapter_output = refined_content
                
                # Force strip internal tags again just to be perfectly safe
                import re
                chapter_output = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|GEMMA4|DEEPSEEK-R1)[^\]]*\]', '', chapter_output, flags=re.IGNORECASE)
                
                # v10.5: Strip leaked Chain-of-Thought / <think> blocks
                # First: always strip explicit <think>...</think> tags
                chapter_output = re.sub(r'<think>.*?</think>', '', chapter_output, flags=re.DOTALL)
                
                # Second: check if output starts with expected chapter number
                # e.g. step2, substep1, chapter3 → expected prefix "2.1.3"
                expected_prefix = f"{current_step_idx + 1}.{current_sub_idx + 1}.{current_chapter_idx + 1}"
                starts_with_expected = chapter_output.lstrip().startswith(f"# {expected_prefix}") or \
                                       chapter_output.lstrip().startswith(f"## {expected_prefix}") or \
                                       chapter_output.lstrip().startswith(f"### {expected_prefix}")
                
                if not starts_with_expected:
                    # Output doesn't start with expected chapter number → check for reasoning preamble
                    # Find the first heading that contains our expected chapter number
                    expected_heading = re.search(rf'^#{1,6}\s+{re.escape(expected_prefix)}', chapter_output, re.MULTILINE)
                    if expected_heading and expected_heading.start() > 0:
                        preamble_len = expected_heading.start()
                        print(f"🧹 Output didn't start with '{expected_prefix}'. Stripped {preamble_len} chars of preamble before chapter heading.")
                        chapter_output = chapter_output[expected_heading.start():]
                    elif not expected_heading:
                        # No expected heading found at all — try fallback: strip before first any '#' heading
                        first_heading = re.search(r'^#{1,6}\s', chapter_output, re.MULTILINE)
                        if first_heading and first_heading.start() > 200:
                            # Only strip if there's a substantial preamble (>200 chars)
                            print(f"🧹 No '{expected_prefix}' heading found. Stripped {first_heading.start()} chars of preamble before first heading.")
                            chapter_output = chapter_output[first_heading.start():]
            else:
                print(f"⚠️ Flash Refinement failed or produced empty. Keeping Qwen3 draft (Caution).")
                
        except Exception as e:
            print(f"⚠️ Flash Refinement Failed: {e}. Keeping Qwen3 draft.")
        
        # ===== v13.0: REGISTRY-BASED CITATION GUARD (100% ENFORCEMENT) =====
        # Replaces the previous 4 separate guards (Patent/Paper/File/URL).
        # Only [REF-XXX] citations from the Verified Reference Registry are allowed.
        import re
        # Use the locally updated registry which contains the new REF-XXX documents
        registry = registry if 'registry' in locals() else state.get('verified_reference_registry', [])
        valid_ref_ids = {r['ref_id'] for r in registry}
        
        # --- Guard 1: Validate [REF-XXX] citations ---
        ref_citations = re.findall(r'\[(REF-\d{3})\]', chapter_output)
        ref_valid = 0
        ref_invalid = 0
        for ref_id in set(ref_citations):
            if ref_id not in valid_ref_ids:
                chapter_output = chapter_output.replace(f'[{ref_id}]', '')
                ref_invalid += 1
                print(f"   🛡️ Registry Guard: Stripped invalid [{ref_id}] (not in registry)")
            else:
                ref_valid += 1
        
        if ref_valid > 0 or ref_invalid > 0:
            print(f"🛡️ Registry Guard (REF-XXX): {ref_valid} valid, {ref_invalid} stripped")
        
        # --- Guard 2: Strip ALL legacy free-form citations ---
        # The Writer was instructed to use only [REF-XXX], but LLMs may still produce old formats
        legacy_types = ['File', 'Web', 'Paper', 'Patent', 'File✓', 'Web✓', 'Paper✓', 'Patent✓']
        total_legacy_stripped = 0
        for lt in legacy_types:
            legacy_pattern = rf'\[{lt}:\s*[^\]]*\]'
            legacy_found = re.findall(legacy_pattern, chapter_output)
            if legacy_found:
                for lf in legacy_found:
                    chapter_output = chapter_output.replace(lf, '')
                    total_legacy_stripped += 1
        
        if total_legacy_stripped > 0:
            print(f"🛡️ Registry Guard (Legacy Strip): Removed {total_legacy_stripped} free-form citation(s) ([File:...], [Web:...], etc.)")
        
        # --- Guard 3: Strip hallucinated markdown URLs not in registry ---
        urls_in_md = re.findall(r'(\[.*?\])\((https?://[^\s\)]+)\)', chapter_output)
        if urls_in_md:
            # Build whitelist from registry web entries
            registry_urls = set()
            for r in registry:
                if r.get('url'):
                    registry_urls.add(r['url'].strip().lower().rstrip('/#?'))
            
            url_stripped = 0
            for text_part, url_part in set(urls_in_md):
                url_clean = url_part.strip().lower().rstrip('/#?')
                if 'example.com' in url_clean:
                    continue
                is_valid = any(
                    url_clean.startswith(wu) or wu.startswith(url_clean)
                    for wu in registry_urls
                )
                if not is_valid:
                    chapter_output = chapter_output.replace(f"{text_part}({url_part})", f"{text_part}(Link_Unverified)")
                    url_stripped += 1
            
            if url_stripped > 0:
                print(f"🛡️ Registry Guard (URL): Replaced {url_stripped} unverified link(s)")
        
        # --- Guard 4: Rebuild References section from registry ---
        # Remove any LLM-generated References section and replace with registry-based one
        chapter_output = re.sub(r'\n##\s*References?\n.*', '', chapter_output, flags=re.DOTALL)
        
        # Extract all REF-XXX occurrences, even if comma-separated like [REF-001, REF-016]
        cited_ref_ids = sorted(set(re.findall(r'(REF-\d{3})', chapter_output)))
        if cited_ref_ids:
            ref_section = "\n\n## References\n\n"
            for ref_id in cited_ref_ids:
                ref = next((r for r in registry if r['ref_id'] == ref_id), None)
                if ref:
                    if ref['type'] == 'web':
                        ref_section += f"- [{ref_id}] Web: [{ref['title']}]({ref.get('url', '#')})\n"
                    elif ref['type'] == 'paper':
                        ref_section += f"- [{ref_id}] Paper: {ref['title']}\n"
                    elif ref['type'] == 'patent':
                        ref_section += f"- [{ref_id}] Patent: {ref.get('patent_id', '')} — {ref['title']}\n"
                    elif ref['type'] == 'file':
                        ref_section += f"- [{ref_id}] File: {ref['title']}\n"
            chapter_output += ref_section
            print(f"📋 Registry Guard: Rebuilt References section with {len(cited_ref_ids)} verified entries")
        
        # ===== END v13.0 REGISTRY GUARD =====
        
        # ===== LEGACY GUARDS (v9.2~v10.9) — PRESERVED FOR RECOVERY =====
        # To restore: uncomment the block below and comment out the Registry Guard above.
        # --- START LEGACY GUARD BLOCK ---
        # # v9.2: PER-CITATION PATENT HALLUCINATION GUARD
        # patent_citations = re.findall(r'\[Patent:\s*([^\]]*)\]', chapter_output)
        # if patent_citations:
        #     all_source_text = str(context_prompt) + str(scientific_notes)
        #     if local_patent_context: all_source_text += str(local_patent_context)
        #     for raw_patent_ref in patent_citations:
        #         patent_id = raw_patent_ref.strip().split('-')[0].split(' ')[0].strip()
        #         patent_id_clean = re.sub(r'[\s\-]', '', patent_id)
        #         found = patent_id in all_source_text or patent_id_clean in all_source_text
        #         if not found: chapter_output = chapter_output.replace(f'[Patent: {raw_patent_ref}]', '')
        #         else: chapter_output = chapter_output.replace(f'[Patent: {raw_patent_ref}]', f'[Patent✓: {raw_patent_ref}]')
        #
        # # v10.2: PER-CITATION PAPER HALLUCINATION GUARD
        # paper_citations = re.findall(r'\[Paper:\s*([^\]]*)\]', chapter_output)
        # if paper_citations:
        #     from app.core.rag import PaperLibrary
        #     paper_lib = PaperLibrary(project_id=project_id)
        #     paper_stats = paper_lib.get_stats()
        #     real_papers = [p.lower().replace('.pdf','').replace('_',' ') for p in paper_stats.get('papers',[])]
        #     for raw_paper_ref in paper_citations:
        #         ref_lower = raw_paper_ref.strip().lower().replace('_',' ')
        #         found = any(ref_lower in rp or rp in ref_lower or len(set(ref_lower.split())&set(rp.split()))>=3 for rp in real_papers)
        #         if not found: chapter_output = chapter_output.replace(f'[Paper: {raw_paper_ref}]', '')
        #         else: chapter_output = chapter_output.replace(f'[Paper: {raw_paper_ref}]', f'[Paper✓: {raw_paper_ref}]')
        #
        # # v10.6: PER-CITATION FILE HALLUCINATION GUARD
        # file_citations = re.findall(r'\[File:\s*([^\]]*)\]', chapter_output)
        # if file_citations:
        #     from app.core.rag import DocumentLibrary
        #     doc_lib = DocumentLibrary(project_id=project_id)
        #     doc_stats = doc_lib.get_stats()
        #     real_files = [f.lower().replace('.pdf','').replace('.txt','').replace('.md','').replace('_',' ') for f in doc_stats.get('documents',[])]
        #     for raw_file_ref in file_citations:
        #         ref_lower = raw_file_ref.strip().lower().replace('_',' ').replace('.pdf','').replace('.txt','').replace('.md','')
        #         found = any(ref_lower in rf or rf in ref_lower for rf in real_files)
        #         if not found: chapter_output = chapter_output.replace(f'[File: {raw_file_ref}]', '')
        #         else: chapter_output = chapter_output.replace(f'[File: {raw_file_ref}]', f'[File✓: {raw_file_ref}]')
        #
        # # v10.9: Web Research Whitelist URL Guard
        # urls_in_md = re.findall(r'(\[.*?\])\((https?://[^\s\)]+)\)', chapter_output)
        # if urls_in_md:
        #     _WEB_RESEARCH_DIR = os.path.join(_BASE_DIR, "data", "projects", project_id, "web_research")
        #     verified_urls = set()
        #     if os.path.isdir(_WEB_RESEARCH_DIR):
        #         for txt_file in glob.glob(os.path.join(_WEB_RESEARCH_DIR, "**", "*.txt"), recursive=True):
        #             with open(txt_file, 'r') as _f:
        #                 first_line = _f.readline().strip()
        #                 if first_line.startswith("SOURCE:"):
        #                     verified_urls.add(first_line.replace("SOURCE:","").strip().lower().rstrip('/#?'))
        #     for text_part, url_part in set(urls_in_md):
        #         url_clean = url_part.strip().lower().rstrip('/#?')
        #         if not any(url_clean.startswith(wu) or wu.startswith(url_clean) for wu in verified_urls):
        #             chapter_output = chapter_output.replace(f"{text_part}({url_part})", f"{text_part}(Link_Unverified)")
        # --- END LEGACY GUARD BLOCK ---
        
        # 3. SAVE & RETURN (single chapter)
        from app.utils import save_artifact
        filename = f"Step{current_step_idx+1}_Sub{current_sub_idx+1}_Ch{current_chapter_idx+1}_v{iteration+1}"
        save_artifact(filename, chapter_output, "md", thread_id=thread_id)
        
        end_time = time.time()
        elapsed = end_time - start_time
        duration_str = f"{elapsed:.1f}s"
        if elapsed > 60:
            duration_str = f"{elapsed/60:.1f}min"

        return {
            "sender": "Researcher",
            "web_knowledge": chapter_output,
            "shared_knowledge": f"Deep Report:\n{chapter_output}", 
            "iteration_count": iteration,
            "current_chapter_index": current_chapter_idx,
            "approved_chapters": approved_chapters,
            "chapter_plan": chapters,
            "sub_plan": state.get("sub_plan", []),
            "cached_master_fact_sheet": cached_master_fact_sheet,
            "verified_reference_registry": registry,  # v13.0: Persist registry across chapters
            "messages": [SystemMessage(content=f"📝 Chapter {current_chapter_idx+1}/{len(chapters)} '{title}' written. (Duration: {duration_str})\nPlease review THIS CHAPTER ONLY.")]
        }
    except Exception as outer_e:
        log_night_audit("Researcher", f"CRITICAL CRASH: {outer_e}")
        # Return state with error so Supervisor can try to recover or stop
        return {
            "sender": "Researcher",
            "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan even on crash
            "messages": [SystemMessage(content=f"🚨 CRITICAL ERROR in Researcher: {outer_e}")],
            "error": str(outer_e)
        }
