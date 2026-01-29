from typing import TypedDict, Annotated, List, Dict, Optional, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Represents the internal state of the Infinite Research Agent system.
    Tracks the conversation history, research data, generated artifacts, and critique feedback.
    """
    
    # Message history for the entire graph execution
    messages: Annotated[List[BaseMessage], add_messages]
    
    # The next node to execute (Supervisor, Researcher, Archivist, Architect)
    next: str
    
    # Mission Context
    research_topic: str
    user_preferences: str
    
    # Knowledge Base
    # gathered_info: List[str] # Raw snippets
    local_knowledge: str     # Found in local files
    web_knowledge: str       # Found on the web
    shared_knowledge: str    # Synthesized summary/kb
    
    # Intermediate Artifacts
    storyboard: str          # Phase 2: Textual narrative for slides
    storyboard_critique: str # Phase 2: Critique of the storyboard
    
    # Final Artifacts
    slide_code: Dict[int, str] # Phase 3: Slide Number -> React Component Code
    current_version: int       # v1, v2, v3...
    
    # Quality Control
    quality_score: float     # 0.0 to 100.0
    critique_feedback: str   # Detailed feedback from Supervisor
    
    # State Metadata
    iteration_count: int
    loop_active: bool
