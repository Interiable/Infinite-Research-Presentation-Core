import sys
import os
from pprint import pprint
from dotenv import load_dotenv

# Load environment variables (for GOOGLE_API_KEY)
load_dotenv()

# Add backend directory to sys.path
# Assuming this script is in backend/tests/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.architect import architect_node
from app.core.state import AgentState

# Mock State
state = AgentState(
    storyboard="""
    # Slide 1: The Evolution of Search
    - Traditional Search: Keyword matching, 10 blue links, surface level.
    - Deep Research: Autonomous agents, multi-step reasoning, synthesis of thousands of sources.
    - The Shift: From "Finding" to "Understanding".
    - Visual Metaphor: An iceberg. Traditional search is the tip. Deep research is the massive structure below.
    """,
    current_version=2,
    critique_feedback="",
    slide_code={},
    messages=[],
    next="",
    research_topic="",
    user_preferences="",
    local_knowledge="",
    web_knowledge="",
    shared_knowledge="",
    storyboard_critique="",
    quality_score=0.0,
    iteration_count=0,
    loop_active=False
)

print("🚀 Triggering Architect Agent...")
result = architect_node(state)
print("✅ Architect Agent Finished.")
print("Generated Code:")
print(result['slide_code'].get(1, "No code generated"))
