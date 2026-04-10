import sys
import os
import glob
print("Starting script...")
thread_id = "krjgg8"
base_dir = "/home/hgeon/gravity/LangAIAgent/backend"
artifact_dir = os.path.join(base_dir, "artifacts", thread_id)
report_files = glob.glob(os.path.join(artifact_dir, "*_report_final.md"))
print(f"Found {len(report_files)} files")
