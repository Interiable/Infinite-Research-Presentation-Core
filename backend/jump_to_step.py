#!/usr/bin/env python3
"""
⏭️ Step Jump Tool
Jumps the checkpoint directly to a specific step WITHOUT deleting any artifacts.
Use this to skip already-completed steps.

Usage:
  python jump_to_step.py <thread_id> <step_number>

Examples:
  python jump_to_step.py u6ejcd 7    # Jump to Step 7 (Finalizer)
  python jump_to_step.py u6ejcd 6    # Jump to Step 6

Notes:
  - Step number is 1-indexed (Step 1, Step 2, ...)
  - NO artifacts are deleted (unlike rewind_step.py)
  - MUST be run while run_system.py is STOPPED
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="⏭️ Jump to a specific step (no artifact deletion)")
    parser.add_argument("thread_id", help="Thread ID (e.g., u6ejcd)")
    parser.add_argument("step", type=int, help="Step number to jump to (1-indexed)")
    parser.add_argument("--db", default="data/checkpoints.sqlite", help="Path to checkpoints DB")
    args = parser.parse_args()

    target_index = args.step - 1
    if target_index < 0:
        print("❌ Step number must be >= 1")
        sys.exit(1)

    print(f"⏭️ Jumping thread '{args.thread_id}' to Step {args.step} (index {target_index})...")
    print()

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

            # Apply jump (clean state for the target step)
            state["current_step_index"] = target_index
            state["current_sub_step_index"] = 0
            state["iteration_count"] = 0
            state["current_chapter_index"] = 0
            state["approved_chapters"] = []
            state["chapter_plan"] = []
            state["critique_feedback"] = ""
            state["sub_plan"] = []
            state["_finalizer_retries"] = 0  # Reset finalizer retry counter

            checkpoint["channel_values"] = state
            metadata = checkpoint_tuple.metadata or {}
            saver.put(checkpoint_tuple.config, checkpoint, metadata, {})

            # Verify
            verify = saver.get_tuple(config).checkpoint["channel_values"]
            print(f"  After:  Step {verify['current_step_index']+1}, Sub-step {verify['current_sub_step_index']}")
            print(f"  ✅ Checkpoint jumped! No artifacts deleted.")

    except Exception as e:
        print(f"❌ Jump failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print(f"✅ Done! Run 'python run_system.py' and Resume to start from Step {args.step}.")


if __name__ == "__main__":
    main()
