import os
import datetime
from typing import Any, List, Dict

def log_night_audit(node_name: str, message: str):
    """
    Appends an error or audit message to a central night_audit_log.md file.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n### [{timestamp}] {node_name}\n- {message}\n"
    
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(current_file_dir)
    backend_dir = os.path.dirname(app_dir)
    log_path = os.path.join(backend_dir, "artifacts", "night_audit_log.md")
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"📡 Night Audit Logged: {node_name}")
    except Exception as e:
        print(f"❌ Failed to log night audit: {e}")

def save_artifact(name: str, content: str, extension: str = "md", thread_id: str = None):
    """
    Saves content to the 'artifacts' directory.
    If thread_id is provided, saves into 'artifacts/{thread_id}/'.
    """
    # Base Artifacts Dir - Absolute Path Anchor
    # app/utils/__init__.py -> app/utils -> app -> backend
    current_file_dir = os.path.dirname(os.path.abspath(__file__))  # app/utils
    app_dir = os.path.dirname(current_file_dir)  # app
    backend_dir = os.path.dirname(app_dir)  # backend
    base_dir = os.path.join(backend_dir, "artifacts")
    
    # If thread_id provided, append subdirectory
    if thread_id:
        # Sanitize thread_id to be safe for filesystem
        safe_thread_id = "".join([c for c in thread_id if c.isalnum() or c in ('-', '_')])
        target_dir = os.path.join(base_dir, safe_thread_id)
    else:
        target_dir = base_dir
        
    # Create dir if not exists
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    # Timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean filename
    clean_name = name.replace(" ", "_").lower()
    
    filename = f"{timestamp}_{clean_name}.{extension}"
    filepath = os.path.join(target_dir, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Artifact saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Failed to save artifact: {e}")
        return None

def extract_text_content(ai_output: Any) -> str:
    """
    Robustly extracts string content from varied AI model responses.
    Handles:
    - Pure strings
    - LangChain AIMessage objects
    - Lists of dicts (Gemini/OpenAI structured format)
    - Dicts with 'text' or 'content' keys
    """
    if ai_output is None:
        return ""
    
    # 1. Handle Strings
    if isinstance(ai_output, str):
        return ai_output
    
    # 2. Handle LangChain Messages
    if hasattr(ai_output, "content"):
        return extract_text_content(ai_output.content)
    
    # 3. Handle Lists (Common in structured Gemini outputs)
    if isinstance(ai_output, list):
        text_parts = []
        for item in ai_output:
            text_parts.append(extract_text_content(item))
        return " ".join(text_parts).strip()
    
    # 4. Handle Dictionaries
    if isinstance(ai_output, dict):
        # Look for typical keys
        for key in ["text", "content", "message", "body"]:
            if key in ai_output:
                return extract_text_content(ai_output[key])
        return str(ai_output)
    
    return str(ai_output)

# --- ROBUST LLM WRAPPER ---
# --- ROBUST LLM WRAPPER (POLYGLOT) ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class RobustGemini:
    """
    Wrapper for Google Gemini that handles Quota Exhaustion (429) AND Model Not Found (404).
    Wrapper for Google Gemini that handles Quota Exhaustion (429) AND Model Not Found (404).
    Fallback Strategy:
    1. Gemini 3.1 Pro (Primary)
    2. Gemini 3 Pro (1st Backup - Equivalent Quality)
    3. OpenAI GPT-5.2 (2nd Backup - High Quality Fallback)
    4. Gemini Flash (Ultimate Fallback)
    """
    def __init__(self, pro_model_name=None, flash_model_name=None, temperature=0.0):
        # Read model names from env vars (set in .env), fall back to sensible defaults
        self.pro_model_name   = pro_model_name   or os.getenv("GEMINI_PRO_MODEL",         "gemini-2.5-pro")
        self.flash_model_name = flash_model_name or os.getenv("GEMINI_FLASH_MODEL",       "gemini-2.5-flash")
        self.pro_backup_name  =                     os.getenv("GEMINI_PRO_BACKUP_MODEL",  "gemini-2.5-pro-preview-06-05")
        self.openai_model     =                     os.getenv("OPENAI_MODEL",             "gpt-4o")
        self.temperature = temperature
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        # 1. Primary: Gemini Pro
        self.llm_pro = ChatGoogleGenerativeAI(
            model=self.pro_model_name,
            temperature=temperature,
            google_api_key=self.google_api_key,
            timeout=300,
            max_retries=2
        )

        # 2. 1st Backup: Gemini Pro (alternate quota/version)
        self.llm_pro_backup = ChatGoogleGenerativeAI(
            model=self.pro_backup_name,
            temperature=temperature,
            google_api_key=self.google_api_key,
            timeout=300,
            max_retries=2
        )

        # 3. 2nd Backup: OpenAI (if key provided)
        self.llm_openai = None
        if self.openai_api_key:
            try:
                self.llm_openai = ChatOpenAI(
                    model=self.openai_model,
                    temperature=temperature,
                    api_key=self.openai_api_key,
                    timeout=300,
                    max_retries=2
                )
            except Exception as e:
                print(f"⚠️ OpenAI Init Failed: {e}")

        # 4. Ultimate Backup: Gemini Flash
        self.llm_flash = ChatGoogleGenerativeAI(
            model=self.flash_model_name,
            temperature=temperature,
            google_api_key=self.google_api_key,
            timeout=300,
            max_retries=2
        )

    def invoke(self, messages):
        import time
        max_retries = 2 # Reduced retries per model to move faster through tiers
        base_delay = 3

        # --- Tier 1: Gemini 3.1 Pro ---
        for attempt in range(max_retries):
            try:
                return self.llm_pro.invoke(messages)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "ResourceExhausted" in error_str:
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ Tier 1 (3.1 Pro) Quota Exhausted. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                break # Move to next tier for 404 or persistent 429
        
        # --- Tier 2: Gemini 3 Pro (1st Backup) ---
        print(f"🔄 Moving to Tier 2: Gemini 3 Pro...")
        for attempt in range(max_retries):
            try:
                return self.llm_pro_backup.invoke(messages)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "ResourceExhausted" in error_str:
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ Tier 2 (3 Pro) Quota Exhausted. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                break

        # --- Tier 3: OpenAI GPT-5.2 (2nd Backup) ---
        if self.llm_openai:
            print(f"🔄 Moving to Tier 3: OpenAI GPT-5.2...")
            try:
                return self.llm_openai.invoke(messages)
            except Exception as openai_e:
                print(f"⚠️ Tier 3 (OpenAI) Failed: {openai_e}")
        
        # --- Tier 4: Gemini Flash (Ultimate) ---
        print(f"⚡ Moving to Tier 4: {self.flash_model_name}...")
        try:
            return self.llm_flash.invoke(messages)
        except Exception as flash_e:
            if "429" in str(flash_e):
                print("🚨 ALL MODELS EXHAUSTED (429).")
                time.sleep(30)
            raise flash_e

from langchain_tavily import TavilySearch

class DeepResearcher:
    """
    Dedicated class for the Google Deep Research specialized model.
    Actively searches the web using Tavily API (Optimized for LLMs) to provide grounded answers.
    """
    def __init__(self, temperature=0.2):
        # Using the centralized local model for web research synthesis
        from app.agents.local_model import local_llm
        self.llm = local_llm
        
        # Tavily Search Tool (Requires TAVILY_API_KEY in .env)
        self.search = TavilySearch(
            max_results=5,
            search_depth="advanced", # Deep search mode
            include_answer=True,
            include_raw_content=True # Get more content for better context
        )

    def invoke(self, messages):
        print("🔍 🧬 ACTIVATING DEEP RESEARCH MODEL (Tavily Investigative Mode)...")
        
        # Extract the query from the last message
        query = messages[-1].content if isinstance(messages, list) else str(messages)
        
        # 1. Perform Web Search
        try:
            print(f"🌍 Searching Web (Tavily) for: {query[:50]}...")
            search_results = self.search.invoke(query)
            
            # Tavily returns a list of dicts with 'url', 'content', 'score'
            # We formats this for the LLM
            search_context = ""
            if isinstance(search_results, list):
                for res in search_results:
                    url = res.get('url', 'No URL')
                    content = res.get('content', 'No content')
                    search_context += f"\n--- SOURCE: {url} ---\n{content}\n"
            else:
                search_context = str(search_results)

            # PROMPT for the LLM to Synthesize
            research_prompt = f"""
            You are a **Deep Research Analyst**.
            
            **USER QUERY:** {query}
            
            **WEB SEARCH RESULTS (Tavily High-Quality Data):**
            {search_context[:50000]}
            
            **INSTRUCTION:**
            1. Analyze the search results deeply.
            2. Extract key facts, statistics, and academic findings.
            3. Synthesize a detailed answer in **ENGLISH**.
            4. **CITE SOURCES**: Use the URLs provided.
            
            **CRITICAL: COLLABORATIVE RETRIEVAL MODE**
            - 만약 검색 결과 중에 **수식(Formula)**이나 **아키텍처(Architecture)**가 포함된 매우 중요한 논문/문서가 있지만, 현재 스니펫 정보만으로는 내용이 불충분하다고 판단된다면:
            - 답변 마지막에 **"🚨 추가 정보 필요 (사용자 협업)"** 섹션을 만드세요.
            - 해당 문서의 **URL**을 명시하고, "이 문서의 전문을 다운로드하여 로컬 연구 디렉토리에 넣어주시면 정밀 분석이 가능합니다"라고 사용자에게 요청하세요.
            """
            
            return self.llm.invoke([HumanMessage(content=research_prompt)])
            
        except Exception as e:
            print(f"⚠️ Tavily Web Search Failed: {e}. Falling back to DuckDuckGo/Internal.")
            from langchain_community.tools import DuckDuckGoSearchRun
            fallback_search = DuckDuckGoSearchRun()
            try:
                fallback_res = fallback_search.invoke(query)
                return self.llm.invoke([HumanMessage(content=f"Query: {query}\nResults: {fallback_res}")])
            except Exception as e2:
                return self.llm.invoke([HumanMessage(content=f"Search failed completely. Answer based on internal knowledge: {query}")])


# PDF Conversion Utility
def convert_to_pdf(markdown_path: str, output_pdf_path: str = None):
    """
    Converts a Markdown file to a PDF file using playwright and custom CSS.
    """
    import os
    import asyncio
    import markdown
    from playwright.async_api import async_playwright

    if not os.path.exists(markdown_path):
        print(f"❌ Markdown file not found: {markdown_path}")
        return False

    if not output_pdf_path:
        output_pdf_path = markdown_path.replace(".md", ".pdf")

    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Pre-process LaTeX math into styled HTML (works offline, no CDN needed)
        import re as _re_math
        # Display math: $$...$$ → centered, styled block
        text = _re_math.sub(
            r'\$\$(.+?)\$\$',
            r'<div class="math-display">\1</div>',
            text, flags=_re_math.DOTALL
        )
        # Inline math: $...$ → italic styled span (avoid matching $$ or currency)
        text = _re_math.sub(
            r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)',
            r'<span class="math-inline">\1</span>',
            text
        )

        html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])

        html_doc = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ background-color: transparent !important; }}
body {{ font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; padding: 40px; font-size: 14px; line-height: 1.7; color: #222222; background-color: #ffffff !important; }}
h1 {{ color: #111111; border-bottom: 2px solid #cccccc; padding-bottom: 0.3em; margin-bottom: 16px; margin-top: 32px; }}
h2 {{ color: #1a1a1a; border-bottom: 1px solid #dddddd; padding-bottom: 0.3em; margin-top: 28px; margin-bottom: 16px; }}
h3 {{ color: #333333; margin-top: 24px; margin-bottom: 12px; }}
h4, h5, h6 {{ color: #444444; }}
p, li {{ color: #222222; }}
pre {{ background-color: #f7f7f7 !important; padding: 16px; border-radius: 6px; border: 1px solid #e0e0e0; overflow: auto; white-space: pre-wrap; word-wrap: break-word; }}
code {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; background-color: #f0f0f0 !important; color: #333333; padding: 0.15em 0.35em; border-radius: 4px; font-size: 85%; white-space: pre-wrap; word-wrap: break-word; }}
pre code {{ background-color: transparent !important; padding: 0; white-space: pre-wrap; word-wrap: break-word; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 15px; margin-bottom: 15px; table-layout: fixed; word-wrap: break-word; font-size: 11px; background-color: #ffffff !important; }}
th, td {{ border: 1px solid #cccccc; padding: 8px; word-break: keep-all; word-wrap: break-word; overflow-wrap: break-word; color: #222222; background-color: #ffffff !important; }}
th {{ background-color: #f5f5f5 !important; font-weight: 600; color: #111111; }}
tr:nth-child(2n) {{ background-color: #fafafa !important; }}
blockquote {{ padding: 0 1em; color: #555555; border-left: .25em solid #cccccc; background-color: transparent !important; }}
strong {{ color: #111111; }}
.math-display {{ text-align: center; margin: 1em 0; padding: 12px; background-color: #f8f8f8 !important; border-radius: 6px; border: 1px solid #e8e8e8; font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif; font-size: 16px; font-style: italic; color: #111111; }}
.math-inline {{ font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif; font-style: italic; color: #111111; font-size: 105%; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""

        temp_html = markdown_path.replace(".md", "_temp.html")
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(html_doc)

        async def generate_pdf():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                file_url = f"file://{os.path.abspath(temp_html)}"
                await page.goto(file_url, wait_until="networkidle")
                await page.pdf(
                    path=output_pdf_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
                )
                await browser.close()

        # Check if an event loop is already running
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(generate_pdf())
        else:
            asyncio.run(generate_pdf())

        if os.path.exists(temp_html):
            os.remove(temp_html)

        print(f"✅ PDF Generated via Playwright: {output_pdf_path}")
        return True
    
    except Exception as e:
        print(f"❌ PDF Conversion Failed: {e}")
        return False
