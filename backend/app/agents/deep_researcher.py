import os
import json
import hashlib
import time
import random
import requests
from bs4 import BeautifulSoup
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import save_artifact, log_night_audit
from langchain_tavily import TavilySearch
from app.agents.local_model import local_llm
from app.core.rag import PatentLibrary, WebSearchLibrary, MediaLibrary

# SPECIALIZED DEEP RESEARCH ENGINE (Using Llama 4 Scout for Quality)
# Web Search: Tavily | Report Writing: Llama 4 Scout (Local)
llm_deep = local_llm

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _get_cache_dir(project_id: str) -> str:
    path = os.path.join(_BASE_DIR, "data", "projects", project_id, "search_cache")
    os.makedirs(path, exist_ok=True)
    return path

def _get_web_content_dir(project_id: str) -> str:
    path = os.path.join(_BASE_DIR, "data", "projects", project_id, "web_fulltext")
    os.makedirs(path, exist_ok=True)
    return path

def _cache_key(query: str) -> str:
    """Generate a stable hash from a search query."""
    normalized = query.strip().lower()[:200]
    return hashlib.md5(normalized.encode()).hexdigest()

def _get_cached_results(query: str, project_id: str):
    """Returns cached search results if available and fresh (<24h)."""
    import time
    key = _cache_key(query)
    cache_path = os.path.join(_get_cache_dir(project_id), f"{key}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Check freshness (24 hour TTL)
            if time.time() - data.get("timestamp", 0) < 86400:
                print(f"   💾 Cache HIT for query: {query[:60]}...")
                return data.get("results", [])
        except Exception:
            pass
    return None

def _save_cache(query: str, results, project_id: str):
    """Saves search results to cache."""
    key = _cache_key(query)
    cache_path = os.path.join(_get_cache_dir(project_id), f"{key}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"query": query[:200], "timestamp": time.time(), "results": results}, f, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠️ Cache save failed: {e}")


# v7.0: Web Page Full-Text Scraping
def _fetch_page_fulltext(url: str, project_id: str, max_chars: int = 50000) -> str:
    """Fetches and extracts clean text from a web URL.
    Returns the full text content or empty string on failure.
    Caches results to avoid re-fetching.
    """
    # Cache check
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_path = os.path.join(_get_web_content_dir(project_id), f"{url_hash}.txt")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = f.read()
            if len(cached) > 100:
                return cached
        except Exception:
            pass

    # Skip non-HTML URLs
    skip_exts = ['.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3', '.jpg', '.png', '.gif']
    if any(url.lower().endswith(ext) for ext in skip_exts):
        return ""

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    try:
        time.sleep(0.5 + random.uniform(0.3, 1.0))  # Polite delay
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        
        # Check content type
        ct = resp.headers.get('content-type', '')
        if 'text/html' not in ct and 'text/plain' not in ct:
            return ""

        soup = BeautifulSoup(resp.text, 'lxml')

        # Remove noise elements
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # Try to find main content area
        main_content = (
            soup.find('article') or
            soup.find('main') or
            soup.find('div', class_='content') or
            soup.find('div', class_='post-content') or
            soup.find('div', id='content') or
            soup.body
        )

        if not main_content:
            return ""

        text = main_content.get_text(separator='\n', strip=True)
        
        # Clean up: collapse multiple newlines
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text[:max_chars]

        # Save to cache
        if len(text) > 100:
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {url}\n\n{text}")
            except Exception:
                pass

        return text

    except requests.exceptions.Timeout:
        return ""
    except Exception:
        return ""


def _enrich_web_results(results: list, project_id: str, max_fetch: int = 5) -> list:
    """Enriches Tavily search results with full page content.
    Only fetches top `max_fetch` results to avoid rate limiting.
    """
    if not results:
        return results

    enriched_count = 0
    for res in results[:max_fetch]:
        if not isinstance(res, dict):
            continue
        url = res.get('url', '')
        if not url:
            continue

        fulltext = _fetch_page_fulltext(url, project_id)
        if fulltext and len(fulltext) > len(res.get('content', '')):
            res['content_original'] = res.get('content', '')  # Keep snippet
            res['content'] = fulltext  # Replace with full text
            res['has_fulltext'] = True
            enriched_count += 1
        else:
            res['has_fulltext'] = False

    if enriched_count > 0:
        print(f"   📄 Web Full-Text: Enriched {enriched_count}/{min(len(results), max_fetch)} pages.")
    return results

# Maximum tokens per chunk (Optimized for English)
# Maximum tokens per chunk (Optimized for Qwen3 32k Context)
MAX_CHUNK_TOKENS = 15000  # huge chunk size for deep analysis

SYSTEM_PROMPT = """
You are the **Specialized Deep Investigator**.
Your goal is to gather components, facts, and technical details for the Lead Researcher.

**ROLE:**
- You are NOT the final report writer.
- You are the **Intelligence Officer** who provides raw, verified data.
- **OUTPUT**: Structured "Research Notes" that the Writer can easily integrate.

**LANGUAGE RULE:**
- **ENGLISH**: Summaries and explanations in English.
- **SOURCE MATERIAL**: Focus on synthesizing local files and web findings into actionable data points.
- **CITATION RULES (STRICT)**: 
  - IF the info comes from a local file (PDF, TXT, MD), you MUST use: **[File: filename.ext]**.
  - IF the info comes from the "WEB FINDINGS" section, you MUST use: **[Web: specific_url_or_title]**.
  - **NEVER** label a local file as [Web]. Check the "LOCAL KNOWLEDGE BASE" section carefully.
"""

CHUNK_ANALYSIS_PROMPT = """
You are analyzing a **chunk of research data**. 

**YOUR TASK:**
1. Extract **Hard Facts**: Formulas, definitions, specific numbers, methods.
2. Ignore fluff or general introductions.
3. Identify "Key Enablers" for the topic.

**OUTPUT FORMAT:**
- **핵심 사실**: [fact]
- **수식/데이터**: [formula/data]
- **참조 파일/링크**: [source]
"""

SYNTHESIS_PROMPT = """
You are synthesizing multiple chunk analyses into a **Consolidated Research Note**.

**TASK:**
1. Aggregate all facts and data points.
2. Structure them logically (e.g., heavily bulleted).
3. **DO NOT** write a prose essay. Write detailed **NOTES**.
4. These notes will be passed to the Lead Writer to create the final report.

**STRUCTURE:**
- **1. 핵심 발견 (Key Findings)**: High-level summary of what was found.
- **2. 상세 데이터 (Technical Details)**: Formulas, algorithms, specific parameters.
- **3. 문맥 연결 (Context)**: How this relates to the Master Report terms.
- **4. 원본 출처 (Sources)**: List of key files or URLs used.

**CHUNK ANALYSES:**
{chunk_analyses}

**ORIGINAL TOPIC:**
{topic}

Write the Consolidated Research Note in ENGLISH:
"""

from langchain_core.runnables import RunnableConfig

def estimate_tokens(text: str) -> int:
    """
    Conservative token estimation for English text:
    - Base: 1 character ≈ 1 token (Very conservative safety buffer)
    """
    return len(text)

def chunk_text(text: str, max_tokens: int) -> list:
    """
    Split text into chunks of approximately max_tokens size.
    SPLIT STRATEGY: By newline '\n' to handle dense RAG data.
    """
    if not text:
        return []
    
    # Split by lines to handle dense text blocks (like 100 RAG results)
    lines = text.split('\n')
    chunks = []
    current_chunk_parts = []
    current_tokens = 0
    
    for line in lines:
        line_tokens = estimate_tokens(line)
        
        # Guard: If a single line is LARGER than max_tokens, force split it
        if line_tokens > max_tokens:
            if current_chunk_parts:
                chunks.append("\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_tokens = 0
            
            # Sub-split long line aggressively by character count
            for start in range(0, len(line), max_tokens):
                chunks.append(line[start:start+max_tokens])
            continue

        if current_tokens + line_tokens > max_tokens and current_chunk_parts:
            chunks.append("\n".join(current_chunk_parts))
            current_chunk_parts = [line]
            current_tokens = line_tokens
        else:
            current_chunk_parts.append(line)
            current_tokens += line_tokens + 1 # +1 for the newline
    
    if current_chunk_parts:
        chunks.append("\n".join(current_chunk_parts))
    
    return chunks

def deep_researcher_node(state: AgentState, config: RunnableConfig):
    """
    Dedicated node for comprehensive research.
    Performs Web, Academic, and Patent research based on user flags.
    Returns: A rich chunk of textual knowledge for the writer to use.
    """
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    topic = state.get('research_topic', '')
    project_id = state.get('project_id', 'default')
    
    # Extract Original Goal for context-aware search queries
    messages = state.get("messages", [])
    original_goal = str(messages[0].content) if messages else topic
    
    print(f"\n🧠 [DEEP RESEARCHER] Initializing... Generating optimized search keywords for: '{topic[:50]}...'")
    
    # v13.0: Domain-Aware Search Query Generation
    from app.utils import extract_text_content
    try:
        from app.agents.local_model import local_llm
        prompt = f"""You are a Search Query Specialist. Generate 1 to 3 distinct search queries for web search engines.

**TASK**: Read the research context and generate up to 3 distinct search queries. If the topic contains distinctly different theoretical concepts and brand names, split them into separate focused queries to avoid concept blending.

**RULES:**
1. OUTPUT MUST BE A VALID JSON ARRAY OF STRINGS: ["query 1", "query 2"]
2. Maximum 3 queries.
3. For brand-specific queries, ALWAYS preserve proper nouns (e.g., "Samsung Design Mauro Porcini").
4. For pure theoretical or methodological topics (e.g., "PESO model framework", "Media tiering definition"), output a SEPARATE query WITHOUT the brand name to ensure proper academic or methodological extraction.
5. Do NOT include markdown code blocks (```json), just the raw JSON array.

Original Research Goal: {original_goal[:1000]}
Current Sub-topic: {topic[:500]}

JSON Output:"""
        res = local_llm.invoke([HumanMessage(content=prompt)])
        raw_res = extract_text_content(res).strip()
        if '</think>' in raw_res:
            raw_res = raw_res.split('</think>')[-1].strip()
        raw_res = raw_res.replace('```json', '').replace('```', '').strip()
        
        import json
        try:
            queries_list = json.loads(raw_res)
            if not isinstance(queries_list, list):
                queries_list = [str(queries_list)]
        except json.JSONDecodeError:
            print(f"⚠️ JSON Decode Error for multi-query. Fallback to raw string.")
            queries_list = [raw_res[:200].replace('\n', ' ')]
            
        optimized_query = queries_list[0] if queries_list else topic[:200].split('\n')[0]
        all_web_queries = queries_list[:3]
    except Exception as e:
        print(f"⚠️ Keyword optimization failed: {e}")
        optimized_query = topic[:200].split('\n')[0]
        all_web_queries = [optimized_query]
        
    print(f"\n🔍 [DEEP RESEARCHER] Activating on Optimized Queries: {all_web_queries} (Topic: {topic[:50]}...)")
    
    try:
        # Extract Thread ID
        thread_id = config.get("configurable", {}).get("thread_id", None)
        project_id = state.get('project_id', 'default')
        
        topic = state.get('research_topic', 'Deep Investigation')
        mode = state.get('research_mode', 'deep')
        
        current_index = state.get('current_step_index', 0)
        current_sub_idx = state.get('current_sub_step_index', 0)
        iteration = state.get('iteration_count', 0)
        
        local_context = state.get('local_knowledge', '')
        # v3.9: Context Balancing - Truncate background knowledge to 3k chars.
        if local_context and len(local_context) > 3000:
            print(f"⚖️ Context Balancing: Truncated internal knowledge for Deep Researcher ({len(local_context)} -> 3000 chars).")
            local_context = local_context[:3000] + "\n... [Background Context Truncated for Token Efficiency] ..."
        
        # v5.2: Search LOCAL Paper Library (ChromaDB) for relevant papers
        local_paper_context = ""
        try:
            from app.core.rag import PaperLibrary, PatentLibrary, WebSearchLibrary, MediaLibrary
            paper_lib = PaperLibrary(project_id=project_id)
            patent_library = PatentLibrary(project_id=project_id)
            web_search_library = WebSearchLibrary(project_id=project_id)
            media_library = MediaLibrary(project_id=project_id)
            
            local_paper_context = paper_lib.search_papers(optimized_query, k=10)
            if local_paper_context:
                print(f"📚 Deep Investigator: Found local papers ({len(local_paper_context)} chars)")
                local_context += f"\n\n**LOCAL ACADEMIC PAPERS (From Curated Library):**\n{local_paper_context}"
            else:
                print("📚 Deep Investigator: No relevant local papers found.")
        except Exception as e:
            print(f"⚠️ Paper Library search in Deep Investigator failed: {e}")
        
        web_context = ""

        # Web Research Trigger — v8.0: ALWAYS perform external research when DEEP_RESEARCHER is invoked.
        # The Supervisor only routes here when external data is needed, so no further gating required.
        should_search = True  # Always search when this node is invoked
        
        search_options = state.get('search_options', {})
        use_academic = search_options.get('academic', False)
        use_patent = search_options.get('patent', False)
        use_web = search_options.get('web', True)
        use_media = search_options.get('media', False)
        
        # v13.0: Track all discovered sources for Reference Registry
        discovered_sources = []
        
        # v13.0+: Dynamic search count — assess if topic needs more web sources
        base_web_results = 12   # raised from 8
        base_academic_results = 4  # raised from 2
        try:
            from app.agents.local_model import local_llm as _assess_llm
            assess_prompt = f"""Assess the research topic below. How heavily does it rely on EXTERNAL web sources vs LOCAL project files?
Topic: {topic[:300]}
Respond with ONLY one word: LOW, MEDIUM, or HIGH"""
            assess_res = _assess_llm.invoke([HumanMessage(content=assess_prompt)])
            web_need = str(assess_res.content).strip().upper()
            if 'HIGH' in web_need:
                base_web_results = 20
                base_academic_results = 8
                print(f"📈 Dynamic Search: HIGH web dependency detected → {base_web_results} web results, {base_academic_results} academic per keyword")
            elif 'MEDIUM' in web_need:
                base_web_results = 16
                base_academic_results = 6
                print(f"📊 Dynamic Search: MEDIUM web dependency → {base_web_results} web results, {base_academic_results} academic per keyword")
            else:
                print(f"📉 Dynamic Search: LOW web dependency → {base_web_results} web results, {base_academic_results} academic per keyword")
        except Exception:
            print(f"⚠️ Dynamic search assessment failed, using defaults: {base_web_results} web results, {base_academic_results} academic")
        
        print(f"🔧 Search Options: web={use_web}, academic={use_academic}, patent={use_patent}, media={use_media}")
        
        if should_search:
            print(f"🌍 Performing Persistent Web Research on: {topic}")
            from app.utils.db_utils import log_web_research, init_vault
            
            # Initialize vault for this project
            init_vault(project_id)
            
            from app.utils.academic_researcher import AcademicResearcher
            
            # --- ACADEMIC RESEARCH (New Architecture) ---
            academic_context = ""
            if use_academic:
                try:
                    print("🎓 Activating Academic Research Protocol...")
                    academic = AcademicResearcher(project_id=project_id)
                    
                    # 1. Keyword Extraction (v13.0: domain-aware, with full context)
                    keywords = academic.extract_keywords(optimized_query, original_goal=original_goal)
                    print(f"   🔑 Extracted Keywords: {keywords}")
                    
                    # 2. Search ArXiv
                    paper_results = []
                    for kw_idx, kw in enumerate(keywords[:3]): # Search top 3 keywords
                        if kw_idx > 0:
                            # Inter-keyword delay to avoid rate limiting across APIs
                            import time as _time
                            _time.sleep(10)
                            print(f"   ⏳ Academic search: inter-keyword delay before keyword {kw_idx+1}...")
                        paper_results.extend(academic.search_arxiv(kw, max_results=base_academic_results))
                    
                    # Remove duplicates based on title
                    unique_papers = {p['title']: p for p in paper_results}.values()
                    paper_results = list(unique_papers)
                    
                    # 3. Download & Analyze
                    if paper_results:
                        print(f"   📄 Analyzing {len(paper_results)} papers...")
                        academic_context = academic.analyze_papers(
                            paper_results, 
                            topic=topic, 
                            original_goal=original_goal
                        )
                        
                        # v13.0: Track discovered papers for Reference Registry
                        for paper in paper_results:
                            pdf_path = paper.get('local_path', '')
                            discovered_sources.append({
                                "type": "paper",
                                "title": paper.get('title', 'Unknown Paper'),
                                "url": paper.get('url', ''),
                                "arxiv_id": paper.get('arxiv_id', ''),
                                "source_file": pdf_path,
                                "content": paper.get('abstract', '')[:1000],
                                "verified": bool(pdf_path and os.path.exists(pdf_path))
                            })
                        print(f"   📋 Tracked {len(paper_results)} papers for Reference Registry")
                        
                        if academic_context:
                            academic_context = f"\n\n**🎓 ACADEMIC PAPER ANALYSIS (ArXiv):**\n{academic_context}\n"
                    else:
                        print("   ⚠️ No academic papers found.")
                        
                except Exception as e:
                    print(f"⚠️ Academic Research Failed: {e}")
            else:
                print("🎓 Academic Research skipped by user preference.")

            # --- PATENT RESEARCH (v6.1 + v6.3 DB) ---
            patent_context = ""
            if use_patent:
                try:
                    from app.utils.patent_researcher import PatentResearcher
                    patent_researcher = PatentResearcher()
                    if patent_researcher.is_available():
                        print("🔬 Activating Patent Research Protocol...")
                        patent_text, patent_raw_results = patent_researcher.search_patents_raw(optimized_query)
                        if patent_text:
                            patent_context = f"\n\n**🔬 PATENT / PRIOR ART ANALYSIS:**\n{patent_text}\n"
                            print(f"   ✅ Patent context generated ({len(patent_context)} chars)")
                            # v6.3: Auto-index into Patent Library DB
                            if patent_raw_results:
                                patent_library.index_patents(patent_raw_results)
                                # v13.0: Track discovered patents for Reference Registry
                                for pat in patent_raw_results:
                                    discovered_sources.append({
                                        "type": "patent",
                                        "title": pat.get('title', 'Unknown Patent'),
                                        "patent_id": pat.get('patent_id', pat.get('publication_number', '')),
                                        "url": pat.get('url', ''),
                                        "source_file": '',
                                        "content": pat.get('abstract', pat.get('snippet', ''))[:1000],
                                        "verified": True  # Indexed into Patent Library
                                    })
                                print(f"   📋 Tracked {len(patent_raw_results)} patents for Reference Registry")
                        else:
                            print("   ⚠️ No patents found for this topic.")
                    # v6.3: Also search existing Patent Library for previously found patents
                    existing_patent_ctx = patent_library.search_patents(optimized_query)
                    if existing_patent_ctx:
                        patent_context += f"\n\n**📋 PREVIOUSLY FOUND PATENTS (from Patent DB):**\n{existing_patent_ctx}\n"
                        print(f"   📋 Injected {len(existing_patent_ctx)} chars from Patent Library DB.")
                except Exception as e:
                    print(f"⚠️ Patent Research Failed: {e}")
            else:
                print("🔬 Patent Research skipped by user preference.")

            # --- GENERAL WEB RESEARCH (Tavily) ---
            if use_web:
                try:
                    search = TavilySearch(max_results=base_web_results)  # v13.0: dynamic count
                    
                    # v14.0: Multi-Query Execution
                    all_results = []
                    for sq in all_web_queries:
                        search_query = sq[:200]
                        print(f"  🔎 General Search query: {search_query[:80]}...")
                        
                        # v6.3: Check cache first
                        cached = _get_cached_results(search_query, project_id)
                        if cached is not None:
                            sq_results = cached
                            print(f"  💾 Using cached Tavily results ({len(sq_results)} items) for query: {search_query[:30]}...")
                        else:
                            sq_results = search.invoke(search_query)

                            # langchain-tavily TavilySearch returns a dict: {'results': [...]}
                            # TavilySearchResults (old) returned a list directly.
                            # Normalise to list regardless of format.
                            if isinstance(sq_results, dict):
                                sq_results = sq_results.get('results', [])

                            # Handle error responses
                            if isinstance(sq_results, str):
                                if 'Error' in sq_results or 'error' in sq_results:
                                    print(f"  ❌ Tavily API Error: {sq_results[:200]}")
                                    sq_results = []
                                else:
                                    try:
                                        sq_results = json.loads(sq_results)
                                        if isinstance(sq_results, dict):
                                            sq_results = sq_results.get('results', [])
                                    except json.JSONDecodeError:
                                        print(f"  ⚠️ Unexpected string result, skipping web search")
                                        sq_results = []

                        # v6.3: Save to cache (only valid results — snippets only for cache)
                            if sq_results and isinstance(sq_results, list):
                                _save_cache(search_query, sq_results, project_id)

                        if sq_results and isinstance(sq_results, list):
                            all_results.extend(sq_results)
                    
                    # Deduplicate results by URL to prevent redundant scraping
                    seen_urls = set()
                    unique_results = []
                    for r in all_results:
                        if isinstance(r, dict):
                            url = r.get('url', '')
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                unique_results.append(r)
                        elif isinstance(r, str):
                            if r not in seen_urls:
                                seen_urls.add(r)
                                unique_results.append(r)
                    
                    results = unique_results[:30] # Cap at 30 to preserve prompt token limit during LLM filtering
                    
                    # v13.1: Web Relevance Filter — score before full-text scraping & DB indexing
                    if results and isinstance(results, list):
                        print(f"  🔍 Pre-index web relevance filtering ({len(results)} distinct candidates)...")
                        try:
                            web_list = ""
                            for i, r in enumerate(results):
                                if isinstance(r, dict):
                                    t = r.get('title', 'No Title')
                                    snippet = r.get('content', '')[:150]
                                    url = r.get('url', '')
                                else:
                                    t, snippet, url = f"Result {i+1}", str(r)[:150], ""
                                web_list += f"{i+1}. \"{t}\" ({url[:60]}) — {snippet}\n"
                            
                            filter_prompt = f"""You are a Research Librarian. Score each web search result's relevance to the research topic.

Original Research Goal: {original_goal[:400]}
Current Search Topic: "{topic[:300]}"

**Web results to evaluate:**
{web_list}

**SCORING RULES:**
- 8-10: Directly relevant (mentions the specific entities, events, or concepts being researched)
- 5-7: Tangentially related (same general domain but different specific focus)
- 1-4: Irrelevant (only shares surface keywords, different domain entirely)

**CRITICAL:** Avoid results about completely unrelated entities that happen to share a random keyword (e.g. a restaurant sharing a name with a CEO).

**OUTPUT FORMAT:** JSON array of integer scores only, one per result, in order.
Example: [9, 2, 7, 1, 8]"""
                            
                            filter_res = local_llm.invoke([HumanMessage(content=filter_prompt)])
                            filter_content = str(filter_res.content)
                            if '</think>' in filter_content:
                                filter_content = filter_content.split('</think>')[-1].strip()
                            filter_content = filter_content.replace("```json","").replace("```","").strip()
                            
                            import ast as _ast
                            web_scores = _ast.literal_eval(filter_content)
                            
                            if isinstance(web_scores, list) and len(web_scores) == len(results):
                                filtered_results = []
                                for r, score in zip(results, web_scores):
                                    try:
                                        s = float(score)
                                    except (ValueError, TypeError):
                                        s = 5.0
                                    t = r.get('title', 'No Title')[:60] if isinstance(r, dict) else f"{r}"[:60]
                                    if s >= 5.0:
                                        filtered_results.append(r)
                                        print(f"   ✅ [{s:.0f}/10] {t}")
                                    else:
                                        print(f"   ❌ [{s:.0f}/10] {t} — SKIPPED")
                                print(f"   📊 Web Filter: {len(filtered_results)}/{len(results)} results passed")
                                results = filtered_results
                            else:
                                print(f"   ⚠️ Web score mismatch ({len(web_scores)} vs {len(results)}). Keeping all.")
                        except Exception as _fe:
                            print(f"   ⚠️ Web relevance filter failed: {_fe}. Keeping all results.")
                    
                    # v7.0: Enrich with full page content (only relevant results)
                    print(f"  📄 Fetching full page content from top web results...")
                    results = _enrich_web_results(results, project_id, max_fetch=5)
                    
                    web_context = "\n\n**EXTERNAL WEB FINDINGS (General):**\n"
                    
                    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    DATA_DIR = os.path.join(BASE_DIR, "data", "projects", project_id)
                    topic_slug = topic[:30].replace(' ', '_').replace('/', '_')
                    research_dir = os.path.join(DATA_DIR, "web_research", topic_slug)
                    os.makedirs(research_dir, exist_ok=True)
                    
                    current_timestamp = int(time.time())
    
                    for i, res in enumerate(results):
                        if isinstance(res, dict):
                            title = res.get('title', 'No Title')
                            link = res.get('url', '#')
                            content = res.get('content', '')
                            has_fulltext = res.get('has_fulltext', False)
                        else:
                            title = f"Result {i+1}"
                            link = "#"
                            content = str(res)[:500]
                            has_fulltext = False
                        
                        # Use more content in context for full-text pages
                        ctx_len = 2000 if has_fulltext else 300
                        ft_tag = " ✅ Full-Text" if has_fulltext else ""
                        web_context += f"- [{title}]({link}){ft_tag}: {content[:ctx_len]}...\n"
                        
                        file_name = f"web_{i}_{current_timestamp}.txt"
                        file_path = os.path.join(research_dir, file_name)
                        
                        with open(file_path, "w") as f:
                            f.write(f"SOURCE: {link}\nTITLE: {title}\nFULL_TEXT: {has_fulltext}\n\n{content}")
                        
                        # v13.0: Track discovered web sources for Reference Registry
                        discovered_sources.append({
                            "type": "web",
                            "title": title,
                            "url": link,
                            "source_file": file_path,
                            "content": content[:1000],
                            "has_fulltext": has_fulltext,
                            "verified": os.path.exists(file_path)
                        })
                        
                        log_web_research(topic, title, link, content[:500], file_path=file_path, project_id=project_id)
                    
                    # v6.3: Auto-index web results into Web Search Library DB
                    if results and isinstance(results, list):
                        web_search_library.index_results(results, search_query=search_query)
                    
                    print(f"💾 Web Research logged to Vault and {research_dir}")
                    
                    # v6.3: Also search existing Web Library for previously found results
                    existing_web_ctx = web_search_library.search(topic)
                    if existing_web_ctx:
                        web_context += f"\n\n**🌐 PREVIOUSLY FOUND WEB RESULTS (from Web DB):**\n{existing_web_ctx}\n"
                        print(f"   🌐 Injected {len(existing_web_ctx)} chars from Web Search Library DB.")
                    
                except Exception as e:
                    print(f"⚠️ Web Search Failed: {e}")
                    web_context = "\n(Web Search Failed)"
            else:
                print("🔎 General Web Research skipped by user preference.")
                
            # --- MEDIA RESEARCH (YouTube) ---
            media_context = ""
            if use_media:
                try:
                    from app.utils.media_researcher import MediaResearcher
                    media_researcher = MediaResearcher()
                    print("🎬 Activating Media Research Protocol...")
                    
                    # Truncate topic for search using the optimized query
                    search_query = optimized_query[:100].split('\n')[0]
                    videos = media_researcher.research(search_query, max_results=3)
                    
                    if videos:
                        media_context = "\n\n**🎬 MEDIA/YOUTUBE FINDINGS:**\n"
                        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        DATA_DIR = os.path.join(BASE_DIR, "data", "projects", project_id)
                        topic_slug = topic[:30].replace(' ', '_').replace('/', '_')
                        media_dir = os.path.join(DATA_DIR, "media_research", topic_slug)
                        os.makedirs(media_dir, exist_ok=True)
                        
                        current_timestamp = int(time.time())
                        indexed_videos = []
                        
                        for i, video in enumerate(videos):
                            title = video.get('title', 'Unknown')
                            url = video.get('url', '#')
                            content = video.get('content', '')
                            
                            media_context += f"- [{title}]({url}): {content[:500]}...\n"
                            
                            # Save to file
                            file_name = f"media_{i}_{current_timestamp}.txt"
                            file_path = os.path.join(media_dir, file_name)
                            with open(file_path, "w") as f:
                                f.write(f"SOURCE: {url}\nTITLE: {title}\nCHANNEL: {video.get('channel')}\n\nTRANSCRIPT:\n{content}")
                            
                            indexed_videos.append(video)
                        
                        # Index to Vector DB
                        if indexed_videos:
                            media_library.index_media(indexed_videos)
                            print(f"💾 Media transcripts logged to {media_dir} and DB")
                    else:
                        print("   ⚠️ No media transcripts found.")
                    
                    # Search existing Media Library
                    existing_media_ctx = media_library.search_media(optimized_query)
                    if existing_media_ctx:
                        media_context += f"\n\n**🎬 PREVIOUSLY FOUND MEDIA (from Media DB):**\n{existing_media_ctx}\n"
                        print(f"   🎬 Injected {len(existing_media_ctx)} chars from Media Library DB.")
                
                except Exception as e:
                    print(f"⚠️ Media Research Failed: {e}")
            else:
                print("🎬 Media Research skipped by user preference.")
                
            # Combine Contexts (Academic + Patent + Web + Media)
            web_context = academic_context + patent_context + web_context + media_context

        # Load Master Report
        master_report_content = ""
        incremental_path = state.get('incremental_report_path', '')
        if incremental_path and os.path.exists(incremental_path):
            try:
                with open(incremental_path, "r") as f:
                    master_report_content = f.read()
                print(f"📖 Loaded Incremental Master Report ({len(master_report_content)} chars)")
            except Exception as e:
                print(f"⚠️ Failed to read incremental report: {e}")
        
        # Warden Strategic Brief
        warden_brief = ""
        shared_knowledge = state.get('shared_knowledge', '')
        if "--- WARDEN STRATEGIC BRIEF ---" in shared_knowledge:
            parts = shared_knowledge.split("--- WARDEN STRATEGIC BRIEF ---")
            if len(parts) > 1:
                warden_brief = parts[1].split("\n\n")[0]
                print("👁️ Warden Strategic Brief detected.")
        
        # ===== CHUNKED PROCESSING =====
        full_context = f"""
**LOCAL KNOWLEDGE BASE:**
{local_context}

**WEB FINDINGS:**
{web_context}

**PREVIOUS REPORT (Master Report):**
{master_report_content[-8000:] if len(master_report_content) > 8000 else master_report_content}

**WARDEN BRIEF:**
{warden_brief}
"""
        
        total_tokens = estimate_tokens(full_context)
        print(f"🧬 ACTIVATING DEEP RESEARCH ENGINE for: {topic}")
        print(f"📊 Total context: ~{total_tokens} tokens")
        
        if total_tokens > MAX_CHUNK_TOKENS:
            print(f"🔄 Context exceeds limit ({MAX_CHUNK_TOKENS} tokens). Using chunked processing...")
            
            chunks = chunk_text(full_context, MAX_CHUNK_TOKENS)
            print(f"📦 Split into {len(chunks)} chunks")
            
            chunk_analyses = []
            for i, chunk in enumerate(chunks):
                print(f"  └─ Processing chunk {i+1}/{len(chunks)}...")
                
                try:
                    chunk_prompt = f"""
**CHUNK {i+1} of {len(chunks)} - Topic: "{topic}"**

{chunk}

Analyze this chunk and extract key information:
"""
                    response = llm_deep.invoke([
                        SystemMessage(content=CHUNK_ANALYSIS_PROMPT),
                        HumanMessage(content=chunk_prompt)
                    ])
                    chunk_analyses.append(f"--- Chunk {i+1} Analysis ---\n{response.content}")
                except Exception as e:
                    print(f"  ⚠️ Chunk {i+1} failed: {e}")
                    chunk_analyses.append(f"--- Chunk {i+1} Analysis ---\n(Failed: {e})")
            
            print(f"🔗 Synthesizing {len(chunk_analyses)} chunk analyses into final report...")
            
            all_analyses = "\n\n".join(chunk_analyses)
            safe_analyses = all_analyses[:25000] if len(all_analyses) > 25000 else all_analyses
            
            synthesis_prompt = SYNTHESIS_PROMPT.format(
                chunk_analyses=safe_analyses,
                topic=topic
            )
            
            try:
                response = llm_deep.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=synthesis_prompt)
                ])
                report_content = response.content
            except Exception as e:
                report_content = f"Synthesis Failed: {e}\n\n--- Raw Chunk Analyses ---\n" + "\n\n".join(chunk_analyses)
        
        else:
            print(f"✅ Context within limit. Direct processing...")
            
            prompt = f"""
**STRICT TASK: PERFORM DEEP RESEARCH ON "{topic}"**

{full_context}

**INSTRUCTIONS:**
1. Analyze the context deeply.
2. Produce **STRUCTURED RESEARCH NOTES** (Not an essay).
3. Focus on **Hard Facts**, **Technical Specs**, and **Formulas**.
4. Language: **ENGLISH**.
5. Structure: [1. Key Findings, 2. Technical Details, 3. Critical Analysis].
"""
            
            try:
                response = llm_deep.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=prompt)
                ])
                report_content = response.content
            except Exception as e:
                report_content = f"Deep Research Model Failed: {e}"

        # Save Research Notes
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_Step{current_index+1}_Sub{current_sub_idx+1}_Research_Notes_v{iteration+1}"
        save_artifact(filename, report_content, "md", thread_id=thread_id)

        # v13.0: Log discovered source summary
        print(f"📋 Deep Researcher Completed. Discovered {len(discovered_sources)} traceable sources:")
        src_types = {}
        for ds in discovered_sources:
            src_types[ds['type']] = src_types.get(ds['type'], 0) + 1
        for stype, scount in src_types.items():
            print(f"   └─ {stype}: {scount}")
        
        return {
            "sender": "DeepResearcher",
            "web_knowledge": report_content,
            "shared_knowledge": f"--- RESEARCH NOTES (From Deep Investigator about '{topic}') ---\n{report_content}",
            "iteration_count": iteration,
            "sub_plan": state.get("sub_plan", []),
            "deep_research_sources": discovered_sources,  # v13.0: Pass source metadata to Writer
            "messages": [SystemMessage(content=f"Research Notes on '{topic}' generated successfully. {len(discovered_sources)} traceable sources discovered.")]
        }

    except Exception as e:
        print(f"⚠️ Deep Researcher Node Critical Failure: {e}")
        log_night_audit("DeepResearcher", f"Critical Failure: {str(e)}")
        return {
            "web_knowledge": f"Deep Research Failed: {e}",
            "shared_knowledge": f"--- RESEARCH FAILED ---",
            "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
            "messages": [SystemMessage(content=f"Deep Research Failed: {e}")]
        }
