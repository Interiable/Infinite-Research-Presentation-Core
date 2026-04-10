#!/usr/bin/env python3
"""
🔄 Checkpoint Rewind Tool
Rewinds a LangGraph research thread to a specific step, cleaning artifacts.

Usage:
  python rewind_step.py <thread_id> <step_number>

Examples:
  python rewind_step.py krjgg8 3       # Rewind to Step 3 (Sub-step 0)
  python rewind_step.py krjgg8 1       # Rewind to Step 1
  python rewind_step.py krjgg8 3 --keep-artifacts   # Rewind without deleting files

Notes:
  - Step number is 1-indexed (Step 1, Step 2, Step 3...)
  - Internally converted to 0-indexed for the checkpoint
  - Clears sub_plan, chapter_plan, approved_chapters for a clean restart
  - Deletes matching step artifacts unless --keep-artifacts is specified
  - MUST be run while run_system.py is STOPPED
"""

import sys
import os
import glob
import argparse

def main():
    parser = argparse.ArgumentParser(description="🔄 Rewind LangGraph checkpoint to a specific step")
    parser.add_argument("thread_id", help="Thread ID (e.g., krjgg8)")
    parser.add_argument("step", type=int, help="Step number to rewind to (1-indexed, e.g., 3 for Step 3)")
    parser.add_argument("--keep-artifacts", action="store_true", help="Don't delete old artifacts for this step")
    parser.add_argument("--db", default="data/checkpoints.sqlite", help="Path to checkpoints DB")
    args = parser.parse_args()

    target_index = args.step - 1  # Convert to 0-indexed
    if target_index < 0:
        print("❌ Step number must be >= 1")
        sys.exit(1)

    print(f"🔄 Rewinding thread '{args.thread_id}' to Step {args.step} (index {target_index})...")
    print()

    # --- 1. Rewind Checkpoint ---
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        with SqliteSaver.from_conn_string(args.db) as saver:
            config = {"configurable": {"thread_id": args.thread_id, "checkpoint_ns": ""}}
            
            checkpoint_tuple = saver.get_tuple(config)
            if checkpoint_tuple is None:
                print(f"❌ No checkpoint found for thread: {args.thread_id}")
                sys.exit(1)

            checkpoint = checkpoint_tuple.checkpoint
            state = checkpoint.get("channel_values", {})
            plan = state.get("plan", [])

            old_step = state.get("current_step_index", 0)
            old_sub = state.get("current_sub_step_index", 0)

            print(f"📋 Plan ({len(plan)} steps):")
            for i, step in enumerate(plan):
                marker = "👉" if i == old_step else "  "
                title = step.get('title', '?')[:60]
                agent = step.get('assigned_to', '?')
                print(f"  {marker} Step {i+1}: {title} [{agent}]")

            print()
            print(f"  Before: Step {old_step+1}, Sub-step {old_sub}")

            if target_index >= len(plan):
                print(f"❌ Step {args.step} doesn't exist (plan has {len(plan)} steps)")
                sys.exit(1)

            # Apply rewind
            state["current_step_index"] = target_index
            state["current_sub_step_index"] = 0
            state["iteration_count"] = 0
            state["current_chapter_index"] = 0
            state["approved_chapters"] = []
            state["chapter_plan"] = []
            state["critique_feedback"] = ""
            state["sub_plan"] = []

            checkpoint["channel_values"] = state
            metadata = checkpoint_tuple.metadata or {}
            saver.put(checkpoint_tuple.config, checkpoint, metadata, {})

            # Verify
            verify = saver.get_tuple(config).checkpoint["channel_values"]
            print(f"  After:  Step {verify['current_step_index']+1}, Sub-step {verify['current_sub_step_index']}")
            print(f"  ✅ Checkpoint rewound!")

    except Exception as e:
        print(f"❌ Checkpoint rewind failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- 2. Clean Artifacts ---
    if not args.keep_artifacts:
        artifacts_dir = os.path.join("artifacts", args.thread_id)
        if os.path.exists(artifacts_dir):
            # Delete artifacts for this step and all later steps
            deleted = 0
            for step_num in range(args.step, len(plan) + 1):
                pattern = os.path.join(artifacts_dir, f"*step{step_num}*")
                matches = glob.glob(pattern)
                for f in matches:
                    os.remove(f)
                    deleted += 1
            print(f"  🗑️  Deleted {deleted} artifact files (Step {args.step}+)")
        else:
            print(f"  📁 No artifacts directory found at: {artifacts_dir}")
    else:
        print(f"  📁 Keeping existing artifacts (--keep-artifacts)")

    print()
    print(f"✅ Done! Run 'python run_system.py' and Resume to start from Step {args.step}.")


if __name__ == "__main__":
    main()
