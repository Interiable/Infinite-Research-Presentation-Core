import sys
import asyncio
from app.agents.deep_researcher import deep_researcher_node

# Mock state
mock_state = {
    "research_topic": "patent UX multimodal robot",
    "research_mode": "deep",
    "critique_feedback": "Please find specific patents for multimodal interaction.",
    "current_step_index": 0,
    "current_sub_step_index": 0,
    "iteration_count": 0,
    "local_knowledge": "",
    "messages": []
}

class MockConfig:
    def get(self, key, default=None):
        if key == "configurable":
            return {"thread_id": "test_thread"}
        return default

print("Starting Deep Researcher Test...")
try:
    result = deep_researcher_node(mock_state, MockConfig())
    print("\n--- Output Variables ---")
    print(list(result.keys()))
    print("Success: Node completed without error.")
except Exception as e:
    print(f"Test Failed: {e}")
