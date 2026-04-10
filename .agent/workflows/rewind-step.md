---
description: how to rewind a research thread to a specific step
---
// turbo-all

# Rewind Research Thread

Use this workflow when you need to restart a research thread from a specific step (e.g., after fixing bugs, or when a step failed mid-execution).

## Prerequisites
- `run_system.py` must be **STOPPED** before rewinding
- Kill any stale processes: `pkill -f "run_system.py"; pkill -f "uvicorn"`

## Steps

1. Navigate to the backend directory
```bash
cd /home/hgeon/gravity/LangAIAgent/backend
```

2. Run the rewind script with the thread ID and step number
```bash
python rewind_step.py <thread_id> <step_number>
```

### Examples
```bash
# Rewind krjgg8 to Step 3 (deletes Step 3+ artifacts)
python rewind_step.py krjgg8 3

# Rewind without deleting artifacts
python rewind_step.py krjgg8 3 --keep-artifacts

# Rewind to Step 1 (full restart, keeps Plan)
python rewind_step.py krjgg8 1
```

3. Start the system
```bash
python run_system.py
```

4. Open Mission Control at http://localhost:5174, select the thread, and click **Resume**

## What gets reset
- `current_step_index` → target step (0-indexed internally)
- `current_sub_step_index` → 0
- `sub_plan` → cleared (regenerated on resume)
- `chapter_plan` → cleared
- `approved_chapters` → cleared
- `iteration_count` → 0
- Artifacts for the target step and later → deleted (unless `--keep-artifacts`)

## What is preserved
- The master Plan (all 7 steps)
- All artifacts from earlier steps
- The Recursive Master Report (results/ folder)
- ChromaDB patent/paper libraries
