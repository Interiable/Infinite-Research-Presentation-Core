"""
Patent Research Module (v9.0)
Expert-level patent search with:
  - Technology description → Concept extraction via Gemini/GPT (TieredLLMWrapper)
  - Iterative refinement loop (max 3 iterations)
  - LLM-based relevance scoring and filtering
  - Domain anchor terms to ensure results stay in correct technology domain
  
  Tier 1: Google Patents BigQuery    ← MAIN (90M+ worldwide patents, SQL)
  Tier 2: USPTO Bulk Data API        ← SECONDARY (US patent grants & applications, free, no auth)
  Tier 3: PatentsView API            ← METADATA (US patent metadata, free)
  Optional: Lens Patent API          ← OPTIONAL (if API key available)
  
  + Google Patents Full-Text Scraping (claims, description, abstract)
    Saves to data/patents/{patent_id}.json for archival
"""

import os
import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage
from app.utils import RobustGemini

# v9.0: Use Gemini/GPT via RobustGemini for patent reasoning (strategy generation, keyword refinement)
patent_llm = RobustGemini(temperature=0.3)
# v9.3: Use Gemini Flash for lightweight scoring tasks (much faster + cheaper)
from langchain_google_genai import ChatGoogleGenerativeAI
scoring_llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_FLASH_MODEL", "gemini-3.5-flash"),
    temperature=0.2,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)
print("🔬 Patent Research v9.3: RobustGemini for strategy, Gemini Flash for scoring.")


class PatentResearcher:
    """
    Orchestrates patent searches across BigQuery, USPTO, PatentsView, and optionally Lens.
    """

    # v10.7: BigQuery Result Cache (7-day TTL)
    _BQ_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "patent_cache")
    _BQ_CACHE_TTL = 7 * 86400  # 7 days in seconds (patent data rarely changes)

    def __init__(self):
        self.lens_api_key = os.getenv("LENS_API_KEY", "")
        self.gcp_project = os.getenv("GCP_PROJECT_ID", "")

        # BigQuery client (lazy-loaded)
        self._bq_client = None
        
        # Ensure cache directory exists
        os.makedirs(self._BQ_CACHE_DIR, exist_ok=True)

    def _bq_cache_key(self, query: str, strategy: dict = None) -> str:
        """Generate a stable hash for a BigQuery search query."""
        import hashlib
        normalized = query.strip().lower()[:300]
        cpc = ""
        if strategy:
            cpc = ",".join(sorted(strategy.get("cpc_codes", [])))
        return hashlib.md5(f"{normalized}|{cpc}".encode()).hexdigest()

    def _get_bq_cache(self, query: str, strategy: dict = None):
        """Returns cached BigQuery results if available and fresh."""
        key = self._bq_cache_key(query, strategy)
        cache_path = os.path.join(self._BQ_CACHE_DIR, f"{key}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if time.time() - data.get("timestamp", 0) < self._BQ_CACHE_TTL:
                    print(f"   💾 BigQuery CACHE HIT for: {query[:60]}... ({len(data.get('results', []))} patents)")
                    return data.get("results", [])
            except Exception:
                pass
        return None

    def _save_bq_cache(self, query: str, results: list, strategy: dict = None):
        """Saves BigQuery results to cache."""
        key = self._bq_cache_key(query, strategy)
        cache_path = os.path.join(self._BQ_CACHE_DIR, f"{key}.json")
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"query": query[:300], "timestamp": time.time(), "results": results}, f, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"   ⚠️ BigQuery cache save failed: {e}")

    def is_available(self) -> bool:
        """Returns True if at least one patent source is usable."""
        # USPTO + PatentsView are always free — so always available
        return True

    # =====================================================================
    # Expert Boolean Patent Search Formula Generator (v8.0)
    # =====================================================================
    def extract_patent_keywords(self, topic: str) -> List[str]:
        """Legacy wrapper — returns just keyword list for backward compatibility."""
        strategy = self.generate_search_strategy(topic)
        return strategy.get('keywords', [topic])

    def generate_search_strategy(self, topic: str, iteration: int = 0, prev_feedback: str = "") -> Dict:
        """
        v9.0: Technology Description → Concept Extraction → Query Expansion.
        Uses Gemini/GPT (TieredLLMWrapper) for expert-level concept extraction.
        
        Args:
            topic: Technology description (natural language)
            iteration: Current iteration number (0 = first pass)
            prev_feedback: Feedback from previous iteration about what went wrong
        """
        iteration_context = ""
        if iteration > 0 and prev_feedback:
            iteration_context = f"""

**⚠️ ITERATION {iteration + 1} — PREVIOUS SEARCH FAILED:**
{prev_feedback}

You MUST generate DIFFERENT and MORE PRECISE keywords this time.
Focus on the specific technology described, not generic mechanical terms.
Think about what a patent examiner would search for when classifying this technology.
"""

        prompt = f"""You are a Senior Patent Examiner and Search Strategist with 20+ years of IP experience.

**YOUR TASK:** Read the technology description below and extract the core patentable concepts.
Then generate precise patent search queries that would find RELEVANT prior art.

**TECHNOLOGY DESCRIPTION:**
\"{topic[:600]}\"
{iteration_context}

**STEP 1 — CONCEPT EXTRACTION:**
Identify 2-3 distinct technical concepts from the description (NOT more than 3).

**STEP 2 — QUERY EXPANSION (SINGLE-WORD TERMS ONLY):**
For each concept, generate 3 SINGLE-WORD synonyms as they would appear in patents.
⚠️ CRITICAL: Each term MUST be a SINGLE WORD (e.g., "robot", "projector", "gimbal", "articulated", "companion").
DO NOT use multi-word phrases (e.g., NOT "companion robot", NOT "display orientation apparatus").
The search engine uses substring matching, so single words work much better.

**STEP 3 — DOMAIN ANCHORS:**
Provide exactly 2 broad single-word domain terms (e.g., ["robot", "display"]).

**STEP 4 — EXCLUSION TERMS:**
List domains to exclude: medical/surgical, chemical, agricultural, automotive headlamp, etc.

**OUTPUT (JSON only, no explanation):**
{{
  "technology_summary": "one-line summary of what this technology does",
  "keywords": ["word1", "word2", "word3", "word4", "word5"],
  "domain_anchor_terms": ["robot", "display"],
  "concept_groups": [
    {{
      "concept": "what this concept does",
      "terms": ["single_word_1", "single_word_2", "single_word_3"]
    }}
  ],
  "boolean_queries": [
    "(term1 OR term2) AND (term3 OR term4)",
    "second query from different angle"
  ],
  "broadened_queries": [
    "broad single-concept query for recall"
  ],
  "cpc_codes": ["B25J", "G06F3"],
  "exclude_terms": ["surgical", "pharmaceutical", "agricultural", "headlamp"]
}}"""
        try:
            response = patent_llm.invoke([HumanMessage(content=prompt)])
            _rc = response.content
            raw_content = (''.join(c['text'] if isinstance(c, dict) else str(c) for c in _rc) if isinstance(_rc, list) else str(_rc)).strip()
            # Handle <think>...</think> tags from some models
            if '</think>' in raw_content:
                content = raw_content.split('</think>')[-1].strip()
            else:
                content = raw_content
            content = content.replace("```json", "").replace("```", "").strip()
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                content = content[start:end]
            
            import ast
            try:
                strategy = json.loads(content)
            except json.JSONDecodeError:
                strategy = ast.literal_eval(content)
            
            if not isinstance(strategy, dict):
                raise ValueError("Not a dict")
            
            # Ensure required keys
            strategy.setdefault('keywords', [])
            strategy.setdefault('domain_anchor_terms', [])
            strategy.setdefault('concept_groups', [])
            strategy.setdefault('boolean_queries', [])
            strategy.setdefault('broadened_queries', [])
            strategy.setdefault('cpc_codes', [])
            strategy.setdefault('exclude_terms', [])
            
            iter_label = f" (Iteration {iteration + 1})" if iteration > 0 else ""
            print(f"   🧠 Search Strategy Generated{iter_label}:")
            if strategy.get('technology_summary'):
                print(f"      Tech Summary: {strategy['technology_summary'][:100]}")
            print(f"      Keywords: {strategy['keywords'][:5]}")
            print(f"      Domain Anchors: {strategy.get('domain_anchor_terms', [])[:5]}")
            print(f"      Concept Groups: {len(strategy['concept_groups'])} groups")
            print(f"      Boolean Queries: {len(strategy['boolean_queries'])} formulas")
            print(f"      CPC Codes: {strategy['cpc_codes'][:5]}")
            print(f"      Exclude: {strategy['exclude_terms'][:5]}")
            
            return strategy
            
        except Exception as e:
            print(f"⚠️ Patent search strategy generation failed: {e}")
            words = [w for w in topic.split()[:8] if len(w) > 3]
            return {
                'keywords': words[:5],
                'domain_anchor_terms': ['robot', 'display', 'interactive'],
                'concept_groups': [],
                'boolean_queries': [' AND '.join(words[:3])],
                'broadened_queries': [],
                'cpc_codes': [],
                'exclude_terms': []
            }

    # =====================================================================
    # LLM-Based Relevance Scoring (v8.0)
    # =====================================================================
    def score_patent_relevance(self, patents: List[Dict], topic: str, threshold: float = 4.0) -> List[Dict]:
        """
        Uses LLM to score each patent's relevance to the research topic (0-10).
        Filters out patents below the threshold.
        """
        if not patents:
            return []
        
        scored = []
        batch_size = 5  # Score in batches for efficiency
        
        for i in range(0, len(patents), batch_size):
            batch = patents[i:i+batch_size]
            
            # Build batch description
            patent_descriptions = ""
            for j, p in enumerate(batch):
                title = p.get('title', 'No Title')[:150]
                abstract = p.get('abstract', '')[:300]
                patent_descriptions += f"\nPatent {j+1}: \"{title}\"\n  Abstract: {abstract}\n"
            
            prompt = (
                "You are a patent relevance evaluator. Score each patent's relevance to the research topic on a scale of 0-10.\n\n"
                f"**Research Topic:** \"{topic[:300]}\"\n\n"
                f"**Patents to evaluate:**\n{patent_descriptions}\n\n"
                "**Scoring Guide:**\n"
                "- 0-2: Completely unrelated (different field entirely)\n"
                "- 3-4: Tangentially related (shares some words but different application)\n"
                "- 5-6: Moderately related (same technical domain, different specific application)\n"
                "- 7-8: Highly relevant (directly addresses part of the research topic)\n"
                "- 9-10: Extremely relevant (core prior art for this research)\n\n"
                '**Output format (JSON array only, no markdown):**\n'
                '[{"patent_index": 1, "score": 7, "reason": "brief reason"}]\n\n'
                "Output ONLY the JSON array."
            )
            
            try:
                response = scoring_llm.invoke([HumanMessage(content=prompt)])
                _rc = response.content
                raw_content = (''.join(c['text'] if isinstance(c, dict) else str(c) for c in _rc) if isinstance(_rc, list) else str(_rc)).strip()
                # DeepSeek-R1: extract answer after </think>
                if '</think>' in raw_content:
                    content = raw_content.split('</think>')[-1].strip()
                else:
                    content = raw_content
                content = content.replace("```json", "").replace("```", "").strip()
                
                # Find JSON array
                start = content.find('[')
                end = content.rfind(']') + 1
                if start >= 0 and end > start:
                    content = content[start:end]
                
                scores = json.loads(content)
                
                for score_entry in scores:
                    idx = score_entry.get('patent_index', 0) - 1
                    score = float(score_entry.get('score', 0))
                    reason = score_entry.get('reason', '')
                    
                    if 0 <= idx < len(batch):
                        batch[idx]['relevance_score'] = score
                        batch[idx]['relevance_reason'] = reason
                        
                        if score >= threshold:
                            scored.append(batch[idx])
                            print(f"      ✅ [{score:.0f}/10] {batch[idx].get('title', '?')[:60]} — {reason}")
                        else:
                            print(f"      ❌ [{score:.0f}/10] {batch[idx].get('title', '?')[:60]} — FILTERED OUT")
                
            except Exception as e:
                print(f"   ⚠️ Relevance scoring failed for batch: {e}")
                # On failure, include all patents in this batch (fail-open)
                for p in batch:
                    p['relevance_score'] = -1
                    p['relevance_reason'] = 'Scoring failed'
                    scored.append(p)
        
        # Sort by relevance score descending
        scored.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        print(f"   📊 Relevance Filter: {len(scored)}/{len(patents)} patents passed (threshold: {threshold}/10)")
        return scored

    # =====================================================================
    # Iterative Keyword Refinement (v8.2)
    # =====================================================================
    def refine_keywords_from_results(self, initial_results: List[Dict], topic: str) -> dict:
        """
        Pass 2: Extracts real patent vocabulary from initial search results,
        then uses LLM to generate more precise, patent-native keywords.
        Returns a refined strategy dict with better keywords and boolean queries.
        """
        if not initial_results:
            return None
        
        # Extract vocabulary from initial results
        vocab_snippets = ""
        for i, p in enumerate(initial_results[:10]):
            title = p.get('title', '')[:200]
            abstract = p.get('abstract', '')[:300]
            patent_num = p.get('patent_number', '')
            vocab_snippets += f"\nPatent {i+1} ({patent_num}): \"{title}\"\n  Abstract snippet: {abstract}\n"
        
        prompt = (
            "You are an expert patent search strategist performing ITERATIVE REFINEMENT.\n\n"
            f"**Original Research Topic:** \"{topic[:400]}\"\n\n"
            f"**Initial Search Results (real patents found):**\n{vocab_snippets}\n\n"
            "TASK: Analyze the vocabulary used in these actual patents. Many of these patents may be IRRELEVANT. "
            "Your job is to identify the CORRECT patent terminology that would lead to MORE RELEVANT results.\n\n"
            "INSTRUCTIONS:\n"
            "1. Note which patents above are relevant and which are NOT relevant to the research topic.\n"
            "2. From the RELEVANT patents, extract the actual patent phrases and technical terms used.\n"
            "3. From the IRRELEVANT patents, identify what went wrong with the original keywords.\n"
            "4. Generate REFINED keywords and boolean queries that would find MORE relevant patents and FEWER irrelevant ones.\n"
            "5. Add EXCLUSION terms to filter out the types of irrelevant patents found.\n\n"
            "FOCUS ON: Use the exact phrasing style you see in real patent titles/abstracts. "
            "Patents use terms like 'apparatus', 'system and method', 'comprising', 'configured to'.\n\n"
            '**OUTPUT FORMAT (JSON only, no markdown):**\n'
            '{"refined_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],'
            ' "refined_boolean_queries": ["(term1 OR term2) AND (term3 OR term4)", "second query"],'
            ' "additional_exclude_terms": ["irrelevant_domain1", "irrelevant_domain2"],'
            ' "reasoning": "brief explanation of what was wrong and how you fixed it"}\n\n'
            "Output ONLY the JSON object."
        )
        
        try:
            response = patent_llm.invoke([HumanMessage(content=prompt)])
            _rc = response.content
            raw_content = (''.join(c['text'] if isinstance(c, dict) else str(c) for c in _rc) if isinstance(_rc, list) else str(_rc)).strip()
            if '</think>' in raw_content:
                content = raw_content.split('</think>')[-1].strip()
            else:
                content = raw_content
            content = content.replace("```json", "").replace("```", "").strip()
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                content = content[start:end]
            
            refined = json.loads(content)
            
            print(f"   🔄 Iterative Refinement: Keywords refined!")
            print(f"      Refined Keywords: {refined.get('refined_keywords', [])[:5]}")
            print(f"      Refined Boolean: {len(refined.get('refined_boolean_queries', []))} queries")
            if refined.get('reasoning'):
                print(f"      Reasoning: {refined['reasoning'][:120]}")
            
            return refined
        except Exception as e:
            print(f"   ⚠️ Keyword refinement failed: {e}")
            return None

    # =====================================================================
    # Tier 1 (MAIN): Google Patents BigQuery
    # =====================================================================
    def _get_bq_client(self):
        """Lazy-loads the BigQuery client."""
        if self._bq_client is not None:
            return self._bq_client

        try:
            from google.cloud import bigquery
            if self.gcp_project:
                self._bq_client = bigquery.Client(project=self.gcp_project)
            else:
                self._bq_client = bigquery.Client()
            print("✅ BigQuery client initialized.")
            return self._bq_client
        except Exception as e:
            print(f"⚠️ BigQuery client initialization failed: {e}")
            return None

    def search_google_patents(self, query: str, max_results: int = 10, strategy: Dict = None) -> List[Dict]:
        """
        MAIN SEARCH — Google Patents via BigQuery public dataset.
        v8.0: Uses concept-group AND/OR logic from search strategy.
        """
        client = self._get_bq_client()
        if client is None:
            print("⚠️ BigQuery not available. Skipping Google Patents search.")
            return []

        print(f"🔍 [MAIN] Searching Google Patents BigQuery for: {query[:80]}")

        # v10.7: Check BigQuery cache first
        cached = self._get_bq_cache(query, strategy)
        if cached is not None:
            return cached

        def _safe_word(term):
            """Sanitize a term for BigQuery LIKE. Strip quotes, wildcards, parens."""
            t = term.replace("'", "").replace('"', '').replace("\\", "")
            t = t.replace("*", "").replace("?", "").replace("(", "").replace(")", "")
            t = t.strip().lower()
            # Skip boolean operators and short words
            if t in ('and', 'or', 'not', '') or len(t) < 3:
                return None
            return t

        def _term_to_like(term):
            """Convert a single term to a SQL LIKE clause matching title or abstract."""
            return f"(LOWER(t.text) LIKE '%{term}%' OR LOWER(a.text) LIKE '%{term}%')"

        def _parse_boolean_query(bool_query):
            """
            v9.2: Parse a GPT-generated boolean query into a SQL WHERE clause.
            Input:  '(robot OR robotic) AND (projector OR projection)'
            Output: "(LIKE '%robot%' OR LIKE '%robotic%') AND (LIKE '%projector%' OR LIKE '%projection%')"
            """
            # Split by AND (case-insensitive) to get groups
            import re
            and_groups = re.split(r'\s+AND\s+', bool_query, flags=re.IGNORECASE)
            
            sql_groups = []
            for group in and_groups:
                # Split by OR to get individual terms
                or_terms = re.split(r'\s+OR\s+', group, flags=re.IGNORECASE)
                
                like_parts = []
                for raw_term in or_terms:
                    # Clean up the term
                    safe = _safe_word(raw_term)
                    if not safe:
                        continue
                    # If still multi-word after cleanup, split and use each word independently
                    words = [w for w in safe.split() if len(w) >= 3 and w not in ('and', 'or', 'not')]
                    if not words:
                        continue
                    for w in words[:2]:  # Max 2 words from each phrase
                        like_parts.append(_term_to_like(w))
                
                if like_parts:
                    # OR within group
                    sql_groups.append(f"({' OR '.join(like_parts)})")
            
            if not sql_groups:
                return None
            
            # AND between groups
            return ' AND '.join(sql_groups)

        # v9.2: Use GPT's boolean_queries DIRECTLY
        # GPT-5.2 generates well-structured queries like "(robot OR robotic) AND (projector)"
        # We parse these into SQL LIKE clauses instead of building from concept_groups
        where_clause = None
        
        # Try parsing the query parameter (which IS the boolean_query from GPT)
        # Safety: Only parse if it looks like a structured boolean query (has parentheses)
        # This prevents natural language topics like "Conduct targeted web and patent research" from being parsed
        is_boolean_query = query and '(' in query and ('OR' in query.upper() or 'AND' in query.upper())
        if is_boolean_query:
            parsed = _parse_boolean_query(query)
            if parsed:
                where_clause = parsed
                print(f"   🔗 Parsed GPT boolean query into SQL WHERE clause")
        
        # Fallback: build from concept_groups if boolean parsing failed
        if not where_clause and strategy and strategy.get('concept_groups'):
            group_clauses = []
            for group in strategy['concept_groups'][:2]:
                terms = group.get('terms', [])
                or_parts = []
                for term in terms[:3]:
                    safe = _safe_word(term)
                    if safe:
                        for w in safe.split()[:2]:
                            if len(w) >= 3:
                                or_parts.append(_term_to_like(w))
                if or_parts:
                    group_clauses.append(f"({' OR '.join(or_parts)})")
            if group_clauses:
                where_clause = ' OR '.join(group_clauses)
                print(f"   🔗 Fallback: {len(group_clauses)} concept groups (OR)")
        
        # Ultimate fallback: raw query words
        if not where_clause:
            raw_terms = [_safe_word(t) for t in query.split()[:4]]
            raw_terms = [t for t in raw_terms if t]
            if not raw_terms:
                print("⚠️ No valid search terms.")
                return []
            where_clause = ' OR '.join([_term_to_like(t) for t in raw_terms[:3]])
            print(f"   🔗 Fallback: raw terms {raw_terms[:3]}")
        
        # Domain anchor safety net (only if no AND already in where_clause)
        if strategy and strategy.get('domain_anchor_terms') and ' AND ' not in where_clause:
            anchors = []
            for anchor in strategy['domain_anchor_terms'][:2]:
                safe = _safe_word(anchor)
                if safe:
                    anchors.append(_term_to_like(safe))
            if anchors:
                anchor_clause = ' OR '.join(anchors)
                where_clause = f"({where_clause}) AND ({anchor_clause})"
                print(f"   🛡️ + domain anchors: {[_safe_word(a) for a in strategy['domain_anchor_terms'][:2]]}")

        # v8.1: CPC code filtering — DISABLED by default (too restrictive, causes 0 results).
        # CPC is only used as a secondary refinement if raw results are > 50.
        cpc_filter = ""
        cpc_codes_available = []
        if strategy and strategy.get('cpc_codes'):
            cpc_codes_available = [c.strip().lower() for c in strategy['cpc_codes'][:5] if len(c) >= 3]
            # Do NOT apply CPC filter on first search — save for post-filtering if needed
            print(f"   📋 CPC Codes (for post-filtering only): {cpc_codes_available}")
        
        # v8.0: Exclude terms filtering
        exclude_filter = ""
        if strategy and strategy.get('exclude_terms'):
            excl = [t.strip().lower() for t in strategy['exclude_terms'][:5] if len(t) >= 3]
            if excl:
                excl_parts = [f"LOWER(t.text) NOT LIKE '%{t}%'" for t in excl]
                exclude_filter = f"AND {' AND '.join(excl_parts)}"
                print(f"   🚫 Exclude: {excl}")

        sql = f"""
        WITH matched_patents AS (
            SELECT
                p.publication_number,
                t.text AS title,
                a.text AS abstract,
                p.filing_date,
                p.publication_date,
                p.country_code,
                ARRAY_TO_STRING(ARRAY(SELECT i FROM UNNEST(p.inventor) AS i LIMIT 5), ', ') AS inventors,
                ARRAY_TO_STRING(ARRAY(SELECT ass FROM UNNEST(p.assignee) AS ass LIMIT 3), ', ') AS assignees,
                -- v8.0: Scoring — prioritize granted patents, recent filings, major companies
                CASE
                    WHEN REGEXP_CONTAINS(p.publication_number, r'B[12]$') THEN 10
                    WHEN REGEXP_CONTAINS(p.publication_number, r'B$') THEN 8
                    ELSE 2
                END
                +
                CASE
                    WHEN p.filing_date >= 20200101 THEN 5
                    WHEN p.filing_date >= 20150101 THEN 3
                    WHEN p.filing_date >= 20100101 THEN 1
                    ELSE 0
                END
                +
                CASE
                    WHEN EXISTS(SELECT 1 FROM UNNEST(p.assignee) AS ass 
                        WHERE LOWER(ass) LIKE '%apple%'
                        OR LOWER(ass) LIKE '%google%' OR LOWER(ass) LIKE '%alphabet%'
                        OR LOWER(ass) LIKE '%samsung%'
                        OR LOWER(ass) LIKE '%amazon%'
                        OR LOWER(ass) LIKE '%microsoft%'
                        OR LOWER(ass) LIKE '%sony%'
                        OR LOWER(ass) LIKE '%lg elec%' OR LOWER(ass) LIKE '%lg corp%'
                        OR LOWER(ass) LIKE '%ibm%'
                        OR LOWER(ass) LIKE '%boston dynamics%'
                        OR LOWER(ass) LIKE '%softbank%'
                        OR LOWER(ass) LIKE '%irobot%'
                        OR LOWER(ass) LIKE '%panasonic%'
                        OR LOWER(ass) LIKE '%hyundai%'
                    ) THEN 3
                    ELSE 0
                END AS quality_score
            FROM `bigquery-public-data.patents.publications` AS p,
                 UNNEST(p.title_localized) AS t,
                 UNNEST(p.abstract_localized) AS a
            WHERE t.language = 'en'
              AND a.language = 'en'
              AND ({where_clause})
              {cpc_filter}
              {exclude_filter}
            LIMIT {max_results * 5}
        )
        SELECT DISTINCT publication_number, title, abstract, filing_date,
               publication_date, country_code, inventors, assignees, quality_score
        FROM matched_patents
        ORDER BY quality_score DESC
        LIMIT {max_results}
        """

        try:
            query_job = client.query(sql)
            results = []

            for row in query_job:
                results.append({
                    "patent_number": row.get("publication_number", ""),
                    "title": (row.get("title", "") or "")[:200],
                    "abstract": (row.get("abstract", "") or "")[:500],
                    "applicants": [a.strip() for a in (row.get("assignees", "") or "").split(",") if a.strip()],
                    "inventors": [i.strip() for i in (row.get("inventors", "") or "").split(",") if i.strip()],
                    "publication_date": str(row.get("publication_date", "")),
                    "country_code": row.get("country_code", ""),
                    "cpc_codes": [],
                    "source": "GooglePatents"
                })

            print(f"✅ [MAIN] Google Patents BigQuery found {len(results)} patents.")
            # v10.7: Save to cache
            self._save_bq_cache(query, results, strategy)
            return results

        except Exception as e:
            print(f"⚠️ BigQuery query failed: {e}")
            return []

    # =====================================================================
    # Tier 2 (SECONDARY): USPTO Bulk Data API
    # =====================================================================
    def search_uspto(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        SECONDARY SEARCH — USPTO Bulk Search API.
        Free, no authentication required.
        Supports Lucene query syntax.
        Endpoint: https://api.uspto.gov/api/v1/patent/applications/search
        """
        print(f"🔍 [SECONDARY] Searching USPTO for: {query}")

        url = "https://api.uspto.gov/api/v1/patent/applications/search"

        # Build Lucene query: search in inventionTitle and abstractText
        safe_query = query.replace('"', '\\"')
        lucene_query = f'applicationMetaData.inventionTitle:"{safe_query}" OR abstractText:"{safe_query}"'

        params = {
            "q": lucene_query,
            "offset": 0,
            "limit": max_results
        }

        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                time.sleep(1.0 + random.uniform(0.3, 0.8))
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    # Handle different response structures
                    patents_list = data if isinstance(data, list) else data.get("patentApplications", data.get("results", data.get("data", [])))
                    if not isinstance(patents_list, list):
                        patents_list = []

                    for patent in patents_list:
                        # Extract nested metadata fields
                        meta = patent.get("applicationMetaData", patent)

                        title = meta.get("inventionTitle", patent.get("patentTitle", "No Title"))
                        abstract = patent.get("abstractText", patent.get("abstract", ""))

                        # Extract inventors
                        inventors = []
                        for inv in patent.get("inventors", []):
                            name = f"{inv.get('firstName', '')} {inv.get('lastName', '')}".strip()
                            if name:
                                inventors.append(name)

                        # Extract applicants/assignees
                        applicants = []
                        for app in patent.get("applicants", patent.get("assignees", [])):
                            name = app.get("orgName", app.get("applicantName", ""))
                            if name:
                                applicants.append(name)

                        results.append({
                            "patent_number": meta.get("applicationNumber", meta.get("patentNumber", "")),
                            "title": (title or "")[:200],
                            "abstract": (abstract or "")[:500],
                            "applicants": applicants,
                            "inventors": inventors,
                            "publication_date": meta.get("filingDate", meta.get("publicationDate", "")),
                            "cpc_codes": [],
                            "source": "USPTO"
                        })

                    print(f"✅ [SECONDARY] USPTO found {len(results)} patents.")
                    return results

                elif response.status_code == 429:
                    wait = retry_delay * (2 ** attempt)
                    print(f"⚠️ USPTO Rate Limit (429). Retry {attempt + 1}/{max_retries} in {wait:.1f}s...")
                    time.sleep(wait)

                elif response.status_code == 404:
                    print(f"⚠️ USPTO endpoint not found. Trying fallback...")
                    return self._search_uspto_fallback(query, max_results)

                else:
                    print(f"⚠️ USPTO API Error: {response.status_code} - {response.text[:200]}")
                    return []

            except requests.exceptions.Timeout:
                print(f"⚠️ USPTO timeout. Retry {attempt + 1}/{max_retries}...")
                time.sleep(retry_delay)
            except Exception as e:
                print(f"⚠️ USPTO search failed: {e}")
                if attempt == max_retries - 1:
                    return []

        return []

    def _search_uspto_fallback(self, query: str, max_results: int = 10) -> List[Dict]:
        """Fallback: Try the PatentFileWrapper endpoint."""
        print(f"🔄 USPTO Fallback: Trying Patent File Wrapper API...")
        url = "https://api.uspto.gov/api/v1/patent/grants/search"

        safe_query = query.replace('"', '\\"')
        params = {
            "q": f'inventionTitle:"{safe_query}"',
            "offset": 0,
            "limit": max_results
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                results = []
                patents_list = data if isinstance(data, list) else data.get("patentGrants", data.get("results", []))
                if not isinstance(patents_list, list):
                    patents_list = []

                for patent in patents_list:
                    meta = patent.get("applicationMetaData", patent)
                    results.append({
                        "patent_number": meta.get("patentNumber", meta.get("applicationNumber", "")),
                        "title": (meta.get("inventionTitle", "") or "")[:200],
                        "abstract": (patent.get("abstractText", "") or "")[:500],
                        "applicants": [],
                        "inventors": [],
                        "publication_date": meta.get("grantDate", ""),
                        "cpc_codes": [],
                        "source": "USPTO-Grants"
                    })

                print(f"✅ USPTO Fallback found {len(results)} granted patents.")
                return results
            else:
                print(f"⚠️ USPTO Fallback also failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"⚠️ USPTO Fallback failed: {e}")
            return []

    # =====================================================================
    # Tier 3 (METADATA): PatentsView API
    # =====================================================================
    def search_patentsview(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        METADATA ENRICHMENT — PatentsView API for US patents.
        Free, no API key required.
        """
        print(f"🔍 [METADATA] Searching PatentsView for: {query}")

        url = "https://api.patentsview.org/patents/query"

        payload = {
            "q": {
                "_text_any": {
                    "_fields": ["patent_title", "patent_abstract"],
                    "_value": query
                }
            },
            "f": [
                "patent_number", "patent_title", "patent_abstract",
                "patent_date", "patent_type",
                "assignees.assignee_organization",
                "inventors.inventor_first_name",
                "inventors.inventor_last_name",
                "cpcs.cpc_group_id"
            ],
            "o": {"per_page": max_results}
        }

        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                time.sleep(1.0 + random.uniform(0.3, 0.8))
                response = requests.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for patent in data.get("patents", []):
                        inventors = []
                        for inv in patent.get("inventors", []):
                            first = inv.get("inventor_first_name", "")
                            last = inv.get("inventor_last_name", "")
                            if first or last:
                                inventors.append(f"{first} {last}".strip())

                        assignees = []
                        for asgn in patent.get("assignees", []):
                            org = asgn.get("assignee_organization", "")
                            if org:
                                assignees.append(org)

                        cpc_codes = []
                        for cpc in patent.get("cpcs", []):
                            code = cpc.get("cpc_group_id", "")
                            if code:
                                cpc_codes.append(code)

                        results.append({
                            "patent_number": patent.get("patent_number", ""),
                            "title": patent.get("patent_title", "No Title"),
                            "abstract": (patent.get("patent_abstract", "") or "")[:500],
                            "applicants": assignees,
                            "inventors": inventors,
                            "publication_date": patent.get("patent_date", ""),
                            "cpc_codes": cpc_codes[:5],
                            "source": "PatentsView"
                        })

                    print(f"✅ [METADATA] PatentsView found {len(results)} US patents.")
                    return results

                elif response.status_code == 429:
                    wait = retry_delay * (2 ** attempt)
                    print(f"⚠️ PatentsView Rate Limit (429). Retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait)

                else:
                    print(f"⚠️ PatentsView API Error: {response.status_code} - {response.text[:200]}")
                    return []

            except requests.exceptions.Timeout:
                print(f"⚠️ PatentsView timeout. Retry {attempt + 1}/{max_retries}...")
                time.sleep(retry_delay)
            except Exception as e:
                print(f"⚠️ PatentsView search failed: {e}")
                if attempt == max_retries - 1:
                    return []

        return []

    # =====================================================================
    # Optional: Lens Patent API (activated when LENS_API_KEY is set)
    # =====================================================================
    def search_lens(self, query: str, max_results: int = 10) -> List[Dict]:
        """Optional search via Lens Patent API. Only active if LENS_API_KEY is configured."""
        if not self.lens_api_key:
            return []

        print(f"🔍 [OPTIONAL] Searching Lens Patents for: {query}")

        url = "https://api.lens.org/patent/search"
        headers = {
            "Authorization": f"Bearer {self.lens_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"title": query}},
                        {"match": {"abstract": query}},
                        {"match": {"claims": query}}
                    ]
                }
            },
            "size": max_results,
            "sort": [{"relevance": "desc"}],
            "include": [
                "lens_id", "title", "abstract",
                "biblio.parties.applicants",
                "biblio.parties.inventors",
                "biblio.publication_reference",
                "biblio.classifications_cpc"
            ]
        }

        try:
            time.sleep(1.0 + random.uniform(0.3, 1.0))
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results = []
                for patent in data.get("data", []):
                    applicants = []
                    try:
                        for app in patent.get("biblio", {}).get("parties", {}).get("applicants", []):
                            name = app.get("extracted_name", {}).get("value", "")
                            if name:
                                applicants.append(name)
                    except (KeyError, TypeError):
                        pass

                    inventors = []
                    try:
                        for inv in patent.get("biblio", {}).get("parties", {}).get("inventors", []):
                            name = inv.get("extracted_name", {}).get("value", "")
                            if name:
                                inventors.append(name)
                    except (KeyError, TypeError):
                        pass

                    results.append({
                        "lens_id": patent.get("lens_id", ""),
                        "patent_number": patent.get("lens_id", ""),
                        "title": patent.get("title", "No Title"),
                        "abstract": (patent.get("abstract", "") or "")[:500],
                        "applicants": applicants,
                        "inventors": inventors,
                        "publication_date": patent.get("biblio", {}).get("publication_reference", {}).get("date", ""),
                        "cpc_codes": [],
                        "source": "Lens"
                    })

                print(f"✅ [OPTIONAL] Lens found {len(results)} patents.")
                return results
            elif response.status_code == 401:
                print(f"❌ Lens API auth failed. Check LENS_API_KEY.")
            else:
                print(f"⚠️ Lens API Error: {response.status_code}")
            return []

        except Exception as e:
            print(f"⚠️ Lens search failed: {e}")
            return []

    # =====================================================================
    # Google Patents Full-Text Scraping (v7.0)
    # =====================================================================
    def _get_patents_dir(self) -> str:
        """Returns (and creates) the data/patents/ directory."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        patents_dir = os.path.join(base_dir, "data", "patents")
        os.makedirs(patents_dir, exist_ok=True)
        return patents_dir

    def _normalize_patent_id(self, patent_id: str) -> str:
        """Normalizes patent ID for Google Patents URL.
        e.g., 'US-10600214-B2' -> 'US10600214B2'
        """
        return re.sub(r'[\s\-/]', '', patent_id.upper())

    def fetch_google_patents_fulltext(self, patent_id: str) -> Dict:
        """
        Scrapes full patent text from Google Patents public pages.
        Returns dict with: abstract, claims, description, title, url.
        Saves result to data/patents/{patent_id}.json.
        """
        normalized_id = self._normalize_patent_id(patent_id)
        patents_dir = self._get_patents_dir()
        cache_path = os.path.join(patents_dir, f"{normalized_id}.json")

        # Check cache first
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                if cached.get('claims') or cached.get('description'):
                    print(f"   📋 Patent {normalized_id}: Loaded from cache.")
                    return cached
            except Exception:
                pass

        url = f"https://patents.google.com/patent/{normalized_id}/en"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        result = {
            'patent_id': normalized_id,
            'url': url,
            'title': '',
            'abstract': '',
            'claims': '',
            'description': '',
            'full_text': '',
            'scraped': False
        }

        try:
            time.sleep(1.0 + random.uniform(0.5, 1.5))  # Polite delay
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                print(f"   ⚠️ Patent {normalized_id}: HTTP {response.status_code}")
                return result

            soup = BeautifulSoup(response.text, 'lxml')

            # Title
            title_el = soup.find('span', {'itemprop': 'title'}) or soup.find('meta', {'name': 'DC.title'})
            if title_el:
                result['title'] = title_el.get_text(strip=True) if hasattr(title_el, 'get_text') else title_el.get('content', '')

            # Abstract
            abstract_el = soup.find('div', class_='abstract') or soup.find('section', {'itemprop': 'abstract'})
            if abstract_el:
                result['abstract'] = abstract_el.get_text(separator=' ', strip=True)

            # Claims
            claims_el = soup.find('section', {'itemprop': 'claims'})
            if not claims_el:
                claims_el = soup.find('div', class_='claims')
            if claims_el:
                claims_text = claims_el.get_text(separator='\n', strip=True)
                result['claims'] = claims_text[:30000]  # Cap at 30k chars

            # Description
            desc_el = soup.find('section', {'itemprop': 'description'})
            if not desc_el:
                desc_el = soup.find('div', class_='description')
            if desc_el:
                desc_text = desc_el.get_text(separator='\n', strip=True)
                result['description'] = desc_text[:50000]  # Cap at 50k chars

            # Build composite full_text
            parts = []
            if result['title']:
                parts.append(f"Patent: {result['title']}")
            if result['abstract']:
                parts.append(f"Abstract:\n{result['abstract']}")
            if result['claims']:
                parts.append(f"Claims:\n{result['claims']}")
            if result['description']:
                parts.append(f"Description:\n{result['description']}")
            result['full_text'] = '\n\n'.join(parts)
            result['scraped'] = bool(result['claims'] or result['description'])

            # Save to file
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"   ⚠️ Patent save failed: {e}")

            scraped_len = len(result['full_text'])
            if result['scraped']:
                print(f"   ✅ Patent {normalized_id}: Full text scraped ({scraped_len:,} chars)")
            else:
                print(f"   ⚠️ Patent {normalized_id}: Only metadata (no claims/description found)")

            return result

        except requests.exceptions.Timeout:
            print(f"   ⚠️ Patent {normalized_id}: Timeout (Google Patents may be slow)")
            return result
        except Exception as e:
            print(f"   ⚠️ Patent {normalized_id}: Scraping failed - {e}")
            return result

    def enrich_with_fulltext(self, results: List[Dict], max_fetch: int = 5) -> List[Dict]:
        """
        Enriches search results with full text from Google Patents.
        Only fetches top `max_fetch` results to avoid rate limiting.
        """
        if not results:
            return results

        enriched_count = 0
        for patent in results[:max_fetch]:
            patent_id = patent.get('patent_number', '')
            if not patent_id:
                continue

            fulltext_data = self.fetch_google_patents_fulltext(patent_id)

            if fulltext_data.get('scraped'):
                # Upgrade abstract if we got a better one
                if fulltext_data.get('abstract') and len(fulltext_data['abstract']) > len(patent.get('abstract', '')):
                    patent['abstract'] = fulltext_data['abstract']
                # Add full text fields
                patent['claims'] = fulltext_data.get('claims', '')
                patent['description'] = fulltext_data.get('description', '')
                patent['full_text'] = fulltext_data.get('full_text', '')
                patent['has_fulltext'] = True
                enriched_count += 1
            else:
                patent['has_fulltext'] = False

        print(f"   📋 Full-Text Enrichment: {enriched_count}/{min(len(results), max_fetch)} patents enriched.")
        return results

    # =====================================================================
    # Formatting
    # =====================================================================
    def format_patent_results(self, results: List[Dict]) -> str:
        """Formats patent search results into structured markdown."""
        if not results:
            return ""

        output = ""
        for i, patent in enumerate(results, 1):
            title = patent.get("title", "No Title")
            abstract = patent.get("abstract", "")
            applicants = ", ".join(patent.get("applicants", [])) or "Unknown"
            inventors = ", ".join(patent.get("inventors", [])) or "Unknown"
            pub_date = patent.get("publication_date", "Unknown")
            source = patent.get("source", "Unknown")
            cpc = ", ".join(patent.get("cpc_codes", []))
            patent_num = patent.get("patent_number", patent.get("lens_id", ""))
            has_fulltext = patent.get("has_fulltext", False)

            output += f"### 📋 Patent {i}: {title}\n"
            output += f"- **Patent ID**: {patent_num}\n"
            output += f"- **Source**: {source}{'  ✅ Full-Text' if has_fulltext else ''}\n"
            output += f"- **Applicants**: {applicants}\n"
            output += f"- **Inventors**: {inventors}\n"
            output += f"- **Published**: {pub_date}\n"
            if cpc:
                output += f"- **CPC Classification**: {cpc}\n"
            if abstract:
                output += f"- **Abstract**: {abstract}\n"
            # Include claims summary for full-text patents
            claims = patent.get('claims', '')
            if claims:
                # Show first 3 claims
                claim_lines = [l.strip() for l in claims.split('\n') if l.strip() and l.strip()[0].isdigit()]
                top_claims = claim_lines[:3]
                if top_claims:
                    output += f"- **Key Claims**:\n"
                    for cl in top_claims:
                        output += f"  - {cl[:300]}\n"
            output += "\n"

        return output

    # =====================================================================
    # Orchestration: Combined Search
    # =====================================================================
    def search_patents(self, topic: str) -> str:
        """
        Main orchestration method.
        Tier 1: Google BigQuery (main — worldwide, 90M+)
        Tier 2: USPTO Bulk API (secondary — US applications & grants)
        Tier 3: PatentsView (metadata — US patent details)
        Optional: Lens (if API key available)
        """
        formatted, _ = self.search_patents_raw(topic)
        return formatted
    
    def _run_single_search_pass(self, strategy: Dict, max_results: int = 10) -> List[Dict]:
        """Runs one BigQuery search pass with the given strategy."""
        results = []
        keywords = strategy.get('keywords', [])
        boolean_queries = strategy.get('boolean_queries', [])
        
        # Tier 1: Google BigQuery (MAIN)
        try:
            search_queries = boolean_queries[:2] if boolean_queries else keywords[:2]
            for query in search_queries:
                bq_results = self.search_google_patents(query, max_results=max_results, strategy=strategy)
                results.extend(bq_results)
            
            # Broadened fallback if precise queries got nothing
            if not results:
                broadened = strategy.get('broadened_queries', [])
                if broadened:
                    print(f"   🔄 Precise queries returned 0 results. Trying broadened queries...")
                    for query in broadened[:2]:
                        bq_results = self.search_google_patents(query, max_results=max_results, strategy=strategy)
                        results.extend(bq_results)
                    if results:
                        print(f"   ✅ Broadened queries found {len(results)} patents!")
        except Exception as e:
            print(f"⚠️ BigQuery search failed: {e}")
        
        # Tier 2: USPTO (SECONDARY)
        for kw in keywords[:2]:
            results.extend(self.search_uspto(kw, max_results=5))
        
        # Tier 3: PatentsView (METADATA)
        for kw in keywords[:1]:
            results.extend(self.search_patentsview(kw, max_results=5))
        
        # Optional: Lens
        if self.lens_api_key:
            for kw in keywords[:1]:
                results.extend(self.search_lens(kw, max_results=5))
        
        return results

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Deduplicates patents by title similarity."""
        seen_titles = set()
        unique = []
        for r in results:
            title_key = r.get("title", "").lower().strip()[:80]
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(r)
        return unique

    def search_patents_raw(self, topic: str) -> tuple:
        """
        v9.0: Iterative Patent Search with Gemini/GPT Concept Extraction.
        
        Flow:
        1. Technology description → Gemini/GPT extracts concepts + queries
        2. BigQuery search with extracted queries
        3. LLM scores relevance of results
        4. If < min_relevant found → refine description, repeat (max 3 iterations)
        
        Returns (formatted_text, raw_results_list).
        """
        MAX_ITERATIONS = 3
        MIN_RELEVANT = 3  # minimum relevant patents to consider search successful
        RELEVANCE_THRESHOLD = 5.0  # minimum score to count as relevant
        
        print(f"🔬 Starting Patent Research (v9.0 — Iterative Concept Extraction) for: {topic[:100]}...")
        
        all_relevant = []  # accumulate relevant patents across iterations
        all_seen_titles = set()  # avoid re-processing same patents
        prev_feedback = ""
        final_strategy = None
        
        for iteration in range(MAX_ITERATIONS):
            print(f"\n{'='*60}")
            print(f"📍 ITERATION {iteration + 1}/{MAX_ITERATIONS}")
            print(f"{'='*60}")
            
            # Step 1: Generate search strategy (with feedback from previous iteration)
            strategy = self.generate_search_strategy(topic, iteration=iteration, prev_feedback=prev_feedback)
            if final_strategy is None:
                final_strategy = strategy
            
            # Step 2: Run BigQuery search
            raw_results = self._run_single_search_pass(strategy, max_results=10)
            
            # Filter out already-seen patents
            new_results = []
            for r in raw_results:
                title_key = r.get("title", "").lower().strip()[:80]
                if title_key and title_key not in all_seen_titles:
                    all_seen_titles.add(title_key)
                    new_results.append(r)
            
            print(f"📊 Iteration {iteration + 1}: {len(new_results)} new unique patents (from {len(raw_results)} raw)")
            
            if not new_results:
                print(f"⚠️ No new patents found in iteration {iteration + 1}.")
                if iteration < MAX_ITERATIONS - 1:
                    prev_feedback = (
                        "The search returned 0 results. The keywords were likely too specific or "
                        "used terminology not found in patent databases. Try broader, more fundamental "
                        "technical terms. Think about what the physical hardware components are."
                    )
                    continue
                else:
                    break
            
            # Step 3: Score relevance
            print(f"🧪 Scoring {len(new_results)} patents for relevance...")
            relevant = self.score_patent_relevance(new_results, topic, threshold=RELEVANCE_THRESHOLD)
            
            if relevant:
                all_relevant.extend(relevant)
                print(f"✅ Iteration {iteration + 1}: {len(relevant)} relevant patents found! (total: {len(all_relevant)})")
            else:
                print(f"⚠️ Iteration {iteration + 1}: 0 patents passed relevance threshold ({RELEVANCE_THRESHOLD}/10)")
            
            # Step 4: Check if we have enough relevant patents
            if len(all_relevant) >= MIN_RELEVANT:
                print(f"\n🎯 Found {len(all_relevant)} relevant patents (>= {MIN_RELEVANT}). Search complete!")
                break
            
            # Not enough relevant results — prepare feedback for next iteration
            if iteration < MAX_ITERATIONS - 1:
                irrelevant_titles = [r.get('title', '')[:80] for r in new_results if r not in relevant]
                relevant_titles = [r.get('title', '')[:80] for r in relevant] if relevant else []
                
                prev_feedback = (
                    f"Previous iteration found {len(new_results)} patents but only {len(relevant)} were relevant.\n"
                    f"Relevant patents (good examples): {relevant_titles[:3]}\n"
                    f"Irrelevant patents (wrong matches): {irrelevant_titles[:5]}\n"
                    f"The keywords matched wrong domains. Generate MORE SPECIFIC terms "
                    f"that are closer to the actual technology described."
                )
                print(f"\n🔄 Refining search strategy for iteration {iteration + 2}...")
        
        # If still not enough, lower threshold
        if not all_relevant:
            print("⚠️ No relevant patents found across all iterations. Lowering threshold to 2.0...")
            # Re-score all seen patents with lower threshold
            all_candidates = list({r.get('title', '')[:80]: r for r in raw_results}.values()) if raw_results else []
            if all_candidates:
                all_relevant = self.score_patent_relevance(all_candidates, topic, threshold=2.0)
        
        if not all_relevant:
            print("⚠️ Still no relevant patents found after all iterations.")
            return "", []
        
        # Full-Text Enrichment for relevant patents
        print(f"\n📄 Fetching full patent text for {len(all_relevant)} relevant patents...")
        all_relevant = self.enrich_with_fulltext(all_relevant, max_fetch=5)
        
        # Format output
        formatted = self.format_patent_results(all_relevant)
        keywords = final_strategy.get('keywords', []) if final_strategy else []
        strategy_info = f"**Keywords**: {', '.join(keywords)}\n"
        if final_strategy and final_strategy.get('cpc_codes'):
            strategy_info += f"**CPC Codes**: {', '.join(final_strategy['cpc_codes'][:5])}\n"
        strategy_info += f"**Iterations**: {min(iteration + 1, MAX_ITERATIONS)}\n"
        
        full_text = (
            f"## 🔬 Patent / Prior Art Analysis\n\n"
            f"**Search Topic**: {topic[:200]}\n{strategy_info}"
            f"**Relevant Results**: {len(all_relevant)} patents\n\n{formatted}"
        )
        return full_text, all_relevant
