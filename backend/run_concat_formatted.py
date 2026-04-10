import os
import glob
import re
import json
from datetime import datetime

def save_artifact(name, content, ext="md", thread_id="krjgg8"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "/home/hgeon/gravity/LangAIAgent/backend"
    artifact_dir = os.path.join(base_dir, "artifacts", thread_id)
    os.makedirs(artifact_dir, exist_ok=True)
    fpath = os.path.join(artifact_dir, f"{timestamp}_{name}.{ext}")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return fpath
import json

thread_id = "krjgg8"
base_dir = "/home/hgeon/gravity/LangAIAgent/backend"
artifact_dir = os.path.join(base_dir, "artifacts", thread_id)
report_files = glob.glob(os.path.join(artifact_dir, "*_report_final.md"))

if not report_files:
    print("❌ No final report segments found.")
    exit()

def extract_sort_key(filepath):
    filename = os.path.basename(filepath)
    m1 = re.search(r"Step(\d+)_Sub(\d+)_", filename, re.IGNORECASE)
    if m1:
        return (int(m1.group(1)), int(m1.group(2)))
    m2 = re.search(r"step(\d+)_sub(\d+)_", filename, re.IGNORECASE)
    if m2:
        return (int(m2.group(1)), int(m2.group(2)))
    return (999, 999)

report_files.sort(key=extract_sort_key)

# 1. Extract Step Titles
step_titles = {}
master_plan_files = glob.glob(os.path.join(artifact_dir, "*_project_master_plan_raw.md"))
if master_plan_files:
    master_plan_files.sort() # Get latest
    with open(master_plan_files[-1], 'r', encoding='utf-8') as f:
        content = f.read()
        try:
            json_str = content.split("```json")[1].split("```")[0].strip()
            plan_data = json.loads(json_str)
            for step in plan_data.get("steps", []):
                step_id = str(step.get("id", "")).replace("step_", "")
                step_titles[int(step_id)] = step.get("title", f"Step {step_id}")
        except Exception as e:
            print("Failed to parse master plan json:", e)

# 2. Extract Substep Titles
substep_titles = {}
subplan_files = glob.glob(os.path.join(artifact_dir, "*_subplan.md"))
for sp_file in subplan_files:
    m = re.search(r"step(\d+)_subplan", os.path.basename(sp_file), re.IGNORECASE)
    if m:
        step_idx = int(m.group(1))
        with open(sp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            sub_matches = re.findall(r"###\s*\[.*?\]\s*Sub-Step\s*(\d+):\s*(.*)", content, re.IGNORECASE)
            for sub_match in sub_matches:
                sub_idx = int(sub_match[0])
                sub_title = sub_match[1].strip()
                substep_titles[(step_idx, sub_idx)] = sub_title

toc_lines = ["# 📑 Table of Contents\n"]
processed_contents = []
current_step = -1

for r_file in report_files:
    sort_key = extract_sort_key(r_file)
    if sort_key == (999, 999): continue
    s_idx, sub_idx = sort_key
    
    with open(r_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Clean internal tags immediately
    content = re.sub(r'\[[^\]]*(Pre-Digested Facts|Scientific Notes|GEMMA4|DEEPSEEK-R1)[^\]]*\]', '', content, flags=re.IGNORECASE)
    
    # Extract Real Titles
    step_title = step_titles.get(s_idx, f"Step {s_idx}")
    sub_title = substep_titles.get((s_idx, sub_idx), f"Sub-step {s_idx}.{sub_idx}")
    
    # If we entered a new Step, add the H1 for the step and TOC entry
    if s_idx != current_step:
        current_step = s_idx
        step_header = f"# {s_idx}. {step_title}"
        processed_contents.append(step_header)
        toc_lines.append(f"- **[{s_idx}. {step_title}](#{s_idx}-{step_title.lower().replace(' ', '-')})**")
        
    substep_header = f"## {s_idx}.{sub_idx} {sub_title}"
    
    # Ensure TOC links are properly formatted for Markdown anchors (all lowercase, spaces replaced with hyphens)
    anchor_id = f"{s_idx}{sub_idx}-{sub_title.lower().replace(' ', '-').replace(':', '')}"
    anchor_id = re.sub(r'[^a-z0-9\-]', '', anchor_id)
    toc_lines.append(f"  - [{s_idx}.{sub_idx} {sub_title}](#{anchor_id})")
    
    # Process content to fix formatting:
    # Right now, stepX_subY file has `# Step X.Y Research Report` -> Remove this!
    content = re.sub(r"^#\s*Step\s*\d+\.\d+.*?(\n|$)", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"Deep Report:", "", content, flags=re.IGNORECASE)
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if line.strip().startswith("#"):
            m = re.match(r"^(\s*)(#+)\s+(.*)", line)
            if m:
                indent = m.group(1)
                level = m.group(2)
                rest = m.group(3)
                # If chapter title (matches X.Y.Z or 'Chapter X')
                if re.match(r"^\d+\.\d+\.\d+", rest) or "Chapter " in rest:
                    new_lines.append(f"{indent}### {rest}")
                else:
                    # Shift other headers by 2 (e.g. H2 -> H4, H1 -> H3)
                    new_level_len = min(6, len(level) + 2)
                    new_lines.append(f"{indent}{'#' * new_level_len} {rest}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    chapter_content = "\n".join(new_lines).strip()
    
    # Combine
    combined_substep = f"{substep_header}\n\n{chapter_content}\n\n"
    processed_contents.append(combined_substep)

# Generate final references (like before)
all_combined = "\n\n".join(processed_contents)
all_citations = re.findall(r"(\[(?:File|Paper|Web|Patent)[\✓]?:\s*[^\]]+\])", all_combined, flags=re.IGNORECASE)
unique_citations = list(dict.fromkeys(all_citations)) # Ordered dict deduplication

if unique_citations:
    all_combined += "\n\n# Complete Project References\n\n"
    all_combined += "The following citations are referenced throughout this master report:\n\n"
    for i, cite in enumerate(unique_citations):
        all_combined += f"{i+1}. {cite}\n"

final_md = "\n".join(toc_lines) + "\n\n---\n\n" + all_combined
save_path = save_artifact("Project_Structured_Final_Report", final_md, "md", thread_id=thread_id)
print(f"✅ Saved Project_Structured_Final_Report.md at {save_path}")
