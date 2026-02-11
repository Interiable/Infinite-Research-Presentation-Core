
import re
import os

report_path = "/home/hgeon/gravity/LangAIAgent/backend/results/g52edq/Project_Recursive_Master_Report.md"

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

content = read_file(report_path)

# Strategy:
# 1. Identify Main Step Headers (e.g., "## 📍 Step 1...", "## 📍 Step 2...")
# 2. Demote existing headers inside the steps so they don't conflict with the main structure?
#    Actually, the report structure is:
#    # Title
#    ## Step 1
#    (Content starts with ## 1.1 ...) -> This is H2, same level as Step 1. This is the problem.
#
#    Actual content inside includes 'python list strings' (artifacts) which are noise. We should clean those too if possible? 
#    The user just mentioned indexing.
#
#    Let's enforce:
#    H1: # Project Recursive Master Report
#    H2: ## Step X: Title
#    H3: ### 1.1 Title (The inner content should be demoted by one level effectively, or just kept as H3)
    
lines = content.split('\n')
new_lines = []
current_step = 0

# Helper to remove the python artifacts strings if they exist as separate lines
# They look like "[{'type': 'text', ...}]"
# But be careful not to remove code blocks.
# The artifacts I pasted had them.

ignore_block = False

for line in lines:
    stripped = line.strip()
    
    # 1. Remove the artifact raw dumps
    if stripped.startswith("[{'type': 'text'") and stripped.endswith("}}]"):
        continue
    if stripped.startswith("[{'type': 'text'") and stripped.endswith("..."):
        continue
        
    # 2. Remove "Deep Report:", "Web Research:" markers that I added or were there?
    if stripped in ["Deep Report:", "Web Research:"]:
        continue
        
    # 3. Identify Step Headers
    # Current format: ## 📍 Step 1.1: ... or ## 📍 Step 2: ...
    step_match = re.match(r"^## 📍 Step (\d+)(\.\d+)?: (.*)", line)
    if step_match:
        step_num = step_match.group(1)
        title = step_match.group(3)
        current_step = int(step_num)
        new_lines.append(f"\n## Step {step_num}: {title}")
        continue
        
    # 4. Handle Inner Headers
    # If we are in a step, we want to make sure the inner headers are H3 or below, OR clearly distinguished.
    # Step 1 content has "## 1.1 ...". This matches the H2 level of "Step 1". It should be H3.
    # Step 2 content has "## 1. 핵심 발견". This resets to 1. Should be "### 2.1 핵심 발견"? 
    # Or just "### 1. 핵심 발견" (H3) is fine, as long as it's visually under H2.
    
    header_match = re.match(r"^(#+) (.*)", line)
    if header_match:
        level = len(header_match.group(1))
        text = header_match.group(2)
        
        # If it is H1 (#), change to H2 (##) if it's not the main title
        if level == 1 and not text.startswith("🧬 Recursive Research"):
             new_lines.append(f"## {text}")
             continue
             
        # If it is H2 (##) and NOT a Step header (already handled), demote to H3 (###)
        if level == 2 and not text.startswith("📍 Step"):
            new_lines.append(f"### {text}")
            continue
            
        # If H3 (###), demote to H4 (####) ?
        # Step 2 has "### Dynamic Movement...". If we make "## 1. 핵심" -> "### 1. 핵심", then "### Dynamic" becomes H3 too.
        # Maybe demote all by 1 level inside steps?
        if level >= 3:
            # new_lines.append("#" + line) # Demote
            new_lines.append(line) # Keep as is for now?
            continue
            
    # Default
    new_lines.append(line)

# Clean up multiple empty lines
final_content = "\n".join(new_lines)
final_content = re.sub(r'\n{3,}', '\n\n', final_content)

write_file(report_path, final_content)
print("Reformatted report structure.")
