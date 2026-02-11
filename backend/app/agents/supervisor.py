import os
import json
import re
from datetime import datetime
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
    local_knowledge = state.get('local_knowledge', '')
    
    # --- NEW: ARCHIVIST-FIRST FLOW ---
    # --- NEW: ARCHIVIST-FIRST FLOW ---
    # If we have a new user request:
    if messages and isinstance(messages[-1], HumanMessage):
        last_msg = messages[-1].content.lower()
        
        # CASE A: Plan Exists (Ongoing Task)
        if plan:
            reset_keywords = ["reset", "restart", "start over", "처음부터", "다시 시작", "리셋", "초기화", "새로"]
            
            # 1. Explicit Reset Requested
            if any(k in last_msg for k in reset_keywords):
                print("🔄 User requested RESET. Restarting Planner...")
                return {"next": "PLANNER", "plan": [], "current_step_index": 0, "current_sub_step_index": 0, "iteration_count": 0, "sender": "Supervisor"}
            
            # 2. Implicit Feedback (Continue Current Flow)
            # 2. Implicit Feedback (Continue Current Flow)
            else:
                print("📝 User Feedback Detected. Injecting into current context...")
                # Calculate assigned agent dynamically to route immediately
                try:
                    current_step = plan[current_index]
                    assigned_to = current_step['assigned_to']
                    
                    # Direct route to worker with feedback
                    return {
                        "next": assigned_to, 
                        "critique_feedback": f"USER FEEDBACK: {messages[-1].content}",
                        "sender": "Supervisor"
                    }
                except Exception as e:
                     print(f"⚠️ Error routing feedback: {e}. Defaulting to SUPERVISOR.")
                     return {"next": "SUPERVISOR", "sender": "Supervisor"}

        # CASE B: No Plan (Initial Start)
        else:
            # Check if local_knowledge is empty or stale (new request should refresh)
            if not local_knowledge or local_knowledge == "No local research directory configured.":
                print("📂 New User Input Detected -> Routing to ARCHIVIST for Local Document Ingestion")
                return {"next": "ARCHIVIST", "sender": "Supervisor"}
            else:
                # ARCHIVIST already ran, now go to PLANNER
                print("👤 Local Knowledge Ready -> Routing to PLANNER")
                return {"next": "PLANNER", "sender": "Supervisor"}
    
    if not plan:
        if not local_knowledge:
            print("📂 No Plan & No Local Knowledge -> Routing to ARCHIVIST")
            return {"next": "ARCHIVIST", "sender": "Supervisor"}
        print("📋 No Plan but Local Knowledge Ready -> Routing to PLANNER")
        return {"next": "PLANNER", "sender": "Supervisor"}
        
    # 1. Check if all steps completed
    if current_index >= len(plan):
        print("🚩 All plan steps completed -> Routing to FINALIZER for Master Synthesis")
        return {
            "next": "FINALIZER",
            "sender": "Supervisor",
            "messages": [SystemMessage(content="모든 계획 단계가 완료되었습니다. 최종 마스터 보고서 합성을 시작합니다.")]
        }
        
    # 2. Get Current Step
    current_step = plan[current_index]
    step_id = current_step['id']
    assigned_to = current_step['assigned_to']
    
    # 4. Artifact Update: Save current plan status to file (for user visibility)
    # We mark current as 'in_progress' conceptually for the UI, or just 'active'
    from app.utils import save_artifact
    
    # Only save plan when step index changes (avoid excessive file creation)
    last_saved_step = state.get('last_saved_step_index', -1)
    last_saved_sub = state.get('last_saved_sub_index', -1)
    current_sub_index = state.get('current_sub_step_index', 0)
    sub_plan = state.get('sub_plan', [])

    if current_index != last_saved_step or current_sub_index != last_saved_sub:
        plan_text = "# 📋 Project Execution Plan\n\n"
        for idx, step in enumerate(plan):
            mark = "[ ]"
            if idx < current_index: mark = "[x]"
            elif idx == current_index: mark = "[>]" # Current
            
            plan_text += f"### {mark} Step {idx+1}: {step['title']}\n"
            plan_text += f"- **Goal**: {step['description']}\n"
            plan_text += f"- **Agent**: {step['assigned_to']}\n"
            
            # --- v3.9 SUB-STEP INTEGRATION ---
            if idx == current_index and sub_plan:
                plan_text += "\n  **Detailed Sub-steps:**\n"
                for s_idx, sub in enumerate(sub_plan):
                    s_mark = "[ ]"
                    if s_idx < current_sub_index: s_mark = "[x]"
                    elif s_idx == current_sub_index: s_mark = "[>]"
                    plan_text += f"  - {s_mark} **Step {idx+1}.{s_idx+1}**: {sub['title']}\n"
            
            plan_text += "\n"
            
        save_artifact("project_plan", plan_text, "md", thread_id=thread_id)
        # Update markers in state to avoid re-saving in the same loop
        last_saved_step = current_index
        last_saved_sub = current_sub_index
    
    # 5. Routing Logic
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
    sub_plan = state.get('sub_plan', [])
    current_sub_index = state.get('current_sub_step_index', 0)
    incremental_path = state.get('incremental_report_path', '')

    # --- v3.4 Recursive Result Initialization ---
    if not incremental_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        results_dir = os.path.join(base_dir, "results", thread_id)
        os.makedirs(results_dir, exist_ok=True)
        filename = "Project_Recursive_Master_Report.md"
        incremental_path = os.path.join(results_dir, filename)
        
        if not os.path.exists(incremental_path):
            # Initial Header
            with open(incremental_path, "w") as f:
                f.write(f"# 🧬 Recursive Research Master Report\n\n**Thread ID**: {thread_id}\n**Start Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
            print(f"📄 Initialized Recursive Report: {incremental_path}")
        else:
             print(f"📄 Found Existing Recursive Report: {incremental_path}")

    # 5. Hierarchical Planning Check (New v3.3 Recursive Strategy)
    # If we just started a main step and have no sub-plan, decide: Fast Path or Full Planning?
    if not sub_plan and last_node not in ["PLAN_REFINER", "WARDEN", assigned_to]:
        
        # --- v3.7 FAST PATH: Skip sub-plan for simple tasks ---
        if len(plan) <= 2:
            print(f"⚡ Fast Path: Simple task ({len(plan)} steps) - Skipping PLAN_REFINER & WARDEN")
            return {
                "next": assigned_to,
                "sender": "Supervisor",
                "incremental_report_path": incremental_path,
                "messages": [SystemMessage(content=f"Fast Path Activated: Directly executing Step {current_index+1}")]
            }
        else:
            print(f"🔄 Hierarchical Planning: Routing to PLAN_REFINER for Step {current_index+1}")
            return {"next": "PLAN_REFINER", "sender": "Supervisor"}
        
    # --- v3.5 Context Warden Integration ---
    # After Sub-Plan is ready, but BEFORE assigning to worker, call WARDEN for a strategic brief
    if last_node == "PLAN_REFINER":
        print(f"👁️ Context Warden: Routing to WARDEN for Strategic Briefing.")
        return {"next": "WARDEN", "sender": "Supervisor", "incremental_report_path": incremental_path}


    if last_node == assigned_to:
        # Worker finished. Now we CRITIQUE their work product.
        # Use Sub-Step description for more granular critiquing
        current_sub_step = sub_plan[current_sub_index] if sub_plan else current_step
        target_description = current_sub_step.get('description', current_step['description'])
        
        print(f"🕵️ Supervisor Critiquing Sub-Step {current_sub_index+1} of {assigned_to}...")
        
        # --- CRITICAL FIX: Extract actual Work Product instead of status message ---
        if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
            last_output = state.get('shared_knowledge', 'No consolidated research found.')
        elif assigned_to == "ARCHITECT":
            # Extract first slide code if available to see quality
            codes = state.get('slide_code', {})
            last_output = codes.get(1, codes.get(list(codes.keys())[0], "No code found")) if codes else "No code found"
        else:
            last_output = messages[-1].content if messages else "No output"
        
        critique_filename = f"Step{current_index+1}_Sub{current_sub_index+1}_Critique_v{state.get('iteration_count', 0)+1}"
        
        # Regular Critique Path
        # Inject Previous Feedback for Repetition Detection
        previous_feedback = state.get("critique_feedback", "")

        critique_prompt = f"""
        You are the **Chief Editor & Lead Engineer** (Strict Supervisor).
        Your persona is **Steve Jobs**: You are obsessed with detail, quality, and "insanely great" results.
        
        **Your Mission:** Mercilessly evaluate the subordinate's work. **DO NOT COMPROMISE.**
        
        **Original User Goal (THE NORTH STAR - MUST ALIGN):**
        "{messages[0].content[:8000]}"
        
        **Current Step Target:** {target_description}
        **Subordinate Agent:** {assigned_to}

        **PREVIOUS CRITIQUE (Did they fix it?):**
        {previous_feedback[:2000] if previous_feedback else "None (First PASS)"}
        
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
        - **COLLABORATIVE RETRIEVAL (IMPORTANT)**: 만약 하급 에이전트가 본문에 **"🚨 추가 정보 필요"**라는 문구를 포함했다면, 이는 현재 단계가 미완성임을 의미합니다. 이 경우 이유 불문하고 무조건 **REJECT** 하세요. 반려 메시지에 "사용자가 파일을 제공할 때까지 이 단계에서 대기합니다"라고 명시하세요.
        - **REPETITION CHECK**: If the subordinate IGNORED the 'PREVIOUS CRITIQUE' and committed the **SAME** error (e.g. still missing formulas), output "REPEAT_FAILURE: [Reason]". This triggers immediate intervention.
        
        **Output Format:**
        - Approval: "APPROVED: [Brief praise in **KOREAN**]"
        - Rejection: "REJECTED: [Numbered list of specific items to fix in **KOREAN**. Be brutal and extremely detailed.]"
        - Repetition Failure: "REPEAT_FAILURE: [Explain that they ignored previous feedback in **KOREAN**.]"
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
                
                print("✅ Supervisor Forced Approval (30+). Checking for Sub-steps...")
                
                # --- v3.9 FIX: Force Approval Sub-step Logic ---
                # Check if we are in a sub-plan
                sub_plan_data = state.get("sub_plan", {})
                sub_steps = sub_plan_data.get('steps', []) if sub_plan_data else []
                total_subs = len(sub_steps)
                
                # Default moves
                next_node = "SUPERVISOR"
                new_step_idx = current_index
                new_sub_idx = current_sub_index
                
                if total_subs > 0 and current_sub_index < total_subs - 1:
                    # Move to next SUB-step
                    new_sub_idx += 1
                    print(f"👉 Force Approved. Advancing to Sub-step {new_sub_idx + 1}/{total_subs}")
                else:
                    # Move to next MAIN step
                    new_step_idx += 1
                    new_sub_idx = 0
                    print(f"👉 Force Approved. Advancing to Main Step {new_step_idx + 1}")

                updates = {
                    "next": next_node,
                    "current_step_index": new_step_idx,
                    "current_sub_step_index": new_sub_idx,
                    "last_saved_step_index": current_index,  # Track for artifact saving
                    "iteration_count": 0, # RESET ON FORCED APPROVAL
                    "critique_feedback": "",
                    "messages": [SystemMessage(content=f"Step {current_index+1} Force-Approved by Supervisor (Threshold 30).\n\nAPPROVED.")]
                }
                
                # SAVE ARTIFACT for transparency
                from app.utils import save_artifact
                force_filename = f"Step{current_index+1}_Sub{current_sub_index+1}_ForceApproval_v{step_iterations}"
                save_artifact(force_filename, f"# 🚨 Force Approval (Safety Valve)\n\n**Reason**: Failed {step_iterations} attempts.\n## Final Content\n{fixed_content}", "md", thread_id=thread_id)
                
                # --- v3.9 FIX: Append to Master Report (Efficiency) ---
                incremental_path = state.get('incremental_report_path', '')
                if incremental_path and os.path.exists(incremental_path):
                    with open(incremental_path, "a") as f:
                        f.write(f"\n\n## [Forced 30+] Step {current_index+1}.{current_sub_index+1}\n{fixed_content}\n")
                    print(f"💾 Forced Content Appended to Master Report: {incremental_path}")

                if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                    updates["shared_knowledge"] = str(fixed_content)
                elif assigned_to == "ARCHITECT":
                    updates["slide_code"] = {1: str(fixed_content)} 
                return updates
            except Exception as e:
                print(f"⚠️ Hard Intervention Failed: {e}. Force skipping.")
                return {"next": "SUPERVISOR", "current_step_index": current_index + 1, "last_saved_step_index": current_index, "iteration_count": 0, "sender": "Supervisor"}

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
                    "iteration_count": step_iterations + 1,
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
        
        # --- EARLY INTERVENTION LOGIC (Repetition Check) ---
        if review_result.startswith("REPEAT_FAILURE"):
            print(f"⚠️ Repeated Failure Detected (Attempt {step_iterations}). Triggering IMMEDIATE Intervention.")
            
            intervention_prompt = f"""
            **COACHING INTERVENTION MODE (EARLY TRIGGER)**
            The subordinate is STUCK and ignoring feedback.
            You, the Mentor, must **REWRITE THE DRAFT** yourself to break the loop.
            
            **Original Goal:** {messages[0].content[:5000]}
            **Previous Feedback:** {previous_feedback}
            **Current Draft:** {last_output[:20000]}
            
            **TASK:**
            - Rewrite the content to fix the persistent error (e.g. add the missing math).
            - Output ONLY the fixed content.
            """
             
            try:
                fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                fixed_content = fix_response.content
                
                print(f"⚠️ Supervisor Sent Fixed Draft back to {assigned_to} (Early Intervention).")
                
                updates = {
                    "next": assigned_to,
                    "iteration_count": step_iterations + 1, # Increment to avoid version collision
                    "critique_feedback": f"I have rewritten your draft because you ignored my feedback. Study this correction:\n\n{fixed_content[:500]}...",
                    "messages": [HumanMessage(content=f"🚨 **SUPERVISOR INTERVENTION (REPEAT FAILURE)** 🚨\n\nYou failed to address the previous critique. I have fixed it for you. Review the updated draft and FINALIZE it.\n\n(Draft Updated internally)")]
                }
                
                if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                    updates["shared_knowledge"] = str(fixed_content)
                elif assigned_to == "ARCHITECT":
                    updates["slide_code"] = {1: str(fixed_content)} 
                return updates

            except Exception as e:
                print(f"⚠️ Early Intervention Failed: {e}. Falling back to standard rejection.")
                # Fallthrough to standard rejection if intervention fails
        
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

            print(f"✅ Sub-Step {current_sub_index+1} Approved.")
            # Clear collaboration state on success
            state["collaboration_start_time"] = None
            
            # --- v3.4 Recursive Synthesis: Append to Master Report ---
            try:
                current_sub_step = sub_plan[current_sub_index] if sub_plan else plan[current_index]
                
                # 1. Save Individual Step Report (User Request)
                sanitized_title = re.sub(r'[\\/*?:"<>| ]', '_', current_sub_step['title'])
                step_filename = f"Step_{current_index+1}_Sub_{current_sub_index+1}_{sanitized_title}.md"
                step_report_path = os.path.join(results_dir, step_filename)
                
                with open(step_report_path, "w") as f:
                    f.write(f"# 📍 Step {current_index+1}.{current_sub_index+1}: {current_sub_step['title']}\n\n")
                    f.write(f"**Goal**: {current_sub_step['description']}\n\n")
                    f.write(f"{last_output}\n\n")
                print(f"📄 Saved Individual Report: {step_report_path}")

                # 2. Append to Master Report
                with open(incremental_path, "a") as f:
                    f.write(f"## 📍 Step {current_index+1}.{current_sub_index+1}: {current_sub_step['title']}\n\n")
                    f.write(f"**Goal**: {current_sub_step['description']}\n\n")
                    f.write(f"{last_output}\n\n")
                    f.write("---\n\n")
                print(f"📝 Appended result to {incremental_path}")
            except Exception as e:
                print(f"⚠️ Failed to save reports: {e}")

            # Check if more sub-steps remain
            if sub_plan and current_sub_index < len(sub_plan) - 1:
                return {
                    "sender": "Supervisor",
                    "next": "SUPERVISOR",
                    "current_sub_step_index": current_sub_index + 1,
                    "iteration_count": 0,
                    "incremental_report_path": incremental_path,
                    "critique_feedback": "",
                    "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} Passed. Moving to Sub-Step {current_sub_index+2}.")]
                }

            print("✅ Main Step Approved. Moving to Next Main Step.")
            # RESET SUB-PLAN for next main step
            return {
                "sender": "Supervisor",
                "next": "SUPERVISOR", 
                "current_step_index": current_index + 1,
                "last_saved_step_index": current_index,  # Track for artifact saving
                "current_sub_step_index": 0,
                "sub_plan": [], 
                "iteration_count": 0, # Reset for next step
                "incremental_report_path": incremental_path,
                "critique_feedback": "", # Clear critique on success
                "plan": plan, # Update Plan in State
                "shared_knowledge": "", # CORE FIX: Clear stale knowledge
                "slide_code": {}, # CORE FIX: Clear stale code
                "messages": [SystemMessage(content=f"Step {current_index+1} (All Sub-steps) Passed Quality Control.\n\n{review_result}")]
            }

        elif review_result.startswith("REJECTED") or review_result.startswith("INSUFFICIENT_DATA"):
            # --- v3.5 Collaborative Timeout Check ---
            import time
            if "🚨 추가 정보 필요" in str(last_output):
                start_time = state.get("collaboration_start_time")
                current_time = time.time()
                
                if start_time is None:
                    print("🚨 First Collaborative Request. Initializing 1-hour timer.")
                    state["collaboration_start_time"] = current_time
                    start_time = current_time
                
                elapsed = current_time - start_time
                if elapsed < 3600: # 1 Hour
                    print(f"⏳ Waiting for user document (Elapsed: {int(elapsed)}s/3600s). Throttling loop...")
                    time.sleep(120) # 2 minute sleep to slow down iterations (30 iterations * 2m = 1hr)
                else:
                    print("⏰ Collaborative Timeout (1 hour) reached. Forcing autonomous progress.")
                    state["collaboration_start_time"] = None
                    return {
                        "sender": "Supervisor",
                        "next": "SUPERVISOR",
                        "current_sub_step_index": current_sub_index + 1,
                        "iteration_count": 0,
                        "critique_feedback": f"TIMEOUT: User did not provide document in 1hr. Proceeding with best available data. DO NOT ask for this file again. (Ref: {current_sub_step_index+1})",
                        "messages": [SystemMessage(content=f"Sub-step {current_sub_index+1} Force-Approved due to user inactivity (1hr timeout). Proceeding autonomously.")]
                    }
            
            print(f"❌ Step Rejected. Sending back to {assigned_to}.")
            return {
                "sender": "Supervisor",
                "next": assigned_to,
                "iteration_count": step_iterations + 1,
                "critique_feedback": review_result, # Explicitly pass critique state
                "messages": [HumanMessage(content=f"🚨 **SUPERVISOR REJECTED YOUR WORK** 🚨\n\n{review_result}\n\nExisting content was insufficient. Refine it or restart deep research.")]
            }
    else:
        # We need to execute this step.
        # 6. Inject Topic/Context for the worker based on the Sub-Step/Step
        active_step = sub_plan[current_sub_index] if sub_plan else current_step
        
        # --- v3.5 Agile Path Optimizer: Dynamic Plan Update Check ---
        # If we are starting a NEW MAIN STEP (sub_index 0), quickly check if the plan is still valid
        # This is a 'soft' version where we just log info, but could be upgraded to force re-plan
        if current_sub_index == 0 and last_node == "WARDEN":
             print(f"🚀 [Agile Optimizer] Proceeding with current plan for Step {current_index+1}.")

        print(f"🚀 Supervisor Delegating Sub-Step {current_sub_index+1} to {assigned_to}...")
        
        return {
            "sender": "Supervisor",
            "next": assigned_to,
            "research_topic": active_step.get('description', active_step.get('title', 'Unknown')), 
            "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} 시작: {active_step['title']}")]
        }

