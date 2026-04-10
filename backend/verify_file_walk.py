
import os
from dotenv import load_dotenv

load_dotenv()

research_dir = os.getenv("LOCAL_RESEARCH_DIR")
print(f"Research Dir: {research_dir}")

available_files = []
if research_dir and os.path.exists(research_dir):
    for root, dirs, files in os.walk(research_dir):
        # Emulate filtering
        dirs[:] = [d for d in dirs if d not in ['node_modules', 'venv', 'dist', 'build', '__pycache__', '.git', '.idea', '.vscode']]
        
        for f in files:
            if f.endswith(('.py', '.js', '.ts', '.tsx', '.md', '.json', '.html', '.css', '.pdf', '.txt', '.docx')):
                rel_path = os.path.relpath(os.path.join(root, f), research_dir)
                available_files.append(rel_path)

# Check for specific file
target_file = "Research/Physical AI UX Design principle.txt"
found = False
for f in available_files:
    if "Physical AI UX Design principle.txt" in f:
        print(f"✅ FOUND: {f}")
        found = True

if not found:
    print("❌ NOT FOUND in available_files list.")
    # Print some files to check what IS found
    print(f"Total files found: {len(available_files)}")
    print(f"First 10 files: {available_files[:10]}")
