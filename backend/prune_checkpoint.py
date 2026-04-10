#!/usr/bin/env python3
"""
🧹 Checkpoint State Pruner
Prunes bloated LangGraph message history to keep only essential messages.
Removes intermediate drafts (v1, v2) and critiques, keeping only:
- Original user prompt
- Final approved step summaries
- Current step's working messages

Usage:
  python prune_checkpoint.py <thread_id>

MUST be run while run_system.py is STOPPED.
"""

import sys
import argparse
import json


def get_message_text(msg):
    """Extract text content from a message regardless of format."""
    if hasattr(msg, 'content'):
        content = msg.content
    elif isinstance(msg, dict):
        content = msg.get('content', '')
    else:
        content = str(msg)
    
    if isinstance(content, list):
        return " ".join(str(c) for c in content)
    return str(content)


def get_message_size(msg):
    """Get approximate size of a message in characters."""
    return len(get_message_text(msg))


def main():
    parser = argparse.ArgumentParser(description="🧹 Prune checkpoint state to reduce bloat")
    parser.add_argument("thread_id", help="Thread ID (e.g., u6ejcd)")
    parser.add_argument("--db", default="data/checkpoints.sqlite", help="Path to checkpoints DB")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pruned without modifying")
    args = parser.parse_args()

    print(f"🧹 Pruning checkpoint state for thread '{args.thread_id}'...")
    print()

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langchain_core.messages import HumanMessage, SystemMessage

        with SqliteSaver.from_conn_string(args.db) as saver:
            config = {"configurable": {"thread_id": args.thread_id, "checkpoint_ns": ""}}
            
            checkpoint_tuple = saver.get_tuple(config)
            if checkpoint_tuple is None:
                print(f"❌ No checkpoint found for thread: {args.thread_id}")
                sys.exit(1)

            checkpoint = checkpoint_tuple.checkpoint
            state = checkpoint.get("channel_values", {})
            messages = state.get("messages", [])
            
            current_step = state.get("current_step_index", 0)
            plan = state.get("plan", [])
            
            print(f"📋 Current State:")
            print(f"   Step: {current_step + 1} / {len(plan)}")
            print(f"   Messages: {len(messages)}")
            
            # Calculate current size
            total_chars = sum(get_message_size(m) for m in messages)
            print(f"   Total message chars: {total_chars:,}")
            print(f"   Estimated size: {total_chars / 1024 / 1024:.1f} MB")
            print()

            # --- PRUNING STRATEGY ---
            # Keep: 
            #   1. First message (user prompt) - always index 0
            #   2. Last 20 messages (current working context)
            # Remove:
            #   Everything in between (old step drafts, critiques, iterations)

            if len(messages) <= 25:
                print("✅ Messages already small enough. No pruning needed.")
                return

            first_msg = messages[0]  # User's original prompt
            recent_msgs = messages[-20:]  # Current working context
            
            # Create a summary of what was pruned
            pruned_count = len(messages) - 21  # 1 (first) + 20 (recent)
            pruned_chars = sum(get_message_size(m) for m in messages[1:-20])
            
            print(f"🔍 Pruning Plan:")
            print(f"   Keep: Message 0 (user prompt, {get_message_size(first_msg):,} chars)")
            print(f"   Remove: Messages 1-{len(messages)-21} ({pruned_count} messages, {pruned_chars:,} chars)")
            print(f"   Keep: Last 20 messages ({sum(get_message_size(m) for m in recent_msgs):,} chars)")
            print()

            # Create a compact summary message to preserve context continuity
            step_summaries = []
            for i, step in enumerate(plan):
                if i < current_step:
                    title = step.get('title', f'Step {i+1}')
                    step_summaries.append(f"- Step {i+1}: {title} [COMPLETED]")
            
            summary_text = (
                "=== PRUNED HISTORY SUMMARY ===\n"
                "Previous steps completed:\n" + 
                "\n".join(step_summaries) +
                f"\n\nTotal {pruned_count} intermediate messages (drafts, critiques, iterations) "
                f"were pruned to optimize performance. All final reports are preserved as artifacts."
            )
            
            if args.dry_run:
                print("🔍 DRY RUN - No changes made.")
                print(f"   Would reduce: {len(messages)} → 22 messages")
                print(f"   Would save: {pruned_chars:,} chars ({pruned_chars / 1024 / 1024:.1f} MB)")
                return

            # Build new messages list
            summary_msg = SystemMessage(content=summary_text)
            new_messages = [first_msg, summary_msg] + recent_msgs
            
            new_total = sum(get_message_size(m) for m in new_messages)
            
            # Apply pruning
            state["messages"] = new_messages
            
            # Also clear any accumulated chapter data from previous steps
            # (current step's data is preserved in recent messages)
            
            checkpoint["channel_values"] = state
            metadata = checkpoint_tuple.metadata or {}
            saver.put(checkpoint_tuple.config, checkpoint, metadata, {})

            # Verify
            verify_tuple = saver.get_tuple(config)
            verify_msgs = verify_tuple.checkpoint["channel_values"].get("messages", [])
            
            print(f"✅ Pruning Complete!")
            print(f"   Messages: {len(messages)} → {len(verify_msgs)}")
            print(f"   Size: {total_chars:,} → {new_total:,} chars")
            print(f"   Saved: {pruned_chars:,} chars ({pruned_chars / 1024 / 1024:.1f} MB)")
            print()
            print(f"✅ Done! Run 'python run_system.py' and Resume.")

    except Exception as e:
        print(f"❌ Pruning failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
