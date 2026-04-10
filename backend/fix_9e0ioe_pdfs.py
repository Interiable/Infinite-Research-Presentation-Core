import re
import os
import sys

# Add backend directory to sys path so we can import from app.utils
backend_dir = "/home/hgeon/gravity/LangAIAgent/backend"
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from app.utils import convert_to_pdf

files_to_fix = [
    "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9e0ioe/20260403_041417_project_master_report_en.md",
    "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9e0ioe/20260403_045650_project_master_report_ko.md"
]

for fpath in files_to_fix:
    if os.path.exists(fpath):
        print(f"Fixing {os.path.basename(fpath)}...")
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Apply the regex fix for markdown tables missing a preceding blank line
        fixed_content = re.sub(r'([^\n|])\n(\s*\|)', r'\1\n\n\2', content)
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(fixed_content)
            
        print("Re-converting to PDF...")
        try:
            convert_to_pdf(fpath)
            print(f"✅ Successfully converted {os.path.basename(fpath)} to PDF!")
        except Exception as e:
            print(f"❌ PDF Conversion failed for {fpath}: {e}")
    else:
        print(f"⚠️ File not found: {fpath}")

print("Done fixing current run's PDFs.")
