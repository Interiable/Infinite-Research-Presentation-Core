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
    temperature=0.2
)

# 2. Flash Model: For repetitive tasks or simple routing
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

from langchain_core.runnables import RunnableConfig

def supervisor_node(state: AgentState, config: RunnableConfig):
    """
    The Supervisor determines the next step based on the current state.
    It acts as the Router and the Judge.
    Uses Pro model for Critiques to ensure high quality planning.
    """
    # Extract Thread ID for Artifact Isolation
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    
    # --- PLAN-DRIVEN SUPERVISOR LOGIC ---
    
    # 0. Check if Plan exists
    plan = state.get('plan', [])
    messages = state.get('messages', [])
    current_index = state.get('current_step_index', 0)
    
    # If no plan, route to Planner
    if not plan:
        return {"next": "PLANNER"}
        
    # --- CRITICAL FIX: Detect New User Input ---
    # If the user sends a new message, we must RE-PLAN (or update plan).
    # We shouldn't blindly follow the stale plan from the previous turn.
    if messages and isinstance(messages[-1], HumanMessage):
        print("👤 New User Input Detected -> Routing to PLANNER")
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
        
    save_artifact("project_plan", plan_text, "md", thread_id=thread_id)
    
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
        # Worker finished. Now we CRITIQUE their work product before moving on.
        print(f"🕵️ Supervisor Critiquing Substantive Work of {assigned_to}...")
        
        # --- CRITICAL FIX: Extract actual Work Product instead of status message ---
        if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
            last_output = state.get('shared_knowledge', 'No consolidated research found.')
        elif assigned_to == "ARCHITECT":
            # Extract first slide code if available to see quality
            codes = state.get('slide_code', {})
            last_output = codes.get(1, codes.get(list(codes.keys())[0], "No code found")) if codes else "No code found"
        else:
            last_output = messages[-1].content if messages else "No output"
        
        critique_filename = f"critique_step{current_index+1}_{int(os.path.getmtime(os.getcwd()))}"
        
        critique_prompt = f"""
        You are the **Chief Editor & Lead Engineer** (Strict Supervisor).
        Your persona is **Steve Jobs**: You are obsessed with detail, quality, and "insanely great" results.
        
        **Your Mission:** Mercilessly evaluate the subordinate's work. **DO NOT COMPROMISE.**
        
        **Original User Goal (THE NORTH STAR - MUST ALIGN):**
        "{messages[0].content[:8000]}"
        
        **Current Step Target:** {current_step['description']}
        **Subordinate Agent:** {assigned_to}
        
        **THE WORK PRODUCT TO EVALUATE:**
        {last_output[:40000]} 
        
        **STRICT EVALUATION CRITERIA:**
        1.  **Alignment (절대적 부합)**: 원본 프롬프트(North Star)의 의도에서 단 1%라도 벗어났는가?
        2.  **Depth (심층성)**: 내용이 뻔한가? 공식, 구체적 수치, 복잡한 로직, 혹은 실질적인 코드 구조가 포함되어 있는가?
        3.  **Specific Detail (구체성)**: 로컬 파일의 내용을 구체적으로 인용했는가? 단순 요약은 'REJECT' 대상임.
        4.  **Polish (완성도)**: 보고서 형식이 논리적이고 풍부한가? 코드가 에러 없이 최신 트렌드를 반영하는가?
        5.  **Scope Guard (Strict)**: The work must match the '**Current Step Target**' EXACTLY. If it covers future steps (e.g., Implementation during Analysis), **REJECT** immediately. Do not praise 'bonus' work.
        
        **DECISION RULES:**
        - "좋은 내용이다" 정도면 **REJECT**. 반드시 "압도적으로 훌륭함(Insanely Great)"을 충족해야 함.
        - 만약 에이전트가 본인의 상태 메시지(예: "Research complete...")만 보내고 실제 보고서 내용을 포함하지 않았다면 무조건 **REJECT**.
        
        **Output Format:**
        - Approval: "APPROVED: [Brief praise in **KOREAN**]"
        - Rejection: "REJECTED: [Numbered list of specific items to fix in **KOREAN**. Be brutal and extremely detailed.]"
        - Insufficient Data: "INSUFFICIENT_DATA: [Explain exactly what external information is missing.]"
        """
        
        # --- GRADUATED INTERVENTION (Safety Valve) ---
        step_iterations = state.get("iteration_count", 0)
        
        # Level 2: Hard Intervention (Force Approve) -> 30+ attempts
        if step_iterations >= 30:
            print(f"🚨 Final Force Approval (Attempt {step_iterations}). Supervisor taking CONTROL.")
            
            intervention_prompt = f"""
            **FINAL INTERVENTION MODE**
            The subordinate has failed 30 times. This is a critical deadlock.
            You must **REWRITE AND FINALIZE** the work now.
            
            **Original Goal:** {messages[0].content[:5000]}
            **Current Draft:** {last_output[:20000]}
            
            **TASK:**
            - Produce the FINAL version of this asset.
            - It must be "Good Enough" to proceed.
            - Output ONLY the fixed content.
            """
            
            try:
                fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                fixed_content = fix_response.content
                
                print("✅ Supervisor Forced Approval (30+). Moving Next.")
                
                updates = {
                    "next": "SUPERVISOR",
                    "current_step_index": current_index + 1,
                    "critique_feedback": "",
                    "messages": [SystemMessage(content=f"Step {current_index+1} Force-Approved by Supervisor (Threshold 30).\n\nAPPROVED.")]
                }
                if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                    updates["shared_knowledge"] = str(fixed_content)
                elif assigned_to == "ARCHITECT":
                    updates["slide_code"] = {1: str(fixed_content)} 
                return updates
            except Exception as e:
                print(f"⚠️ Hard Intervention Failed: {e}. Force skipping.")
                return {"next": "SUPERVISOR", "current_step_index": current_index + 1}

        # Level 1: Soft Intervention (Rewrite & Delegate) -> 10 or 20 attempts
        elif step_iterations in [10, 20]:
            print(f"⚠️ Supervisor Soft Intervention (Attempt {step_iterations}). Rewriting and Delegating.")
            
            intervention_prompt = f"""
            **COACHING INTERVENTION MODE**
            The subordinate is struggling (Attempt {step_iterations}).
            You, the Mentor, will **REWRITE THE DRAFT** to show them how it's done.
            
            **Original Goal:** {messages[0].content[:5000]}
            **Current Draft:** {last_output[:20000]}
            
            **TASK:**
            - Rewrite the content to correct major flaws.
            - Provide a solid high-quality base.
            - Output ONLY the fixed content.
            """
             
            try:
                fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                fixed_content = fix_response.content
                
                print(f"⚠️ Supervisor Sent Fixed Draft back to {assigned_to}.")
                
                updates = {
                    "next": assigned_to,
                    # We pass the fixed content as specific feedback or state update
                    "critique_feedback": f"I have rewritten your draft. Use THIS as your new baseline:\n\n{fixed_content[:500]}...",
                    "messages": [HumanMessage(content=f"🚨 **SUPERVISOR INTERVENTION** 🚨\n\nI have fixed the major issues. Review the updated draft in the context and FINALIZE it.\n\n(Draft Updated internally)")]
                }
                
                if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                    updates["shared_knowledge"] = str(fixed_content)
                elif assigned_to == "ARCHITECT":
                    updates["slide_code"] = {1: str(fixed_content)} 
                return updates

            except Exception as e:
                print(f"⚠️ Soft Intervention Failed: {e}. Continuing critique.")

        # Regular Critique Path
        # Fix: Gemini API requires 'contents' (User Message). SystemMessage alone maps to system_instruction.
        # We send the prompt as a HumanMessage to ensure it's treated as input content.
        response = llm_pro.invoke([HumanMessage(content=critique_prompt)])
        
        # Handle List Content (OpenAI/Gemini Fallback)
        content = response.content
        if isinstance(content, list):
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            content = " ".join(parsed_parts)
            
        review_result = str(content).strip()
        
        # Save Critique Artifact
        from app.utils import save_artifact
        save_artifact(critique_filename, f"# 🕵️ Supervisor Critique\n\n**Verdict**: {review_result}\n\n## Reviewed Content\n{last_output[:2000]}...", "md", thread_id=thread_id)
        
        if review_result.startswith("APPROVED"):
            print("✅ Step Approved. Moving to Next.")
            
            # --- DYNAMIC PLAN REFINEMENT (AGILE) ---
            # Check if future plan needs adjustment based on this result
            remaining_steps = plan[current_index+1:]
            if remaining_steps:
                print("🔄 Agile Supervisor: Running Plan Sanity Check...")
                refine_prompt = f"""
                You are the Project Strategist.
                **Original User Goal:** {messages[0].content[:2000]}
                **Just Completed Step:** {current_step['title']}
                **Outcome Summary:** {last_output[:2000]}
                
                **Remaining Steps in Plan:**
                {json.dumps(remaining_steps, indent=2)}
                
                **Instruction:**
                - Review the Remaining Steps.
                - Do they need to change given the new outcome? (e.g. Findings changed the path)
                - If YES, output the UPDATED JSON List of steps.
                - If NO, output "NO CHANGE".
                """
                
                try:
                    refine_res = llm_pro.invoke([HumanMessage(content=refine_prompt)])
                    refine_content = refine_res.content
                    if "no change" not in refine_content.lower() and "[" in refine_content:
                        # Attempt to parse new steps
                        import re
                        match = re.search(r"```json\s*(.*?)\s*```", refine_content, re.DOTALL)
                        if match: json_str = match.group(1)
                        else: 
                            match = re.search(r"(\[.*\])", refine_content, re.DOTALL)
                            json_str = match.group(1) if match else "[]"
                            
                        new_next_steps = json.loads(json_str)
                        if new_next_steps and isinstance(new_next_steps, list):
                            print(f"🔄 Plan Refined! Updating {len(new_next_steps)} future steps.")
                            # Update the Main Plan in State
                            plan = plan[:current_index+1] + new_next_steps
                except Exception as e:
                    print(f"⚠️ Plan Refinement Failed: {e}. Keeping original.")

            # --- ARTIFACT UPDATE ---
            try:
                plan_text_updated = "# 📋 Project Execution Plan (Updated)\n\n"
                for idx, step in enumerate(plan):
                    mark = "[ ]"
                    if idx <= current_index: mark = "[x]" # Current one is now done
                    elif idx == current_index + 1: mark = "[>]" # Next one is active (conceptually)
                    
                    plan_text_updated += f"### {mark} Step {idx+1}: {step['title']}\n"
                    plan_text_updated += f"- **Goal**: {step['description']}\n"
                    plan_text_updated += f"- **Agent**: {step['assigned_to']}\n\n"
                
                save_artifact("project_plan", plan_text_updated, "md", thread_id=thread_id)
            except Exception as e:
                print(f"⚠️ Failed to update plan artifact on approval: {e}")

            return {
                "sender": "Supervisor",
                "next": "SUPERVISOR", 
                "current_step_index": current_index + 1,
                "critique_feedback": "", # Clear critique on success
                "plan": plan, # Update Plan in State
                "messages": [SystemMessage(content=f"Step {current_index+1} Passed Quality Control.\n\n{review_result}")]
            }
        else:
            print(f"❌ Step Rejected. Sending back to {assigned_to}.")
            return {
                "sender": "Supervisor",
                "next": assigned_to,
                "critique_feedback": review_result, # Explicitly pass critique state
                "messages": [HumanMessage(content=f"🚨 **SUPERVISOR REJECTED YOUR WORK** 🚨\n\n{review_result}\n\nExisting content was insufficient. Refine it or restart deep research.")]
            }
    else:
        # We need to execute this step.
        # Inject Topic/Context for the worker based on the Step Description
        return {
            "sender": "Supervisor",
            "next": assigned_to,
            "research_topic": current_step['description'], # Override topic with specific step goal
            "messages": [SystemMessage(content=f"Step {current_index+1} 시작: {current_step['title']}")]
        }

