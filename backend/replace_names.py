import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Replacements
    # 1. Update the ChatOllama initialization block in researcher.py exactly
    old_init = """# --- v3.11 DEEPSEEK-R1 INTEGRATION ---
from langchain_ollama import ChatOllama

# Initialize DeepSeek-R1 for Math/Logic/Engineering tasks
try:
    local_deepseek = ChatOllama(
        model="deepseek-r1:32b",
        temperature=0.6,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        timeout=300
    )
    print("✅ DeepSeek-R1 Strategy Engine Initialized.")
except Exception as e:
    print(f"⚠️ Failed to initialize DeepSeek-R1: {e}. Fallback to Qwen3.")
    local_deepseek = local_llm"""

    new_init = """# --- v5.0 GEMMA 4 INTEGRATION ---
# Initialize Gemma 4 for Math/Logic/Engineering tasks
try:
    local_deepseek = local_llm # Unified integration
    print("✅ Gemma-4 Strategy Engine Initialized.")
except Exception as e:
    print(f"⚠️ Failed to initialize Gemma-4: {e}. Fallback to local_llm.")
    local_deepseek = local_llm"""

    content = content.replace(old_init, new_init)

    # 2. General string replacements in texts/prints
    content = content.replace("DeepSeek-R1", "Gemma-4-31B")
    content = content.replace("DeepSeek (Science)", "Gemma4 (Science)")
    content = content.replace("Activating DeepSeek", "Activating Gemma4")
    content = content.replace("Force DeepSeek", "Force Gemma4")
    content = content.replace("DeepSeek gets", "Gemma4 gets")
    
    # 3. Regex tags and strippers
    # Add GEMMA4 to stripping regex
    content = re.sub(r'Scientific Notes\|DEEPSEEK-R1', r'Scientific Notes|GEMMA4|DEEPSEEK-R1', content)
    # Fix explicit internal tags string rules in Prompts (adding GEMMA4)
    content = content.replace("`[DEEPSEEK-R1]`", "`[GEMMA4]`, `[DEEPSEEK-R1]`")
    
    # Update dictionary assignment where needed via variables
    content = content.replace("local_deepseek", "local_deepseek") # keep variable name same for safety

    with open(filepath, 'w') as f:
        f.write(content)
        
    print(f"Processed: {filepath}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_files = [
        os.path.join(base_dir, 'app', 'agents', 'researcher.py'),
        os.path.join(base_dir, 'app', 'agents', 'supervisor.py'),
        os.path.join(base_dir, 'app', 'agents', 'finalizer.py'),
        os.path.join(base_dir, 'run_concat.py'),
        os.path.join(base_dir, 'run_concat_formatted.py')
    ]
    
    for fpath in target_files:
        if os.path.exists(fpath):
            process_file(fpath)
            
if __name__ == "__main__":
    main()
