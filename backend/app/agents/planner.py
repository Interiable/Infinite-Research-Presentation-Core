
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState

# Using Flash model to avoid Quota limits
llm_planner = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", 
    temperature=0.3, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

PLANNER_SYSTEM_PROMPT = """
You are the **Lead Project Planner** for an advanced AI Agent team.
Your goal is to break down a complex user request into a **Logical, Sequential Execution Plan**.

**STRICT RULES:**
1.  **Do NOT** jump to the final output (e.g., Slides) immediately.
2.  **Step 1** must always be **Deep Research** or **Requirement Analysis**.
3.  **Step 2** must be **Architecture Definition** or **Structure Planning**.
4.  **Step 3** should be **Drafting/Content Creation**.
5.  **Step 4+** should be **Final Output Generation** (e.g., React Slides).
6.  The plan must be linear. Step N depends on Step N-1.

**OUTPUT FORMAT:**
You must output PURE JSON in the following format (No code blocks, just JSON):
{
  "steps": [
    {
      "id": "step_1",
      "title": "Deep Research: [Topic]",
      "description": "Investigate [Topic] focusing on [Details]...",
      "assigned_to": "RESEARCHER",
      "status": "pending"
    },
    {
      "id": "step_2",
      "title": "Architecture Design",
      "description": "Define the structure based on research...",
      "assigned_to": "RESEARCHER", 
      "status": "pending"
    },
    {
       "id": "step_3",
       "title": "Slide Generation",
       "description": "Create slides based on architecture...",
       "assigned_to": "ARCHITECT",
       "status": "pending"
    }
  ]
}
NOTE: 'assigned_to' must be one of: 'RESEARCHER', 'ARCHITECT'. 
(Use RESEARCHER for planning/writing text, ARCHITECT for coding/slides).
"""

def planner_node(state: AgentState):
    """
    Generates the initial project plan.
    """
    messages = state['messages']
    
    # Extract the latest human goal
    goal = "General Inquiry"
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            goal = m.content
            break
    
    print("📋 Generating Project Plan...")
    
    response = llm_planner.invoke([
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"User Goal: {goal}")
    ])
    
    # Parse JSON
    try:
        content = response.content.replace('```json', '').replace('```', '').strip()
        plan_data = json.loads(content)
        steps = plan_data.get('steps', [])
    except Exception as e:
        print(f"⚠️ Plan Parsing Failed: {e}. Fallback to default plan.")
        steps = [
            {"id": "step_1", "title": "Research", "description": "Analyze request", "assigned_to": "RESEARCHER", "status": "pending"},
            {"id": "step_2", "title": "Drafting", "description": "Draft content", "assigned_to": "RESEARCHER", "status": "pending"},
            {"id": "step_3", "title": "Finalize", "description": "Generate Output", "assigned_to": "ARCHITECT", "status": "pending"}
        ]

    # Initialize State
    return {
        "plan": steps,
        "current_step_index": 0,
        "messages": [SystemMessage(content=f"Planning Complete. Total Steps: {len(steps)}")]
    }
