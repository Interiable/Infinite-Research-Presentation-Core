import os
import datetime

def save_artifact(name: str, content: str, extension: str = "md", thread_id: str = None):
    """
    Saves content to the 'artifacts' directory.
    If thread_id is provided, saves into 'artifacts/{thread_id}/'.
    """
    # Base Artifacts Dir - Absolute Path Anchor
    # app/utils.py -> app -> backend
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(os.path.dirname(current_file_dir), "artifacts")
    
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
        try:
            # 1. Try Gemini Pro
            return self.llm_pro.invoke(messages)
            
        except Exception as e:
            error_str = str(e)
            
            # Handle Quota / Not Found Errors
            if "429" in error_str or "ResourceExhausted" in error_str or "404" in error_str:
                print(f"⚠️ Primary Model Error ({self.pro_model_name}): {error_str.split('}')[0]}...")
                
                # 2. Try OpenAI Fallback
                if self.llm_openai:
                    print(f"🔄 Switching to Secondary Model: OpenAI GPT-5.2...")
                    try:
                        return self.llm_openai.invoke(messages)
                    except Exception as openai_e:
                        print(f"⚠️ OpenAI Fallback Failed: {openai_e}. Moving to Flash.")
                
                # 3. Try Flash Fallback
                print(f"⚡ Switching to Tertiary Model: {self.flash_model_name}...")
                return self.llm_flash.invoke(messages)
                
            else:
                # Other errors (e.g., Validation), re-raise
                raise e

class DeepResearcher:
    """
    Dedicated class for the Google Deep Research specialized model.
    Used ONLY when specific investigative research is required.
    """
    def __init__(self, temperature=0.2):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-pro-preview",
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

    def invoke(self, messages):
        print("🔍 🧬 ACTIVATING DEEP RESEARCH MODEL (Investigative Mode)...")
        # Note: This model may support specific tools/search in the future if enabled via API.
        return self.llm.invoke(messages)

