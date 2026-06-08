import os
import requests
import arxiv
import pymupdf4llm
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.local_model import local_llm

class AcademicResearcher:
    def __init__(self, output_dir=None):
        # Use Absolute Path to prevent Errno 2
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = output_dir or os.path.join(base_dir, "data", "papers")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # v4.5: Initialize Local Paper Library
        try:
            from app.core.rag import PaperLibrary
            self.paper_library = PaperLibrary(papers_dir=self.output_dir)
            print("📚 Paper Library initialized.")
        except Exception as e:
            print(f"⚠️ Paper Library init failed: {e}")
            self.paper_library = None
        
    def extract_keywords(self, topic: str, original_goal: str = "") -> list:
        """
        v13.0: Domain-aware academic keyword extraction.
        Classifies the topic domain first, then generates appropriate search keywords.
        Preserves proper nouns, company names, and person names.
        """
        context_block = ""
        if original_goal and original_goal != topic:
            context_block = f"\n**Original Research Goal**: \"{original_goal[:500]}\""
        
        prompt = f"""You are a Senior Academic Search Strategist. Your job is to generate the BEST possible search keywords for academic paper databases (ArXiv, Semantic Scholar).

**STEP 1 — DOMAIN CLASSIFICATION:**
Read the topic and classify it into ONE of these domains:
- TECHNOLOGY: engineering, CS, AI, robotics, hardware, algorithms
- BUSINESS: corporate strategy, leadership, branding, market analysis, management
- SOCIAL: design, culture, UX, psychology, sociology, urban planning
- HUMANITIES: art, philosophy, history, media studies, linguistics

**STEP 2 — KEYWORD STRATEGY (based on domain):**
- TECHNOLOGY → Use technical terms, algorithm names, methodology names, framework names
- BUSINESS → Use person names, company names, industry terms, strategic concepts
- SOCIAL → Use theory names, design movement names, practitioner names, concepts
- HUMANITIES → Use proper nouns, movement names, period terms, key figures

**CRITICAL RULES:**
1. ALWAYS include proper nouns (person names, company names, brand names) if they appear in the topic
2. NEVER replace a specific entity with a generic term (e.g., do NOT replace "Samsung" with "consumer electronics")
3. Generate 3-5 keywords that would actually find RELEVANT papers on THIS SPECIFIC topic
4. Each keyword can be 1-3 words (phrases are OK for academic search)

**Research Context:**
{context_block}
**Current Search Topic**: "{topic}"

**OUTPUT FORMAT:** Python list only, no explanation.
Example for "Elon Musk's aerospace philosophy at SpaceX": ["Elon Musk", "SpaceX engineering", "aerospace corporate", "reusable rockets", "Mars colonization strategy"]
Example for "DMP trajectory optimization": ["dynamic movement primitives", "ProDMP", "trajectory optimization robotics", "movement primitive learning"]
"""
        try:
            response = local_llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            # Handle thinking tags
            if '</think>' in str(content):
                content = str(content).split('</think>')[-1].strip()
            content = str(content).replace("```json", "").replace("```python", "").replace("```", "").strip()
            
            import ast
            keywords = ast.literal_eval(content)
            if isinstance(keywords, list) and len(keywords) > 0:
                print(f"   🎯 Domain-Aware Keywords: {keywords}")
                return keywords
            return [topic[:100]]
        except Exception as e:
            print(f"⚠️ Keyword extraction failed: {e}")
            return [topic[:100]]

    # Class-level ArXiv client for connection reuse & internal rate-limit state
    _arxiv_client = None
    _arxiv_blocked = False  # Track if ArXiv API is currently blocked

    @classmethod
    def _get_arxiv_client(cls):
        if cls._arxiv_client is None:
            cls._arxiv_client = arxiv.Client(
                page_size=10,
                delay_seconds=5.0,  # ArXiv official recommendation: ≥3s
                num_retries=2
            )
        return cls._arxiv_client

    def _get_s2_headers(self):
        """Get Semantic Scholar API headers. Uses S2_API_KEY if available for higher rate limits (100 RPM vs 1 RPM)."""
        headers = {}
        api_key = os.environ.get('S2_API_KEY', '')
        if api_key:
            headers['x-api-key'] = api_key
        return headers

    def _search_arxiv_via_semantic_scholar(self, query: str, max_results: int = 5) -> list:
        """Fallback: Search for ArXiv papers through Semantic Scholar API with retry."""
        import time
        import random
        
        print(f"   🔄 ArXiv Fallback: Searching via Semantic Scholar for ArXiv papers...")
        
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,year,abstract,openAccessPdf,externalIds",
            "venue": "arxiv"  # Filter to ArXiv papers only
        }
        headers = self._get_s2_headers()
        
        max_retries = 3
        base_backoff = 15
        
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    time.sleep(8.0 + random.uniform(2.0, 5.0))
                else:
                    wait_time = base_backoff * (2 ** attempt) + random.uniform(5.0, 10.0)
                    print(f"   ⏳ ArXiv Fallback backoff: waiting {wait_time:.1f}s before retry {attempt+1}...")
                    time.sleep(wait_time)
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for paper in data.get('data', []):
                        pdf_url = None
                        if paper.get('openAccessPdf'):
                            pdf_url = paper['openAccessPdf'].get('url')
                        
                        # Try to get ArXiv PDF URL from externalIds
                        arxiv_id = None
                        ext_ids = paper.get('externalIds', {})
                        if ext_ids and ext_ids.get('ArXiv'):
                            arxiv_id = ext_ids['ArXiv']
                            if not pdf_url:
                                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                        
                        results.append({
                            "title": paper.get('title'),
                            "authors": [a['name'] for a in paper.get('authors', [])],
                            "summary": paper.get('abstract') or "No abstract available.",
                            "pdf_url": pdf_url,
                            "published": str(paper.get('year')),
                            "source": "ArXiv (via Semantic Scholar)"
                        })
                    print(f"   ✅ ArXiv Fallback: Found {len(results)} papers via Semantic Scholar.")
                    return results
                elif response.status_code in (429, 503):
                    print(f"   ⚠️ ArXiv Fallback: HTTP {response.status_code}. Attempt {attempt+1}/{max_retries}.")
                    continue
                else:
                    print(f"   ⚠️ ArXiv Fallback also failed: HTTP {response.status_code}")
                    return []
            except Exception as e:
                print(f"   ⚠️ ArXiv Fallback attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1: return []
        
        return []

    def search_arxiv(self, query: str, max_results: int = 5) -> list:
        """Searches ArXiv for papers. Falls back to Semantic Scholar if ArXiv API is blocked."""
        import time
        import random
        
        # Cap max_results to avoid huge responses that trigger 503
        max_results = min(max_results, 10)
        print(f"📚 Searching ArXiv for: {query} (max_results={max_results})")
        
        # If ArXiv was previously blocked in this session, skip entirely
        if AcademicResearcher._arxiv_blocked:
            print("   ⚡ ArXiv API known blocked — skipping. (Semantic Scholar also disabled)")
            return []
        
        max_retries = 2
        base_backoff = 8
        
        for attempt in range(max_retries):
            try:
                # Pre-request delay
                if attempt == 0:
                    wait_time = 5.0 + random.uniform(1.0, 3.0)
                else:
                    wait_time = base_backoff * (2 ** attempt) + random.uniform(2.0, 5.0)
                    print(f"   ⏳ ArXiv backoff: waiting {wait_time:.1f}s before retry {attempt+1}...")
                
                time.sleep(wait_time)
                
                client = self._get_arxiv_client()
                
                search = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.Relevance
                )
                
                results = []
                for result in client.results(search):
                    results.append({
                        "title": result.title,
                        "authors": [a.name for a in result.authors],
                        "summary": result.summary,
                        "pdf_url": result.pdf_url,
                        "published": result.published.strftime("%Y-%m-%d"),
                        "source": "ArXiv"
                    })
                print(f"✅ ArXiv found {len(results)} papers.")
                return results
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "503" in error_msg or "Rate Limit" in error_msg or "timed out" in error_msg.lower():
                    print(f"⚠️ ArXiv API blocked ({error_msg[:80]}). Attempt {attempt+1}/{max_retries}.")
                    if attempt == max_retries - 1:
                        AcademicResearcher._arxiv_blocked = True
                        print("🚫 ArXiv API blocked for this session. Skipping academic search.")
                        return []
                    continue
                print(f"⚠️ ArXiv search failed: {e}")
                return []
                
        return []

    def search_semantic_scholar(self, query: str, max_results: int = 5) -> list:
        """Searches Semantic Scholar for papers with robust Rate Limit handling."""
        import time
        import random
        
        max_results = min(max_results, 10)
        print(f"📚 Searching Semantic Scholar for: {query} (max_results={max_results})")
        
        url = f"https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,year,abstract,openAccessPdf"
        }

        max_retries = 2  # Fail fast — ArXiv is the primary academic source
        base_backoff = 8
        
        for attempt in range(max_retries):
            try:
                # Pre-request delay: 5s + jitter to stay well under 1 RPS
                if attempt == 0:
                    time.sleep(5.0 + random.uniform(1.0, 3.0))
                else:
                    wait_time = base_backoff * (2 ** attempt) + random.uniform(3.0, 6.0)
                    print(f"   ⏳ Semantic Scholar backoff: waiting {wait_time:.1f}s before retry {attempt+1}...")
                    time.sleep(wait_time)
                
                headers = self._get_s2_headers()
                response = requests.get(url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for paper in data.get('data', []):
                        pdf_url = None
                        if paper.get('openAccessPdf'):
                            pdf_url = paper['openAccessPdf'].get('url')
                        
                        results.append({
                            "title": paper.get('title'),
                            "authors": [a['name'] for a in paper.get('authors', [])],
                            "summary": paper.get('abstract') or "No abstract available.",
                            "pdf_url": pdf_url,
                            "published": str(paper.get('year')),
                            "source": "Semantic Scholar"
                        })
                    print(f"✅ Semantic Scholar found {len(results)} papers.")
                    return results
                
                elif response.status_code in (429, 503):
                    retry_wait = base_backoff * (2 ** (attempt + 1)) + random.uniform(3.0, 8.0)
                    print(f"⚠️ Semantic Scholar {response.status_code}. Retrying in {retry_wait:.1f}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_wait)
                else:
                    print(f"⚠️ Semantic Scholar API Error: {response.status_code}")
                    return []
            except Exception as e:
                print(f"⚠️ Semantic Scholar search attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1: return []
                time.sleep(retry_delay)
        
        return []

    def download_pdf(self, url: str, title: str) -> str:
        """Downloads a PDF from a URL and saves it to the output directory."""
        try:
            # Sanitize filename
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
            safe_title = safe_title.replace(" ", "_")[:50]
            filename = f"{safe_title}.pdf"
            path = os.path.join(self.output_dir, filename)
            
            if os.path.exists(path):
                print(f"📄 PDF already exists: {path}")
                return path
            
            print(f"⬇️ Downloading PDF: {title}...")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"✅ Downloaded to: {path}")
                
                # v4.5: Auto-index into Paper Library
                if self.paper_library:
                    try:
                        self.paper_library.index_single_paper(path)
                    except Exception as e:
                        print(f"   ⚠️ Auto-index failed: {e}")
                
                return path
            else:
                print(f"❌ Failed to download PDF (Status {response.status_code})")
                return None
        except Exception as e:
            print(f"⚠️ PDF Download Error: {e}")
            return None

    def _unload_llm_from_gpu(self):
        """v5.1: Unload the LLM from GPU to free VRAM for Marker."""
        import subprocess
        try:
            model_name = os.getenv("LOCAL_LLM_MODEL", "gemma4:31b")
            print(f"🔄 GPU Swap: Unloading LLM ({model_name}) from GPU...")
            result = subprocess.run(
                ["ollama", "stop", model_name],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print("✅ GPU Swap: LLM unloaded. GPU is free for Marker.")
            else:
                print(f"⚠️ GPU Swap: ollama stop returned {result.returncode}: {result.stderr}")
            # Give GPU a moment to release memory
            import time
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ GPU Swap: Failed to unload LLM: {e}")

    def _reload_llm_to_gpu(self):
        """v13.1: Pre-warm the LLM back onto GPU after Marker finishes."""
        import subprocess
        import time
        try:
            model_name = os.getenv("LOCAL_LLM_MODEL", "gemma4:31b")
            print(f"🔄 GPU Swap: Re-loading LLM ({model_name}) onto GPU...")
            # Send a minimal prompt to force Ollama to load the model
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
                 "-d", f'{{"model":"{model_name}","prompt":"hi","stream":false,"options":{{"num_predict":1}}}}',
                 "--max-time", "60"],
                capture_output=True, text=True, timeout=90
            )
            if result.returncode == 0:
                print(f"✅ GPU Swap: LLM ({model_name}) re-loaded onto GPU.")
            else:
                print(f"⚠️ GPU Swap: LLM reload returned {result.returncode}")
        except Exception as e:
            print(f"⚠️ GPU Swap: Failed to reload LLM: {e}. Will auto-reload on next call.")

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Converts a PDF to Markdown using Marker (GPU) or pymupdf4llm (fallback)."""
        try:
            print(f"🔄 Converting PDF to Markdown with Marker: {pdf_path}")
            
            import subprocess
            
            # Output directory for marker
            output_dir = os.path.join(self.output_dir, "marker_output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Check if already converted (cache)
            filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
            md_file = os.path.join(output_dir, filename_base, f"{filename_base}.md")
            if os.path.exists(md_file):
                print(f"📄 Marker cache hit: {md_file}")
                with open(md_file, "r") as f:
                    return f.read()
            
            # v5.1: Run Marker with TORCH_DEVICE=cuda (GPU freed by _unload_llm_from_gpu)
            cmd = [
                "marker_single",
                "--output_dir", output_dir,
                "--output_format", "markdown",
                pdf_path
            ]
            
            env = os.environ.copy()
            env["TORCH_DEVICE"] = "cuda"  # Force GPU for Marker
            
            print(f"🚀 Running (GPU): {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
            
            if result.returncode == 0:
                if os.path.exists(md_file):
                    with open(md_file, "r") as f:
                        return f.read()
            
            print(f"⚠️ Marker failed (Code {result.returncode}): {result.stderr[:200]}")
            print(f"⚠️ Falling back to pymupdf4llm...")
            
            # Fallback to pymupdf4llm (no GPU needed, instant)
            import pymupdf4llm
            return pymupdf4llm.to_markdown(pdf_path)

        except subprocess.TimeoutExpired:
            print(f"⚠️ Marker timed out (120s). Falling back to pymupdf4llm...")
            import pymupdf4llm
            return pymupdf4llm.to_markdown(pdf_path)
        except Exception as e:
            print(f"⚠️ PDF Conversion Failed: {e}")
            return ""

    def filter_by_relevance(self, papers: list, topic: str, original_goal: str = "", threshold: float = 5.0) -> list:
        """
        v13.0: Pre-download relevance filtering.
        Uses LLM to score each paper's title+abstract against the research context.
        Papers below threshold are skipped to avoid polluting the DB.
        """
        if not papers:
            return []
        
        # Build paper list for batch scoring
        paper_list = ""
        for i, p in enumerate(papers):
            title = p.get('title', 'Unknown')
            abstract = (p.get('summary', p.get('abstract', '')) or '')[:200]
            paper_list += f"{i+1}. \"{title}\" — {abstract}\n"
        
        context_block = ""
        if original_goal:
            context_block = f"Original Research Goal: {original_goal[:500]}\n"
        
        prompt = f"""You are a Research Librarian. Score each paper's relevance to the research topic.

{context_block}Current Search Topic: "{topic[:500]}"

**Papers to evaluate:**
{paper_list}

**SCORING RULES:**
- 8-10: Directly addresses the research topic (specific entities, methods, or cases match)
- 5-7: Tangentially related (same general field but different specific focus)
- 1-4: Irrelevant (different domain entirely, or only shares generic keywords)

**CRITICAL:** A paper about "human-centered AI" is NOT relevant to "Samsung design leadership" just because both contain the word "design".

**OUTPUT FORMAT:** JSON array of scores only, one per paper, in order.
Example: [8, 3, 6, 2, 9]
"""
        try:
            response = local_llm.invoke([HumanMessage(content=prompt)])
            content = str(response.content)
            if '</think>' in content:
                content = content.split('</think>')[-1].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            
            import ast
            scores = ast.literal_eval(content)
            
            if isinstance(scores, list) and len(scores) == len(papers):
                filtered = []
                for i, (paper, score) in enumerate(zip(papers, scores)):
                    try:
                        score_val = float(score)
                    except (ValueError, TypeError):
                        score_val = 5.0  # Default to include if parsing fails
                    
                    if score_val >= threshold:
                        filtered.append(paper)
                        print(f"   ✅ [{score_val:.0f}/10] {paper.get('title', 'Unknown')[:60]}")
                    else:
                        print(f"   ❌ [{score_val:.0f}/10] {paper.get('title', 'Unknown')[:60]} — SKIPPED")
                
                print(f"   📊 Relevance Filter: {len(filtered)}/{len(papers)} papers passed (threshold: {threshold})")
                return filtered
            else:
                print(f"   ⚠️ Score count mismatch ({len(scores)} vs {len(papers)}). Keeping all papers.")
                return papers
                
        except Exception as e:
            print(f"   ⚠️ Relevance filtering failed: {e}. Keeping all papers.")
            return papers

    def analyze_papers(self, papers_data: list, topic: str = "", original_goal: str = "") -> str:
        """
        Orchestrates the analysis:
        0. v13.0: Filter papers by relevance BEFORE downloading
        1. Unload LLM from GPU (free VRAM for Marker)
        2. Downloads PDFs
        3. Converts to MD using Marker on GPU (fast)
        4. LLM auto-reloads on next call
        5. Returns combined context
        """
        # v13.0: Pre-download relevance filter
        if topic or original_goal:
            print(f"   🔍 Pre-download relevance filtering ({len(papers_data)} candidates)...")
            papers_data = self.filter_by_relevance(papers_data, topic, original_goal, threshold=5.0)
        
        if not papers_data:
            print("   ⚠️ No papers passed relevance filter. Skipping download.")
            return ""
        
        combined_context = ""
        
        # v5.1: Unload LLM before batch PDF conversion
        has_pdfs = any(p.get('pdf_url') for p in papers_data)
        if has_pdfs:
            self._unload_llm_from_gpu()
        
        for paper in papers_data:
            pdf_url = paper.get('pdf_url')
            if pdf_url:
                pdf_path = self.download_pdf(pdf_url, paper['title'])
                if pdf_path:
                    # Store local_path for Reference Registry tracking
                    paper['local_path'] = pdf_path
                    
                    md_content = self.convert_pdf_to_markdown(pdf_path)
                    if md_content:
                        max_chars = 15000 
                        if len(md_content) > max_chars:
                            base_content = md_content[:max_chars]
                            content_preview = f"{base_content}\n\n...(Truncated at {max_chars} chars)..."
                        else:
                            content_preview = md_content

                        summary = f"### 📄 Paper: {paper['title']}\n"
                        summary += f"**Authors**: {', '.join(paper['authors'])}\n"
                        summary += f"**Source**: {paper['source']} ({paper['published']})\n"
                        summary += f"**Content (Full/Extracted)**:\n{content_preview}\n\n---\n\n"
                        
                        combined_context += summary
        
        if has_pdfs:
            print("🔄 GPU Swap: All PDFs processed. Pre-warming LLM...")
            self._reload_llm_to_gpu()
        
        return combined_context

    def search_local_library(self, query: str, k: int = 5) -> str:
        """v4.5: Searches the local paper library for relevant papers."""
        if not self.paper_library:
            return ""
        return self.paper_library.search_papers(query, k=k)
