import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import RobustGemini, save_artifact, log_night_audit

# Plan Refiner uses the Pro model for deep deliberation.
llm = RobustGemini(
    temperature=0.1
)

def plan_refiner_node(state: AgentState, config=None):
    """
    Takes the current step from the main plan and breaks it down into a highly detailed sub-plan.
    This ensures the Researcher/Architect has clear, manageable granular tasks.
    """
    try:
        thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"
        
        plan = state.get('plan', [])
        current_index = state.get('current_step_index', 0)
        
        if current_index >= len(plan):
            return {"next": "SUPERVISOR"}
            
        main_step = plan[current_index]
        original_goal = state.get('messages', [])[0].content if state.get('messages') else "No goal"
        
        print(f"🧠 Plan Refiner: Deliberating on Sub-Plan for Step {current_index+1}: {main_step['title']}...")
        
        # v11.0: Extract previous knowledge to avoid amnesic breakdowns
        previous_knowledge = state.get('shared_knowledge', '') or state.get('web_knowledge', '')
        local_knowledge = state.get('local_knowledge', '')
        
        prompt = f"""
        You are the **Lead Strategic Planner**.
        Your goal is to take a high-level research/development step and break it down into **3-5 extremely granular sub-steps**.
        
        **Master Goal:**
        "{original_goal[:2000]}"
        
        **AGGREGATED KNOWLEDGE BASE (CRITICAL TRUTH):**
        [LOCAL DB & FILES]:
        {local_knowledge[:5000] if local_knowledge else "No local files/DB data."}
        
        [NEW RESEARCH FINDINGS]:
        {previous_knowledge[:8000] if previous_knowledge else "No new research findings accumulated yet."}
        
        **Current High-Level Step:**
        Title: {main_step['title']}
        Target Goal: {main_step['description']}
        Assigned Agent: {main_step['assigned_to']}
        
        **Your Mission:**
        1.  **Analyze** the Target Goal against the Aggregated Knowledge Base to see what exact variables/data still need to be found or analyzed.
        2.  **Deliberate** on the logical sequence.
        3.  **Break down** into sub-steps. Each sub-step should be a single, focused task.
        4.  **Enforce Quality**: If this is a research step, ensure sub-steps include "Verification" and "Specific Variable Extraction".
        
        **CRITICAL RULES:**
        - **NO SLIDES IN SUB-STEPS**: Sub-steps should ONLY be research, analysis, or writing tasks.
        - **NO 'ARCHITECT' ASSIGNMENT**: All sub-steps must be assigned to the same agent as the main step ('{main_step['assigned_to']}').
        - Sub-steps are intermediate work, NOT final deliverables.
        
        **Output Format (STRICT JSON ONLY):**
        ```json
        [
          {{
            "id": "sub_1",
            "title": "Sub-task title",
            "description": "Exhaustive details on what to do. Include specific formulas/variables to look for if research.",
            "assigned_to": "{main_step['assigned_to']}"
          }},
          ...
        ]
        ```
        
        **CRITICAL**: Do NOT use markdown code blocks (```) inside the JSON strings. It breaks parsing.
        Output in **ENGLISH** for titles/descriptions.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        
        # --- v3.9 Gemini 3 Flash List Content Fix ---
        if isinstance(content, list):
            print(f"📦 Detected List Content in Refiner. Parsing...")
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            content = " ".join(parsed_parts)

        # Parse JSON
        sub_plan = []
        try:
            import re
            match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                match = re.search(r"(\[.*\])", content, re.DOTALL)
                json_str = match.group(1) if match else "[]"
                
            sub_plan = json.loads(json_str)
        except Exception as e:
            print(f"⚠️ Plan Refiner failed to parse sub-plan: {e}")
            # Fallback sub-plan
            sub_plan = [{
                "id": "sub_1",
                "title": main_step['title'],
                "description": main_step['description'],
                "assigned_to": main_step['assigned_to']
            }]
            
        # Save sub-plan artifact for user visibility
        sub_plan_text = f"# 🔍 Sub-Plan for Step {current_index+1}\n\n"
        sub_plan_text += f"> **Main Goal**: {main_step['description']}\n\n"
        for i, s in enumerate(sub_plan):
            sub_plan_text += f"### [ ] Sub-Step {i+1}: {s['title']}\n"
            sub_plan_text += f"- {s['description']}\n\n"
            
        save_artifact(f"Step{current_index+1}_SubPlan", sub_plan_text, "md", thread_id=thread_id)
        
        return {
            "sub_plan": sub_plan,
            "current_sub_step_index": 0,
            "next": "SUPERVISOR", 
            "sender": "Plan Refiner",
            "messages": [SystemMessage(content=f"Step {current_index+1}를 {len(sub_plan)}개의 세부 계획으로 세분화했습니다.")]
        }

    except Exception as e:
        print(f"⚠️ Plan Refiner Node Critical Failure: {e}")
        log_night_audit("PlanRefiner", f"Critical Failure: {str(e)}")
        # Return fallback sub-plan
        fallback_sub = [{
            "id": "sub_1",
            "title": "Emergency Breakdown",
            "description": "Critical failure in plan refiner. Proceeding with emergency breakdown.",
            "assigned_to": main_step['assigned_to']
        }]
        return {
            "sub_plan": fallback_sub,
            "current_sub_step_index": 0,
            "next": "SUPERVISOR",
            "sender": "Plan Refiner",
            "messages": [SystemMessage(content=f"Plan Refiner Failed: {e}. Emergency fallback.")]
        }
