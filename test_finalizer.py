import os
import sys

# Add backend to path so imports work (insert at 0 to prioritize over site-packages)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
sys.path.insert(0, backend_dir)

from app.agents.finalizer import finalizer_node

# A dummy state with enough info to trigger the fallback logic using existing reports
thread_id = "9zsvx"
state = {
    "research_topic": "Test Topic"
}
config = {
    "configurable": {"thread_id": thread_id}
}

print(f"Testing finalizer for thread {thread_id}...")
result = finalizer_node(state, config)
print("\nFinalizer Result:", result['next'])
