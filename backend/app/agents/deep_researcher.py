import os
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import save_artifact
from langchain_community.tools.tavily_search import TavilySearchResults
from app.agents.local_model import local_llm

# SPECIALIZED DEEP RESEARCH ENGINE (Using Llama 4 Scout for Quality)
# Web Search: Tavily | Report Writing: Llama 4 Scout (Local)
llm_deep = local_llm

# Maximum tokens per chunk (safe limit for 16k context with system prompt overhead)
MAX_CHUNK_TOKENS = 8000  # ~8k tokens per chunk, leaving room for system prompt and response

SYSTEM_PROMPT = """
You are the **Specialized Deep Investigator**.
Your goal is to gather components, facts, and technical details for the Lead Researcher.

**ROLE:**
- You are NOT the final report writer.
- You are the **Intelligence Officer** who provides raw, verified data.
- **OUTPUT**: Structured "Research Notes" that the Writer can easily integrate.

**LANGUAGE RULE:**
- **KOREAN**: Summaries and explanations in Korean.
- **SOURCE MATERIAL**: Focus on synthesizing local files and web findings into actionable data points.
- **CITATION**: Every key fact MUST have a source (e.g., [File: X], [Web: Y]).
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

Write the Consolidated Research Note in KOREAN:
"""

from langchain_core.runnables import RunnableConfig

def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for mixed content"""
    return len(text) // 4

def chunk_text(text: str, max_tokens: int) -> list:
    """Split text into chunks of approximately max_tokens size"""
    if not text:
        return []
    
    estimated_tokens = estimate_tokens(text)
    if estimated_tokens <= max_tokens:
        return [text]
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        current_tokens = estimate_tokens(current_chunk)
        
        if current_tokens + para_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def deep_researcher_node(state: AgentState, config: RunnableConfig):
    """
    Focused Investigative Node using the specialized Deep Research model.
    Implements chunked processing for large context data.
    """
    # Extract Thread ID
    thread_id = config.get("configurable", {}).get("thread_id", None)
    topic = state.get('research_topic', 'Deep Investigation')
    mode = state.get('research_mode', 'deep')
    
    current_index = state.get('current_step_index', 0)
    current_sub_idx = state.get('current_sub_step_index', 0)
    iteration = state.get('iteration_count', 0)
    
    local_context = state.get('local_knowledge', '')
    web_context = ""

    # Web Research Trigger
    if mode == "deep_web" or "web" in topic.lower() or topic.lower().startswith("dmp"):
        print(f"🌍 Performing Persistent Web Research on: {topic}")
        from app.utils.db_utils import log_web_research, init_vault
        init_vault()

        try:
            search = TavilySearchResults(max_results=8)
            
            # Truncate topic for API (long queries cause 400 errors)
            search_query = topic[:200].split('\n')[0]  # First line only, max 200 chars
            print(f"  🔎 Search query: {search_query[:80]}...")
            
            results = search.invoke(search_query)
            
            # DEBUG: Log raw results format
            print(f"  📋 Raw results type: {type(results)}")
            print(f"  📋 Raw results length: {len(results) if hasattr(results, '__len__') else 'N/A'}")
            
            # Handle error responses (Tavily returns error as string)
            if isinstance(results, str):
                if 'Error' in results or 'error' in results:
                    print(f"  ❌ Tavily API Error: {results[:200]}")
                    results = []  # Skip web search
                else:
                    # Try JSON parse
                    import json
                    try:
                        results = json.loads(results)
                    except json.JSONDecodeError:
                        print(f"  ⚠️ Unexpected string result, skipping web search")
                        results = []
            
            web_context = "\n\n**EXTERNAL WEB FINDINGS:**\n"
            
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            DATA_DIR = os.path.join(BASE_DIR, "data")
            topic_slug = topic[:30].replace(' ', '_').replace('/', '_')
            research_dir = os.path.join(DATA_DIR, "web_research", topic_slug)
            os.makedirs(research_dir, exist_ok=True)
            
            # Use current timestamp for unique filenames
            import time
            current_timestamp = int(time.time())

            for i, res in enumerate(results):
                # Debug: Log result type
                print(f"  🔍 Result {i}: type={type(res).__name__}")
                
                if isinstance(res, dict):
                    title = res.get('title', 'No Title')
                    link = res.get('url', '#')
                    snippet = res.get('content', '')
                else:
                    # Fallback if result is a string
                    title = f"Result {i+1}"
                    link = "#"
                    snippet = str(res)[:500]
                    print(f"  ⚠️ Result {i} was string, not dict!")
                
                web_context += f"- [{title}]({link}): {snippet[:300]}...\n"
                
                # Use timestamp-based unique filename
                file_name = f"web_{i}_{current_timestamp}.txt"
                file_path = os.path.join(research_dir, file_name)
                
                with open(file_path, "w") as f:
                    f.write(f"SOURCE: {link}\nTITLE: {title}\n\n{snippet}")
                
                log_web_research(topic, title, link, snippet, file_path=file_path)
            
            print(f"💾 Web Research logged to Vault and {research_dir}")
            
        except Exception as e:
            print(f"⚠️ Web Search Failed: {e}")
            web_context = "\n(Web Search Failed)"

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
    # Combine all context
    full_context = f"""
**LOCAL KNOWLEDGE BASE:**
{local_context}

**WEB FINDINGS:**
{web_context}

**PREVIOUS REPORT (Master Report):**
{master_report_content[:15000]}

**WARDEN BRIEF:**
{warden_brief}
"""
    
    total_tokens = estimate_tokens(full_context)
    print(f"🧬 ACTIVATING DEEP RESEARCH ENGINE for: {topic}")
    print(f"📊 Total context: ~{total_tokens} tokens")
    
    # Check if chunking is needed
    if total_tokens > MAX_CHUNK_TOKENS:
        print(f"🔄 Context exceeds limit ({MAX_CHUNK_TOKENS} tokens). Using chunked processing...")
        
        # Split into chunks
        chunks = chunk_text(full_context, MAX_CHUNK_TOKENS)
        print(f"📦 Split into {len(chunks)} chunks")
        
        # Process each chunk
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
        
        # Synthesize all chunk analyses
        print(f"🔗 Synthesizing {len(chunk_analyses)} chunk analyses into final report...")
        
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            chunk_analyses="\n\n".join(chunk_analyses),
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
        # Direct processing (context fits in limit)
        print(f"✅ Context within limit. Direct processing...")
        
        prompt = f"""
**STRICT TASK: PERFORM DEEP RESEARCH ON "{topic}"**

{full_context}

**INSTRUCTIONS:**
1. Analyze the context deeply.
2. Produce **STRUCTURED RESEARCH NOTES** (Not an essay).
3. Focus on **Hard Facts**, **Technical Specs**, and **Formulas**.
4. Language: **KOREAN**.
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
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_Step{current_index+1}_Sub{current_sub_idx+1}_Research_Notes_v{iteration+1}"
    save_artifact(filename, report_content, "md", thread_id=thread_id)

    return {
        "sender": "DeepResearcher",
        "web_knowledge": report_content,
        "shared_knowledge": f"--- RESEARCH NOTES (From Deep Investigator about '{topic}') ---\n{report_content}",
        "messages": [SystemMessage(content=f"Research Notes on '{topic}' generated successfully.")]
    }
