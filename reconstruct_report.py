
import os
import re

# Paths
base_dir = "/home/hgeon/gravity/LangAIAgent/backend"
results_dir = os.path.join(base_dir, "results/g52edq")
artifacts_dir = os.path.join(base_dir, "artifacts/g52edq")

master_report_path = os.path.join(results_dir, "Project_Recursive_Master_Report.md")
step2_path = os.path.join(artifacts_dir, "20260209_224056_20260209_224056_step2_sub1_research_notes_v30.md")
step3_critique_path = os.path.join(artifacts_dir, "20260209_230955_step3_sub1_critique_v1.md")
step4_path = os.path.join(artifacts_dir, "20260210_000731_step4_sub1_report_v31.md")

def read_file(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return ""
    with open(path, "r") as f:
        return f.read()

# 1. Read existing Master Report (Step 1)
master_content = read_file(master_report_path)

# 2. Read Step 2
step2_content = read_file(step2_path)
step2_section = f"\n\n---\n\n## 📍 Step 2: Deep Investigation (Research Notes)\n\n{step2_content}\n"

# 3. Extract Step 3 from Critique
step3_critique = read_file(step3_critique_path)
step3_content = ""
if "## Reviewed Content" in step3_critique:
    parts = step3_critique.split("## Reviewed Content")
    raw_content = parts[1].strip()
    # It might be in a python list string format [{'type' ...}] or just text.
    # The view_file showed it starting with "Web Research:\n[{'type'..."
    # We should clean it up if closely resembling the python list structure.
    # For now, just dumping it is better than nothing, but let's try to unescape if it's that list format.
    import ast
    try:
        # Find the list part
        list_start = raw_content.find("[{'type'")
        if list_start != -1:
            list_str = raw_content[list_start:]
            # basic clean up of trailing ... if present
            if list_str.endswith("..."): 
                list_str = list_str[:-3]
                if not list_str.endswith("]"): list_str += "]"
            
            data = ast.literal_eval(list_str)
            text_content = ""
            for item in data:
                if item.get('type') == 'text':
                    text_content += item.get('text', '') + "\n"
            step3_content = text_content
        else:
            step3_content = raw_content
    except Exception as e:
        print(f"Error parsing Step 3 content: {e}")
        step3_content = raw_content # Fallback

step3_section = f"\n\n---\n\n## 📍 Step 3: Mathematical Modeling\n\n{step3_content}\n"

# 4. Read Step 4
step4_raw = read_file(step4_path)
# Step 4 also seems to contain the python list format based on my previous view_file
# Let's check. Yes, likely.
step4_content = ""
try:
    list_start = step4_raw.find("[{'type'")
    if list_start != -1:
        list_str = step4_raw[list_start:]
        # The file content I viewed ended with ...}}] so it might be valid JSON/Python
        data = ast.literal_eval(list_str)
        text_content = ""
        for item in data:
            if item.get('type') == 'text':
                text_content += item.get('text', '') + "\n"
        step4_content = text_content
    else:
        # If not in list format, just use raw
        step4_content = step4_raw
except:
    step4_content = step4_raw

step4_section = f"\n\n---\n\n## 📍 Step 4: Final Technical Report\n\n{step4_content}\n"

# 5. Combine and Write
# Check if Step 2 is already in master (to avoid double append if I run this twice)
if "## 📍 Step 2:" not in master_content:
    final_report = master_content + step2_section + step3_section + step4_section
    with open(master_report_path, "w") as f:
        f.write(final_report)
    print("Successfully reconstructed Master Report.")
else:
    print("Master Report already contains Step 2. Skipping reconstruction to avoid duplication.")
