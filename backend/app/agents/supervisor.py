import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END

from app.core.state import AgentState
from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT, CONTENT_CRITIQUE_PROMPT, DESIGN_CRITIQUE_PROMPT
from app.utils import RobustGemini

# --- TIERED MODEL STRATEGY ---
# 1. Pro Model (Robust): Checks Quota, Falls back to Flash
llm_pro = RobustGemini(
    pro_model_name="gemini-2.0-pro-exp-02-05", 
    flash_model_name="gemini-2.0-flash-exp",
    temperature=0.2
)

# 2. Flash Model: For repetitive tasks or simple routing
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

def supervisor_node(state: AgentState):
    """
    The Supervisor determines the next step based on the current state.
    It acts as the Router and the Judge.
    Uses Pro model for Critiques to ensure high quality planning.
    """
    # --- PLAN-DRIVEN SUPERVISOR LOGIC ---
    
    # 0. Check if Plan exists
    plan = state.get('plan', [])
    current_index = state.get('current_step_index', 0)
    
    # If no plan, route to Planner
    if not plan:
        return {"next": "PLANNER"}
        
    # 1. Check if all steps completed
    if current_index >= len(plan):
        return {
            "next": "END",
            "messages": [SystemMessage(content="모든 계획이 완료되었습니다.")]
        }
        
    # 2. Get Current Step
    current_step = plan[current_index]
    step_id = current_step['id']
    assigned_to = current_step['assigned_to']
    
    # 3. Artifact Update: Save current plan status to file (for user visibility)
    # We mark current as 'in_progress' conceptually for the UI, or just 'active'
    from app.utils import save_artifact
    
    plan_text = "# 📋 Project Execution Plan\n\n"
    for idx, step in enumerate(plan):
        mark = "[ ]"
        if idx < current_index: mark = "[x]"
        elif idx == current_index: mark = "[>]" # Current
        
        plan_text += f"### {mark} Step {idx+1}: {step['title']}\n"
        plan_text += f"- **Goal**: {step['description']}\n"
        plan_text += f"- **Agent**: {step['assigned_to']}\n\n"
        
    save_artifact("project_plan", plan_text, "md")
    
    # 4. Routing Logic
    # If we are just starting this step (status was pending), we route to worker.
    # The worker will return to Supervisor. When they return, we assume completion of that hop.
    # But wait, LangGraph loop returns to Supervisor after Worker.
    # So we need to know if the Worker JUST finished or if we need to send them.
    
    # We can detect this by checking who sent the last message.
    last_msg = messages[-1]
    sender = "system"
    if hasattr(last_msg, 'name'): sender = last_msg.name
    # Or simply context.
    
    # SIMPLIFICATION:
    # If the last node was the assigned worker, we mark done and move next.
    # If not (e.g. Supervisor or Planner just ran), we send to worker.
    
    last_node = state.get("next", "")
    
    if last_node == assigned_to:
        # Worker finished. Mark complete and increment.
        # Update specific PlanStep status if we want (optional for MVP)
        return {
            "next": "SUPERVISOR", # Return to self to evaluate next step
            "current_step_index": current_index + 1,
            "messages": [SystemMessage(content=f"Step {current_index+1} 완료. 다음 단계로 이동합니다.")]
        }
    else:
        # We need to execute this step.
        # Inject Topic/Context for the worker based on the Step Description
        return {
            "next": assigned_to,
            "research_topic": current_step['description'], # Override topic with specific step goal
            "messages": [SystemMessage(content=f"Step {current_index+1} 시작: {current_step['title']}")]
        }


