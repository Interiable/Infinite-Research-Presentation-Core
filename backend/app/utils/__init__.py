import os
import datetime

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

# --- ROBUST LLM WRAPPER ---
# --- ROBUST LLM WRAPPER (POLYGLOT) ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

class RobustGemini:
    """
    Wrapper for Google Gemini that handles Quota Exhaustion (429) AND Model Not Found (404).
    Fallback Strategy:
    1. Gemini Pro (Primary)
    2. OpenAI GPT-5.2 (Secondary - High Quality Fallback)
    3. Gemini Flash (Tertiary - Ultimate Fallback)
    """
    def __init__(self, pro_model_name="gemini-3-pro-preview", flash_model_name="gemini-3-flash-preview", temperature=0.0):
        self.pro_model_name = pro_model_name
        self.flash_model_name = flash_model_name
        self.temperature = temperature
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # 1. Primary: Gemini Pro
        self.llm_pro = ChatGoogleGenerativeAI(
            model=pro_model_name, 
            temperature=temperature, 
            google_api_key=self.google_api_key
        )
        
        # 2. Secondary: OpenAI GPT-5.2 (High Quality Fallback)
        self.llm_openai = None
        if self.openai_api_key:
            # User specified reasoning={"effort": "none"} in example
            # We pass this via model_kwargs if supported, or standard if Chat.
            # Assuming standard ChatOpenAI works for now.
            try:
                self.llm_openai = ChatOpenAI(
                    model="gpt-5.2",
                    temperature=temperature,
                    api_key=self.openai_api_key,
                    # model_kwargs={"reasoning": {"effort": "none"}} # Commented out to suppress warning
                )
            except Exception as e:
                print(f"⚠️ OpenAI Init Failed: {e}")
        
        # 3. Tertiary: Gemini Flash
        self.llm_flash = ChatGoogleGenerativeAI(
            model=flash_model_name, 
            temperature=temperature, 
            google_api_key=self.google_api_key
        )

    def invoke(self, messages):
        import time
        max_retries = 3
        base_delay = 5  # Start with 5 seconds

        for attempt in range(max_retries):
            try:
                # 1. Try Gemini Pro
                return self.llm_pro.invoke(messages)
                
            except Exception as e:
                error_str = str(e)
                
                # Handle Quota / Not Found Errors
                if "429" in error_str or "ResourceExhausted" in error_str:
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ Quota Exhausted (429). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue # Retry current model loop
                    
                elif "404" in error_str:
                    print(f"⚠️ Primary Model Not Found (404): {self.pro_model_name}")
                    # Move to fallbacks immediately for 404
                    break 
                else:
                    # Other errors (e.g., Validation), re-raise
                    raise e
        
        # --- Fallback Section (If all retries fail or 404/Quota persistent) ---
        print(f"🔄 Moving to Fallback Strategy...")
        
        # 2. Try OpenAI Fallback
        if self.llm_openai:
            print(f"🔄 Switching to Secondary Model: OpenAI GPT-5.2...")
            try:
                return self.llm_openai.invoke(messages)
            except Exception as openai_e:
                print(f"⚠️ OpenAI Fallback Failed: {openai_e}. Moving to Flash.")
        
        # 3. Try Flash Fallback
        print(f"⚡ Switching to Tertiary Model: {self.flash_model_name}...")
        try:
            return self.llm_flash.invoke(messages)
        except Exception as flash_e:
            if "429" in str(flash_e):
                print("🚨 ALL MODELS EXHAUSTED (429). System must cool down.")
                time.sleep(60) # Ultimate block
            raise flash_e

from langchain_community.tools.tavily_search import TavilySearchResults

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
        self.search = TavilySearchResults(
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
            3. Synthesize a detailed answer in **KOREAN**.
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
    Converts a Markdown file to a PDF file using markdown-pdf.
    """
    try:
        from markdown_pdf import MarkdownPdf, Section

        if not os.path.exists(markdown_path):
            print(f"❌ Markdown file not found: {markdown_path}")
            return False

        if not output_pdf_path:
            output_pdf_path = markdown_path.replace(".md", ".pdf")

        pdf = MarkdownPdf(toc_level=2)
        
        with open(markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        pdf.add_section(Section(content))
        pdf.save(output_pdf_path)
        
        print(f"✅ PDF Generated: {output_pdf_path}")
        return True
    except Exception as e:
        print(f"❌ PDF Conversion Failed: {e}")
        return False
