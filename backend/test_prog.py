import glob, os, re, json
base_dir = '/home/hgeon/gravity/LangAIAgent/backend'
artifact_dir = os.path.join(base_dir, "artifacts", "f2p6ju")
plan_files = sorted(glob.glob(os.path.join(artifact_dir, "*_project_plan.md")), reverse=True)
if plan_files:
    with open(plan_files[0], 'r', encoding='utf-8') as pf:
        plan_text = pf.read()
    
    steps = re.findall(r'### \[([ x>])\] Step (\d+):', plan_text)
    sub_steps = re.findall(r'- \[([ x>])\] \*\*Step \d+\.\d+\*\*:', plan_text)
    
    total_steps = len(steps)
    if total_steps > 0:
        current_step = 0
        for mark, num in steps:
            if mark == '>':
                current_step = int(num)
                break
            elif mark == 'x':
                current_step = int(num)
        
        total_subs = len(sub_steps)
        current_sub = 0
        for i, (mark, ) in enumerate([(s[0],) for s in sub_steps]):
            if mark == '>':
                current_sub = i + 1
                break
            elif mark == 'x':
                current_sub = i + 1
        
        # Calculate percent
        if total_subs > 0:
            step_pct = (current_step - 1) / total_steps
            sub_pct = (current_sub / total_subs) / total_steps
            percent = round((step_pct + sub_pct) * 100, 1)
        else:
            percent = round(((current_step) / total_steps) * 100, 1)
        
        print(json.dumps({
            "type": "progress",
            "current_step": current_step,
            "total_steps": total_steps,
            "current_sub": current_sub,
            "total_subs": total_subs,
            "percent": min(percent, 99.9),
            "next_agent": "TEST"
        }))
