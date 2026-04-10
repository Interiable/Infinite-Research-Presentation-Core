"""
Step 7 Finalizer for u6ejcd research.
Runs the Finalizer agent to compile Steps 1-6 report_final files into a master report.
"""
from app.agents.finalizer import finalizer_node
from langchain_core.messages import HumanMessage

class Config:
    def get(self, key, default=None):
        if key == "configurable":
            return {"thread_id": "u6ejcd"}
        return default

# The original user request (used by Finalizer to determine extraction style)
original_goal = """3가지 로봇에 대한 구체적이고 논리 정연한 UX적 가치가 있는 Capability Map을 설계해야해.
Compile all drafted Capability Maps into a comprehensive, highly structured final report.
The final output MUST prominently feature the Markdown Tables at the top or in highly visible sections.
Synthesize the findings to provide sharp UX insights, highlighting the key differentiators of each robot
and identifying the highest-priority UX values for the upcoming Experience Framework design."""

state = {
    "research_topic": "Physical AI UX Capability Mapping for 3 Robot Form Factors",
    "messages": [HumanMessage(content=original_goal)],
    "shared_knowledge": "",
    "critique_feedback": "",
    "_finalizer_retries": 0,
}

print("=" * 60)
print("🎓 Running Finalizer (Step 7) for u6ejcd")
print("=" * 60)
result = finalizer_node(state, Config())
print("\n" + "=" * 60)
print(f"✅ Finalizer Result: next={result.get('next', 'N/A')}")
print(f"   Sender: {result.get('sender', 'N/A')}")
print(f"   Deliverable length: {len(result.get('shared_knowledge', ''))} chars")
print("=" * 60)
