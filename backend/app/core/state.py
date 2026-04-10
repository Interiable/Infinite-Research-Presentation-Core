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
    research_mode: Optional[str] # 'deep' or 'refine'
    search_options: Dict[str, Any] # search flags from UI
    project_id: str # 'default', 'robotics', etc.
    
    # Structured Planning
    plan: List[Dict[str, Any]] # List of PlanSteps
    current_step_index: int    # Pointer to current step
    
    # Hierarchical Planning (Recursive)
    sub_plan: List[Dict[str, Any]] # Breaking down the current step
    current_sub_step_index: int
    
    # Persistent Results (v3.4 Recursive Synthesis)
    incremental_report_path: str # Path to the growing master report in 'results' folder
    
    # Collaborative Retrieval (v3.5)
    collaboration_start_time: Optional[float] # Timestamp when first requested
    
    # Strict Step Context Hand-over
    last_completed_step_path: str # Path to the previously completed step report

    # v5.4 Chapter-Level Review (Per-Chapter Write → Review → Approve)
    current_chapter_index: int                  # Pointer to current chapter within sub-step
    approved_chapters: List[str]                # List of approved chapter texts (locked)
    chapter_plan: List[Dict[str, Any]]          # Cached TOC (chapter titles + file refs)
    cached_master_fact_sheet: str               # Cached compressed facts for current sub-step

    # v6.3 Optimization Flags
    rag_ready: bool                             # True after Archivist ingests; Planner skips re-ingest
    gemma_fail_count: int                        # Consecutive Gemma Pre-Critique failures; circuit breaker at 3

    # v10.7 Topic-Aware Critique
    _topic_type_cache: Dict[str, str]           # Cache of chapter topic classifications (key: "s{step}_ss{sub}_ch{idx}", value: "DATA_DRIVEN" or "CONCEPTUAL")
    _consecutive_same_critique: int             # Counter for same-critique detection

    # v6.6 Finalizer Safety
    _finalizer_retries: int                     # Retry counter to prevent infinite Finalizer loops

    # v13.0 Reference-First Writing (RFW)
    verified_reference_registry: List[Dict[str, Any]]  # Pre-built registry of verified citable sources
    deep_research_sources: List[Dict[str, Any]]        # Source metadata from Deep Researcher for registry inclusion
