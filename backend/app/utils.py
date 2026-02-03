import os
import datetime

def save_artifact(name: str, content: str, extension: str = "md"):
    """
    Saves content to the 'artifacts' directory with a timestamp.
    """
    # Create artifacts dir if not exists
    base_dir = os.path.join(os.getcwd(), "artifacts")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    # Timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean filename
    clean_name = name.replace(" ", "_").lower()
    
    filename = f"{timestamp}_{clean_name}.{extension}"
    filepath = os.path.join(base_dir, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Artifact saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Failed to save artifact: {e}")
        return None

# --- ROBUST LLM WRAPPER ---
from langchain_google_genai import ChatGoogleGenerativeAI

class RobustGemini:
    """
    Wrapper for Google Gemini that handles Quota Exhaustion (429)
    by falling back to a Flash model.
    """
    def __init__(self, pro_model_name="gemini-2.0-pro-exp-02-05", flash_model_name="gemini-2.0-flash-exp", temperature=0.0):
        self.pro_model_name = pro_model_name
        self.flash_model_name = flash_model_name
        self.temperature = temperature
        self.api_key = os.getenv("GOOGLE_API_KEY")
        
        # Initialize Models
        self.llm_pro = ChatGoogleGenerativeAI(model=pro_model_name, temperature=temperature, google_api_key=self.api_key)
        self.llm_flash = ChatGoogleGenerativeAI(model=flash_model_name, temperature=temperature, google_api_key=self.api_key)

    def invoke(self, messages):
        try:
            # Try Pro Model
            # print(f"Trying Primary Model: {self.pro_model_name}...")
            return self.llm_pro.invoke(messages)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "ResourceExhausted" in error_str:
                print(f"⚠️ Quota Exceeded ({self.pro_model_name}). Fallback to {self.flash_model_name}.")
                return self.llm_flash.invoke(messages)
            else:
                # Other errors, re-raise
                raise e

