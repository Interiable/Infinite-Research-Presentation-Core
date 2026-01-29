import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END

from app.core.state import AgentState
from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT, CONTENT_CRITIQUE_PROMPT, DESIGN_CRITIQUE_PROMPT

# Initialize Gemini 3 Pro (using the preview identifier if available, or falling back to a supported string)
# Note: In a real scenario, this string would be 'gemini-3.0-pro-preview' or similar. 
# We'll use a placeholder that assumes the environment variable handles the mapping or we use the latest supported.
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro", # Updating to "gemini-3.0-pro" when API officially supports string
    temperature=0.2, # Low temp for precise routing/critique
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

def supervisor_node(state: AgentState):
    """
    The Supervisor determines the next step based on the current state.
    It acts as the Router and the Judge.
    """
    messages = state['messages']
    current_step = state.get('next', 'PLANNING')
    storyboard = state.get('storyboard', '')
    slide_code = state.get('slide_code', {})
    
    # 1. Routing Logic based on Phase
    # This is a simplified heuristic logic for the "Steve Jobs" decision tree. 
    # In a full implementation, we'd use function calling or structured output to determine the 'next' field dynamically.
    
    # If we are just starting or have new user input
    if not state.get('next'):
        return {"next": "RESEARCHER", "messages": [SystemMessage(content="연구 단계를 시작합니다.")]}
    
    # helper to get time
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Content Critique Gate (Phase 2 -> 3)
    # If the researcher/archivist has finished and we have a draft storyboard, we critique it.
    if current_step == "STORYBOARD_REVIEW":
        critique_response = llm.invoke([
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT.format(current_time=now_str)),
            HumanMessage(content=CONTENT_CRITIQUE_PROMPT.format(topic=state.get('research_topic', 'Unknown')))
        ])
        
        # Simple string parsing for this scaffold - in prod use Structured Output
        if "APPROVE" in critique_response.content.upper():
            return {
                "next": "ARCHITECT", 
                "storyboard_critique": critique_response.content,
                "messages": [SystemMessage(content="스토리보드가 승인되었습니다. 디자인 작업을 시작합니다.")]
            }
        else:
            # Send back for more research or re-synthesis
            return {
                "next": "RESEARCHER", 
                "storyboard_critique": critique_response.content,
                "messages": [SystemMessage(content=f"스토리보드 반려됨: {critique_response.content}")]
            }

    # 3. Design Critique Gate (Phase 3 -> 4 -> Loop)
    if current_step == "DESIGN_REVIEW":
        critique_response = llm.invoke([
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT.format(current_time=now_str)),
            HumanMessage(content=DESIGN_CRITIQUE_PROMPT.format(version=state.get('current_version', 1)))
        ])
        
        if "APPROVE" in critique_response.content.upper():
            return {
                "next": "END", # Or wait for user
                "critique_feedback": critique_response.content,
                "messages": [SystemMessage(content="디자인 승인 완료. 버전이 저장되었습니다.")]
            }
        else:
            return {
                "next": "ARCHITECT", # Redo design
                "critique_feedback": critique_response.content,
                "messages": [SystemMessage(content=f"디자인 반려됨: {critique_response.content}")]
            }

    # Default Fallback for now
    return {"next": "RESEARCHER"}

