import re
import random
import os

report_path = "/home/hgeon/gravity/LangAIAgent/backend/results/socnum/00_Project_Recursive_Master_Report.md"

with open(report_path, "r") as f:
    lines = f.readlines()

claims = []
references = {}

current_chapter = ""
for p_idx, line in enumerate(lines):
    if line.startswith("# "):
        current_chapter = line.strip()
    
    # Check for Reference section
    ref_match = re.search(r'- \[REF-(\d+)\] (.*)', line)
    if ref_match:
        ref_id = f"REF-{ref_match.group(1)}"
        references[ref_id] = ref_match.group(2)
        continue
        
    # Check for claims
    matches = re.findall(r'\[REF-\d+\]', line)
    if matches and len(line) > 50 and not line.strip().startswith("- [REF-"):
        for m in set(matches):
            claims.append({
                "chapter": current_chapter,
                "claim": line.strip(),
                "ref_id": m.replace("[", "").replace("]", ""),
                "line_num": p_idx + 1
            })

print(f"Total lines: {len(lines)}")
print(f"Total Unique References found: {len(references.keys())}")
print(f"Total Claims found: {len(claims)}")

random.seed(42) # For reproducibility
sampled_claims = random.sample(claims, min(10, len(claims)))

for i, c in enumerate(sampled_claims):
    ref_id = c['ref_id']
    paper_title = references.get(ref_id, "UNKNOWN PAPER")
    print(f"\n--- sample {i+1} ---")
    print(f"Ref ID: {ref_id}")
    print(f"Paper: {paper_title}")
    print(f"Claim: {c['claim'][:500]}...")

