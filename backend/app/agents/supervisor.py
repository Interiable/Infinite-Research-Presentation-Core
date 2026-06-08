import os
import json
import re
from datetime import datetime

def save_dialogue_message(thread_id, sender, content):
    """Lazy-import wrapper to avoid circular dependency with endpoints.py."""
    try:
        from app.api.endpoints import save_dialogue_message as _sdm
        _sdm(thread_id, sender, content)
    except Exception:
        pass  # Silently fail — dialogue is non-critical
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END

from app.core.state import AgentState
from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT, CONTENT_CRITIQUE_PROMPT, DESIGN_CRITIQUE_PROMPT
from app.utils import RobustGemini, log_night_audit, extract_text_content

# --- TIERED MODEL STRATEGY ---
# 1. Pro Model (Robust): Checks Quota, Falls back to Flash
llm_pro = RobustGemini(
    temperature=0.2
)

# 2. Flash Model: For repetitive tasks or simple routing
llm_flash = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"), 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=120,
    max_retries=2
)

from langchain_core.runnables import RunnableConfig

def _trim_messages(messages, max_keep=20):
    """
    Keeps only the most recent messages to prevent state memory bloat.
    Always preserves the FIRST message (Original User Prompt).
    """
    if not messages or len(messages) <= max_keep:
        return messages
    # Keep the very first message + the last (max_keep - 1) messages
    return [messages[0]] + messages[-(max_keep - 1):]

def supervisor_node(state: AgentState, config: RunnableConfig):
    """
    The Supervisor determines the next step based on the current state.
    It acts as the Router and the Judge.
    Uses Pro model for Critiques to ensure high quality planning.
    """
    try:
        # Extract Thread ID for Artifact Isolation
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        # --- PLAN-DRIVEN SUPERVISOR LOGIC ---
        
        # 0. Check if Plan exists
        plan = state.get('plan', [])
        messages = state.get('messages', [])
        current_index = state.get('current_step_index', 0)
        local_knowledge = state.get('local_knowledge', '')
        
        # v7.0: Helper to attach progress data to every return dict for WebSocket broadcast
        def _with_progress(result: dict) -> dict:
            """Injects plan progress fields into supervisor return dict."""
            result['plan'] = plan
            result['current_step_index'] = current_index
            result['sub_plan'] = state.get('sub_plan', [])
            result['current_sub_step_index'] = state.get('current_sub_step_index', 0)
            return result
        
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
                            "sender": "Supervisor",
                            "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                            "current_chapter_index": state.get('current_chapter_index', 0),
                            "approved_chapters": state.get("approved_chapters", []),
                            "sub_plan": state.get("sub_plan", [])
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
            # Check if any plan step was already assigned to FINALIZER
            has_finalizer_step = any(s.get('assigned_to') == 'FINALIZER' for s in plan)
            
            if has_finalizer_step:
                # Finalizer was explicitly in the plan → it already ran → END
                print("🏁 All plan steps completed (Finalizer was in plan). Ending project.")
                return {
                    "next": "END",
                    "sender": "Supervisor",
                    "messages": [SystemMessage(content="모든 계획 단계가 완료되었습니다. 프로젝트를 종료합니다.")]
                }
            else:
                # No Finalizer in plan → auto-invoke for document assembly
                print("🚩 All plan steps completed → Auto-routing to FINALIZER for assembly.")
                return {
                    "next": "FINALIZER",
                    "sender": "Supervisor",
                    "messages": [SystemMessage(content="모든 계획 단계가 완료되었습니다. 최종 마스터 보고서 합성을 시작합니다.")]
                }
            
        # 2. Get Current Step
        current_step = plan[current_index]
        step_id = current_step['id']
        assigned_to = current_step['assigned_to']
        
        # --- v11.0 RESUME SKIP: Auto-advance past steps that already have report_final artifacts ---
        # When resuming, check if the current step's report_final files already exist.
        # If they do, skip directly to the next main step. This cascades until we hit
        # an incomplete step or reach the end (which triggers FINALIZER).
        if assigned_to != "FINALIZER":  # Don't skip the Finalizer step itself
            import glob as _glob_skip
            base_dir_skip = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            artifact_dir_skip = os.path.join(base_dir_skip, "artifacts", thread_id)
            
            step_num = current_index + 1
            existing_finals = _glob_skip.glob(os.path.join(artifact_dir_skip, f"*_step{step_num}_sub*_report_final.md"))
            # Exclude .old_backup files
            existing_finals = [f for f in existing_finals if not f.endswith('.old_backup')]
            
            if existing_finals:
                # v11.5 FIX: Only execute Resume Skip if ALL sub-step files are complete for this step.
                # Avoid skipping the remaining sub-steps immediately after Sub-Step 1 finishes.
                subplan_files = _glob_skip.glob(os.path.join(artifact_dir_skip, f"*_step{step_num}_subplan.md"))
                should_skip = False
                
                if subplan_files:
                    try:
                        with open(subplan_files[-1], 'r', encoding='utf-8') as f:
                            sp_content = f.read()
                        # Count bullet points to approximate sub_plan length
                        import re
                        item_count = len(re.findall(r'-\s+\[.\]', sp_content))
                        if item_count > 0 and len(existing_finals) >= item_count:
                            should_skip = True
                    except Exception:
                        pass
                
                if should_skip:
                    print(f"⏭️ RESUME SKIP: Step {step_num} already has ALL {len(existing_finals)} report_final file(s). Skipping...")
                    for ef in sorted(existing_finals):
                        print(f"   ► Found: {os.path.basename(ef)}")
                    
                    # Advance to next main step
                    next_index = current_index + 1
                    if next_index >= len(plan):
                        # All steps done, check for FINALIZER
                        has_finalizer_step = any(s.get('assigned_to') == 'FINALIZER' for s in plan)
                        if has_finalizer_step:
                            print("🏁 All steps completed (with Finalizer in plan). Ending project.")
                            return {
                                "next": "END",
                                "sender": "Supervisor",
                                "messages": [SystemMessage(content="모든 계획 단계가 완료되었습니다. 프로젝트를 종료합니다.")]
                            }
                        else:
                            print("🚩 All research steps completed → Auto-routing to FINALIZER.")
                            return {
                                "next": "FINALIZER",
                                "sender": "Supervisor",
                                "messages": [SystemMessage(content="모든 계획 단계가 완료되었습니다. 최종 마스터 보고서 합성을 시작합니다.")]
                            }
                    else:
                        return {
                            "sender": "Supervisor",
                            "next": "SUPERVISOR",
                            "current_step_index": next_index,
                            "current_sub_step_index": 0,
                            "current_chapter_index": 0,
                            "approved_chapters": [],
                            "chapter_plan": [],
                            "sub_plan": [],
                            "iteration_count": 0,
                            "critique_feedback": "",
                            "plan": plan,
                            "messages": [SystemMessage(content=f"⏭️ Step {step_num} already completed (found {len(existing_finals)} artifacts). Advancing to Step {next_index+1}.")]
                        }
        # --- END RESUME SKIP ---
        
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
        
        # --- v11.2 FIX: Detect Finalizer return via message content ---
        # 'sender' is NOT in AgentState TypedDict, so LangGraph drops it.
        # Instead, detect Finalizer return by checking last message for its signature strings.
        if last_node == "SUPERVISOR" and messages:
            last_msg_content = str(messages[-1].content) if messages[-1] else ""
            if "Finalizer Draft Submitted" in last_msg_content or "Finalizer Failure" in last_msg_content:
                last_node = "FINALIZER"
                print(f"   🔄 Detected Finalizer return via message signature. Setting last_node=FINALIZER")
            elif "Assembly Complete" in last_msg_content:
                last_node = "FINALIZER"
                print(f"   🔄 Detected Finalizer Assembly Complete via message signature. Setting last_node=FINALIZER")
            elif "Soft Intervention Complete." in last_msg_content or "Coaching Intervention Complete." in last_msg_content:
                # v11.3 FIX: Softfix & Coaching fix evaluation loop
                last_node = assigned_to
                print(f"   🔄 Detected Intervention (Soft/Coaching) via message signature. Pretending {assigned_to} returned it for evaluation.")

        
        sub_plan = state.get('sub_plan', [])
        current_sub_index = state.get('current_sub_step_index', 0)
        print(f"🔍 DEBUG [Supervisor Entry] sub_plan_len={len(sub_plan) if sub_plan else 0}, current_sub_index={current_sub_index}, last_node={last_node}")
        incremental_path = state.get('incremental_report_path', '')

        # --- v3.4 Recursive Result Initialization ---
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        results_dir = os.path.join(base_dir, "results", thread_id)
        
        if not incremental_path:
            os.makedirs(results_dir, exist_ok=True)
            filename = "00_Project_Recursive_Master_Report.md"
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
        if not sub_plan and last_node not in ["PLAN_REFINER", "WARDEN", "RESEARCHER", assigned_to, "DEEP_RESEARCHER", "FINALIZER"]:
            
            # --- v3.19 FINALIZER DIRECT ROUTING ---
            if assigned_to == "FINALIZER":
                print(f"⚡ Fast Path: Finalizer bypasses sub-planning. Executing final compilation.")
                return {
                    "next": "FINALIZER",
                    "sender": "Supervisor",
                    "incremental_report_path": incremental_path,
                    "messages": [SystemMessage(content=f"Routing directly to FINALIZER for Step {current_index+1}")]
                }
            
            # --- v3.7 FAST PATH: Skip sub-plan for simple tasks ---
            elif len(plan) <= 2:
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


        if last_node == "DEEP_RESEARCHER":
            print(f"📡 Deep Research Complete. Bypassing Critique and returning to Lead Researcher (RESEARCHER).")
            # --- v3.10 FIX: Persistent Iteration Count ---
            current_iterations = state.get("iteration_count", 0)
            existing_critique = state.get("critique_feedback", "")
            
            return {
                "sender": "Supervisor",
                "next": "RESEARCHER",
                "iteration_count": current_iterations, # Persist count
                "research_mode": "deep", # RESET to default mode after deep research
                "critique_feedback": existing_critique, # PRESERVE FEEDBACK FOR DEEPSEEK TRIGGER
                "sub_plan": state.get("sub_plan", []),  # v6.4: CRITICAL - Preserve sub_plan when returning to Researcher
                "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                "current_chapter_index": state.get('current_chapter_index', 0),
                "approved_chapters": state.get("approved_chapters", []),
                "messages": _trim_messages(messages) + [SystemMessage(content=f"Deep Research 자료가 수집되었습니다. (Iteration {current_iterations}/15). 리서처가 이를 바탕으로 보고서를 작성합니다.")]
            }

        # --- PHASE 13.2: RESEARCHER DELEGATION TO DEEP_RESEARCHER ---
        # If the Researcher has no local files and needs web data, it returns a delegation signal.
        # The Supervisor dispatches the full DEEP_RESEARCHER node (keyword optimization, media search, etc.)
        if last_node == "RESEARCHER" and messages:
            last_msg_content = str(messages[-1].content)
            
            if "DELEGATE_DEEP_RESEARCH" in last_msg_content:
                print(f"📡 Researcher requested Deep Research delegation. Dispatching DEEP_RESEARCHER (full pipeline).")
                current_iterations = state.get("iteration_count", 0)
                return {
                    "sender": "Supervisor",
                    "next": "DEEP_RESEARCHER",
                    "research_topic": state.get("research_topic", "Unknown"),
                    "research_mode": "deep_web",
                    "iteration_count": current_iterations,
                    "sub_plan": state.get("sub_plan", []),
                    "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                    "current_chapter_index": state.get('current_chapter_index', 0),
                    "approved_chapters": state.get("approved_chapters", []),
                    "messages": _trim_messages(messages) + [SystemMessage(content=f"Researcher가 Deep Research를 요청했습니다. 풀 파이프라인 조사를 수행합니다.")]
                }
            
            # Legacy: Internal research complete (for backward compatibility)
            if "Deep Research (Web/Academic/Local) Complete" in last_msg_content:
                print(f"📡 Internal Research by Researcher Complete. Requesting report synthesis.")
                current_iterations = state.get("iteration_count", 0)
                return {
                    "sender": "Supervisor",
                    "next": "RESEARCHER",
                    "iteration_count": current_iterations,
                    "research_mode": "deep",
                    "critique_feedback": "조사된 내용을 바탕으로 상세 보고서를 작성해 주세요.",
                    "sub_plan": state.get("sub_plan", []),
                    "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                    "current_chapter_index": state.get('current_chapter_index', 0),
                    "approved_chapters": state.get("approved_chapters", []),
                    "messages": _trim_messages(messages) + [SystemMessage(content=f"내부 조사가 완료되었습니다. 이제 수집된 데이터를 바탕으로 보고서를 작성하세요.")]
                }

        # v5.5 FIX: When assigned_to is DEEP_RESEARCHER, Supervisor redirects to RESEARCHER
        # for report writing. We must also critique RESEARCHER's output in this case.
        worker_returned = (last_node == assigned_to) or \
                          (last_node == "FINALIZER") or \
                          (last_node == "RESEARCHER" and assigned_to == "DEEP_RESEARCHER")
        if worker_returned:
            # v5.5: Determine effective worker — who actually did the work
            effective_worker = "RESEARCHER" if (last_node == "RESEARCHER" and assigned_to == "DEEP_RESEARCHER") else assigned_to
            
            # --- FINALIZER SPECIFIC CRITIQUE LOOP ---
            if effective_worker == "FINALIZER" or last_node == "FINALIZER":
                # Check if Finalizer just finished translation (Assembly Complete)
                if messages and "Assembly Complete" in str(messages[-1].content):
                    print("🏁 Finalizer Document Assembly & Translation Complete. Ending Project.")
                    return {"next": "END", "sender": "Supervisor", "messages": [SystemMessage(content="모든 최종 작업 및 번역이 완료되었습니다.")]}

                print(f"🕵️ Supervisor Critiquing Finalizer Output...")
                last_output = str(state.get('shared_knowledge', 'No consolidated final report found.'))
                step_iterations = state.get("iteration_count", 0)
                previous_feedback = state.get("critique_feedback", "")
                
                critique_prompt = f"""
                You are the **Chief Editor & Publisher**.
                Evaluate the Finalizer's ultimate project deliverable.
                
                **Original User Goal:** "{messages[0].content[:8000]}"
                
                **PREVIOUS CRITIQUE:** {previous_feedback}
                
                **FINAL DRAFT TO EVALUATE:**
                {last_output[:500000]}
                
                **CRITERIA:**
                1. Does it perfectly answer the original user goal?
                2. Is the formatting (like Capability Maps or structural tables) correct?
                3. Are there any internal tags, placeholders, or messy formatting?
                
                If perfect, output "APPROVED: [praise]".
                If it needs fixing, output "REJECTED: [Numbered list of fixes]".
                """
                if step_iterations >= 3:
                     review_result = "APPROVED: Forced approval after max iterations."
                else:
                     response = llm_pro.invoke([HumanMessage(content=critique_prompt)])
                     review_result = extract_text_content(response).strip()
                     
                if review_result.startswith("APPROVED"):
                    print("✅ Finalizer step APPROVED. Transitioning back to Finalizer for Translation/Assembly.")
                    # v7.3: Save critique for review
                    save_artifact(f"Finalizer_Critique_{step_iterations+1}", f"# Finalizer Critique #{step_iterations+1}\n\n**Result:** APPROVED\n\n{review_result}", "md", thread_id=thread_id)
                    return {
                        "next": "FINALIZER",
                        "iteration_count": step_iterations,
                        "critique_feedback": "APPROVED",
                        "messages": [SystemMessage(content="Final Report Approved. Executing final translation and assembly.")]
                    }
                else:
                    print(f"❌ Finalizer Draft REJECTED (iteration {step_iterations+1}):")
                    print(f"   📋 Reason: {review_result[:500]}")
                    # v7.3: Save critique for review
                    save_artifact(f"Finalizer_Critique_{step_iterations+1}", f"# Finalizer Critique #{step_iterations+1}\n\n**Result:** REJECTED\n\n{review_result}", "md", thread_id=thread_id)
                    return {
                        "next": "FINALIZER",
                        "iteration_count": step_iterations + 1,
                        "critique_feedback": review_result,
                        "messages": [HumanMessage(content=f"FINALIZER REJECTED: {review_result}")]
                    }
            
            # Use Sub-Step description for more granular critiquing
            current_sub_step = sub_plan[current_sub_index] if sub_plan else current_step
            target_description = current_sub_step.get('description', current_step['description'])
            
            print(f"🕵️ Supervisor Critiquing Sub-Step {current_sub_index+1} of {effective_worker} (assigned: {assigned_to})...")
            
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
            
            # --- v10.5 EMPTY CHAPTER GUARD: Don't waste iterations on blank submissions ---
            step_iterations = state.get("iteration_count", 0)  # Read early for empty guard
            if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                # Strip markdown headers and whitespace to check actual content length
                import re as _re_guard
                content_only = _re_guard.sub(r'^#+\s+.*$', '', str(last_output), flags=_re_guard.MULTILINE).strip()
                if len(content_only) < 300:
                    print(f"⚠️ EMPTY CHAPTER DETECTED ({len(content_only)} chars of actual content). Returning to Researcher WITHOUT incrementing iteration count ({step_iterations}/15).")
                    save_dialogue_message(thread_id, "Supervisor", f"⚠️ Empty chapter detected ({len(content_only)} chars). Sending back to Researcher without counting as an attempt.")
                    save_artifact(critique_filename, f"# ⚠️ Empty Chapter Detected\n\n**Content length:** {len(content_only)} chars (below 300 char minimum)\n**Action:** Returned to Researcher WITHOUT incrementing iteration count.\n**Current iteration:** {step_iterations}/15", "md", thread_id=thread_id)
                    return {
                        "sender": "Supervisor",
                        "next": assigned_to,
                        "iteration_count": step_iterations,  # DO NOT INCREMENT
                        "sub_plan": state.get("sub_plan", []),
                        "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                        "current_chapter_index": state.get('current_chapter_index', 0),
                        "approved_chapters": state.get("approved_chapters", []),
                        "critique_feedback": f"⚠️ YOUR PREVIOUS SUBMISSION WAS EMPTY (only {len(content_only)} chars of content). This is likely an API error. Please write the FULL chapter content. This attempt was NOT counted against your iteration limit.",
                        "messages": [HumanMessage(content=f"⚠️ EMPTY CHAPTER: Your submission contained only {len(content_only)} chars. Please write the full chapter.")]
                    }

            # Regular Critique Path
            # Inject Previous Feedback for Repetition Detection
            previous_feedback = state.get("critique_feedback", "")

            # --- v6.0 ITERATION-ADAPTIVE CRITIQUE ---
            step_iterations = state.get("iteration_count", 0)
            
            # After 7+ attempts, relax critique to accept reasonable estimates
            adaptive_clause = ""
            if step_iterations >= 7:
                adaptive_clause = """
            **⚠️ ADAPTIVE TOLERANCE (Iteration {iter_count}/15):**
            The writer has attempted this chapter {iter_count} times. At this stage:
            - **ACCEPT reasonable Fermi estimates** for hardware metrics (VRAM, latency, FPS) if exact benchmarks are unavailable.
            - **DO NOT REJECT** solely for lacking precise benchmark numbers — approximate values with clear assumptions are acceptable.
            - **FOCUS ONLY ON**: (1) Factual errors, (2) Internal tags/placeholders, (3) Completely off-topic content.
            - **DO NOT REJECT for partial scope coverage** — the writer has shown good faith effort across {iter_count} attempts.
            - **DO NOT demand additional matrices, tables, or comparative sections** beyond what the chapter title requires.
            - If the content is technically sound, well-structured, and addresses the core topic with reasonable depth, **APPROVE IT**.
            """.format(iter_count=step_iterations)
                print(f"📊 Adaptive Critique Active (Iteration {step_iterations}/15): Relaxed standards.")  # noqa: E501

            # Extract chapter context for scope-aware critique
            _critique_chap_plan = state.get('chapter_plan', [])
            _critique_chap_idx = state.get('current_chapter_index', 0)
            _critique_chap_title = _critique_chap_plan[_critique_chap_idx].get('title', '') if _critique_chap_plan and _critique_chap_idx < len(_critique_chap_plan) else ''
            _critique_chap_total = len(_critique_chap_plan) if _critique_chap_plan else 1
            
            # --- v10.7 TOPIC-AWARE CRITIQUE: Classify chapter as data-driven vs conceptual ---
            _topic_cache = state.get('_topic_type_cache', {})
            _cache_key = f"s{current_index}_ss{current_sub_index}_ch{_critique_chap_idx}"
            topic_type = _topic_cache.get(_cache_key, None)
            
            if topic_type is None and _critique_chap_title:
                try:
                    classify_prompt = f"""Classify this chapter topic as exactly 'A' or 'B':

A = DATA-DRIVEN: Requires specific numbers, benchmarks, formulas, code, hardware specs, experimental results, or quantitative comparisons.
B = CONCEPTUAL: Focuses on UX design, frameworks, taxonomies, scenario mapping, design patterns, strategic analysis, user experience reasoning, or qualitative evaluation.

Step Goal: {target_description[:300]}
Chapter Title: "{_critique_chap_title}"

Answer ONLY 'A' or 'B':"""
                    _cls_resp = llm_flash.invoke([HumanMessage(content=classify_prompt)])
                    _cls_result = extract_text_content(_cls_resp).strip().upper()
                    topic_type = "CONCEPTUAL" if 'B' in _cls_result else "DATA_DRIVEN"
                    print(f"🏷️ Chapter Topic Classification: {_critique_chap_title[:50]}... → {topic_type}")
                except Exception as _cls_err:
                    print(f"⚠️ Topic classification failed: {_cls_err}. Defaulting to DATA_DRIVEN.")
                    topic_type = "DATA_DRIVEN"
            elif topic_type is None:
                topic_type = "DATA_DRIVEN"
            
            # Update cache for persistence
            _topic_cache[_cache_key] = topic_type
            
            # Build topic-specific evaluation criteria
            if topic_type == "CONCEPTUAL":
                topic_criteria = """
            **📐 TOPIC TYPE: CONCEPTUAL / UX DESIGN**
            This chapter is about frameworks, UX patterns, scenario mapping, or qualitative design analysis.
            Adjust your evaluation accordingly:
            - **DO NOT require** inline citations `[File: ...]` or `[Web: ...]` for design reasoning, UX heuristics, or experience-based insights. Citations are only required for externally sourced factual claims (statistics, study results).
            - **DO NOT require** a `## References` section if the chapter is purely design/framework-based with no external data claims.
            - **DO NOT reject** for lacking precise numerical thresholds — UX heuristics with qualitative descriptors (e.g., "brief pause", "subtle motion") are acceptable.
            - **EVALUATE based on**: (1) Logical coherence, (2) Practical applicability, (3) Completeness of framework/taxonomy, (4) Consistency with the user's design vision, (5) Clarity of UX rationale.
            - **APPROVE** if the design framework is well-structured, logically sound, and addresses the chapter topic with practical depth.
            """
                print(f"📐 Conceptual critique mode active for: {_critique_chap_title[:50]}")
            else:
                topic_criteria = """
            **🔬 TOPIC TYPE: DATA-DRIVEN / TECHNICAL**
            Standard strict evaluation criteria apply:
            - Inline citations required for factual claims.
            - `## References` section required.
            - Specific numbers, formulas, and benchmarks expected where applicable.
            """
            
            
            aggregated_knowledge = state.get('shared_knowledge', '') or state.get('web_knowledge', '')
            
            critique_prompt = f"""
            You are the **Chief Editor & Lead Engineer** (Strict Supervisor).
            Your persona is **Steve Jobs**: You are obsessed with detail, quality, and "insanely great" results.
            
            **Your Mission:** Evaluate the subordinate's work with high standards.
            
            **AGGREGATED KNOWLEDGE (The Ground Truth Data):**
            {aggregated_knowledge[:10000] if aggregated_knowledge else "No background knowledge established yet."}
            
            **Original User Goal (THE NORTH STAR - MUST ALIGN):**
            "{messages[0].content[:8000]}"
            
            **Current Step Target:** {target_description}
            **Subordinate Agent:** {assigned_to}
            **Current Iteration:** {step_iterations}/15
            {topic_criteria}
            **⚠️ CHAPTER-LEVEL SCOPE AWARENESS:**
            This submission is **Chapter {_critique_chap_idx+1} of {_critique_chap_total}** in this sub-step.
            Chapter Title: "{_critique_chap_title}"
            The writer is NOT expected to cover the ENTIRE step target in this one chapter.
            Each chapter covers a focused slice. Evaluate ONLY whether this chapter fulfills its own title/topic well.
            Do NOT reject because other dimensions, categories, or analyses are missing — those belong in other chapters.

            **PREVIOUS CRITIQUE (Did they fix it?):**
            {previous_feedback[:2000] if previous_feedback else "None (First PASS)"}
            
            **THE WORK PRODUCT TO EVALUATE:**
            {last_output[:500000]} 
            {adaptive_clause}
            **STRICT EVALUATION CRITERIA:**
            1.  **Alignment (절대적 부합)**: 원본 프롬프트(North Star)의 의도에서 단 1%라도 벗어났는가?
            2.  **Depth & Audience (심층성과 청중 적합성)**: 대상 독자(Audience)에 맞는 최적의 깊이인가? 엔지니어/기술 문서라면 공식과 코드가 필수지만, UX/기획/발표용(PPT/Pitch Deck) 문서라면 복잡한 물리/수학 수식을 제거하고 '비즈니스 및 사용자 경험(UX) 가치'가 심도 있게 다뤄졌는가 판단.
            3.  **Specific Detail (구체성)**: 로컬 파일의 내용을 구체적으로 융합/인용했는가? 단순 요약은 'REJECT' 대상임.
            4.  **Polish (완성도)**: 🚨 DEEP_RESEARCH_REQUIRED 같은 내부 태그나 해결되지 않은 메모가 본문에 남아있는가? (남아있다면 무조건 REJECT). 보고서 형식이 논리적이고 깔끔한가?
            5.  **Scope Guard (Strict)**: The work must match the '**Current Step Target**' EXACTLY. 
                - **FUTURE STEP DETECTION**: If the current step is 1.1, the report MUST NOT contain detailed sections on ToM, LMA, or Architecture. 
                - If it covers future steps (e.g., Step 1.2, 1.3), **REJECT** immediately with "SCOPE_OVERREACH". 
                - Do not praise 'bonus' work; it causes redundancy in the final master report.
            
            **DECISION RULES:**
            - **LANGUAGE RULE**: The report MUST ALWAYS be written in **ENGLISH** regardless of the user's input language. Do NOT reject for being in English even if the user's request is in Korean/Japanese/etc. The user's input language is for communication, NOT the report language.
            - "좋은 내용이다" 정도면 **REJECT**. 반드시 "압도적으로 훌륭함(Insanely Great)"을 충족해야 함.
            - 만약 에이전트가 본인의 상태 메시지(예: "Research complete...")만 보내고 실제 보고서 내용을 포함하지 않았다면 무조건 **REJECT**.
            
            - **MISSING DATA HANDLING (CRITICAL)**:
                1. **Derivable Data (게으름)**: 만약 누락된 데이터가 물리학적 추론이나 페르미 추정으로 도출 가능한 경우(예: "모터 토크가 충분한가?"), **REJECT**하고 "직접 계산하여 가정을 세우시오"라고 지시하세요.
                2. **Non-Derivable Facts (불가항력)**: 만약 누락된 데이터가 외부의 구체적 사실(예: "특정 논문의 실험 수치", "최신 칩셋의 출시일", "경쟁사 제품의 무게")이라서 추론이 불가능한 경우, **DEEP_RESEARCH_REQUIRED**를 출력하세요. "외부 검색을 통해 데이터를 찾아오시오"라고 지시하세요.
                3. **Patent / Prior Art (특허/선행기술)**: 사용자 목표가 UX Research, 제품 설계, 기술 발명, 또는 신규 제품 개발인 경우, 관련 **특허 분석(Prior Art Analysis)**이 보고서에 포함되어야 합니다. 특허 데이터가 누락되었다면 **DEEP_RESEARCH_REQUIRED: Patent search needed for [specific topic]**를 출력하세요. 시스템이 자동으로 Lens Patent API, PatentsView, Google Patents를 검색합니다.
                4. **Citation Sparsity (인용 희박 — 즉시 추가 검색 요청)**: 아래 조건을 **모두** 충족하면 즉시 **DEEP_RESEARCH_REQUIRED**를 출력하세요.
                   - 챕터가 시장 동향, 경쟁사 분석, 기술 스펙, 학술 연구 결과 등 외부 데이터가 필수인 주제를 다루고 있음
                   - 챕터에 인용된 외부 출처(web/paper 타입 REF)가 **2개 이하**이거나 로컬 파일 REF만 반복 인용되고 있음
                   - 즉, 챕터가 사실상 내부 문서에만 의존하여 외부 근거가 빈약한 상태임
                   → 이 경우 "DEEP_RESEARCH_REQUIRED: Insufficient external sources. Need web/paper search for [specific missing data]."를 출력하세요.

            - **CITATION & REFERENCES ENFORCEMENT**:
                1. If the draft lacks inline citations (e.g., `[File: ...]`, `[Web: ...]`) for factual claims, output `REJECTED: Missing inline citations.`
                2. If the draft lacks a "## References" section at the end, output `REJECTED: Missing References section.`

            - **REPETITION CHECK**: If the subordinate IGNORED the 'PREVIOUS CRITIQUE' and committed the **SAME** error, output "REPEAT_FAILURE".
            
            **Output Format:**
            - Approval: "APPROVED: [Brief praise in **ENGLISH**]"
            - Rejection: "REJECTED: [Numbered list of specific items to fix in **ENGLISH**.]"
            - Deep Research Required: "DEEP_RESEARCH_REQUIRED: [Explain what technical data is missing in **ENGLISH**.]"
            - Repetition Failure: "REPEAT_FAILURE: [Explain that they ignored previous feedback in **ENGLISH**.]"
            """
            
            # --- GRADUATED INTERVENTION (Safety Valve) ---
            
            # --- v6.3 CONSECUTIVE SIMILAR-CRITIQUE DETECTION ---
            # Smart Diagnosis takes priority over Soft Intervention at ALL iterations
            if step_iterations >= 3 and previous_feedback:
                try:
                    similarity_check_prompt = f"""Compare these two critique texts. Do they reject for the SAME core reason? Answer ONLY 'YES' or 'NO'.

Critique A (Previous): {previous_feedback[:500]}
Critique B (Current Draft Issues): The writer submitted essentially the same content as before.

Answer:"""
                    sim_response = llm_flash.invoke([HumanMessage(content=similarity_check_prompt)])
                    sim_result = extract_text_content(sim_response).strip().upper()
                    
                    if 'YES' in sim_result and step_iterations >= 3:
                        consecutive_same = state.get('_consecutive_same_critique', 0) + 1
                        if consecutive_same >= 3:
                            print(f"🔄 Consecutive Same-Critique Detected ({consecutive_same}x). Diagnosing root cause...")
                            
                            # v6.3 SMART DIAGNOSIS: Is it a structure problem or a data gap?
                            curr_chap_idx = state.get('current_chapter_index', 0)
                            chap_plan = state.get('chapter_plan', [])
                            chap_title = chap_plan[curr_chap_idx].get('title', 'Unknown Chapter') if curr_chap_idx < len(chap_plan) else "Current Chapter"
                            
                            diagnosis_prompt = f"""You are diagnosing why a research writer has failed 3+ times with the same error.

Recurring Rejection Reason: {previous_feedback[:1500]}
Chapter Title: {chap_title}
Original Goal: {messages[0].content[:1500]}

Is this failure caused by:
A) STRUCTURE PROBLEM — The chapter plan itself is flawed (wrong scope, illogical order, duplicate topics, chapter title doesn't match the goal)
B) DATA GAP — The writer lacks sufficient source material/data to write this chapter properly (missing technical specs, no search results, needs web/patent research)

Answer ONLY 'A' or 'B' with a one-line reason."""

                            try:
                                diag_response = llm_flash.invoke([HumanMessage(content=diagnosis_prompt)])
                                diag_result = extract_text_content(diag_response).strip().upper()
                                
                                if 'A' in diag_result:
                                    # STRUCTURE PROBLEM → Reset chapter_plan
                                    print(f"🏗️ Diagnosis: STRUCTURE PROBLEM. Resetting chapter_plan for re-generation.")
                                    save_artifact(critique_filename, f"# 🏗️ Supervisor Smart Diagnosis: STRUCTURE RESET\n\n**Recurring Issue ({consecutive_same}x):** {previous_feedback[:500]}\n\n**Diagnosis:** Chapter plan structure is flawed. Resetting for re-generation.", "md", thread_id=thread_id)
                                    return {
                                        "next": effective_worker,
                                        "iteration_count": step_iterations,  # v10.6: Don't increment — structure reset is not Researcher's fault
                                        "_consecutive_same_critique": 0,
                                        "chapter_plan": [],  # Force Researcher to rebuild chapter structure
                                        "current_chapter_index": 0,
                                        "approved_chapters": [],
                                        "critique_feedback": f"STRUCTURE_RESET: The chapter plan was flawed. Generate a new chapter plan from scratch that better addresses: {previous_feedback[:500]}",
                                        "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                                        "messages": [HumanMessage(content=f"🏗️ **SUPERVISOR: CHAPTER STRUCTURE RESET** 🏗️\nThe current chapter plan has a structural problem causing repeated failures. Create a completely new chapter plan.")]
                                    }
                                else:
                                    # DATA GAP → Route to DEEP_RESEARCHER
                                    print(f"🔍 Diagnosis: DATA GAP. Routing to DEEP_RESEARCHER for additional research.")
                                    save_artifact(critique_filename, f"# 🔍 Supervisor Smart Diagnosis: DATA GAP\n\n**Recurring Issue ({consecutive_same}x):** {previous_feedback[:500]}\n\n**Diagnosis:** Insufficient source data. Routing to Deep Researcher for additional material.", "md", thread_id=thread_id)
                                    return {
                                        "next": "DEEP_RESEARCHER",
                                        "sender": "Supervisor",
                                        "iteration_count": step_iterations,  # v10.6: Don't increment — data gap is not Researcher's fault
                                        "_consecutive_same_critique": 0,
                                        "research_mode": "deep",
                                        "research_topic": state.get("research_topic", chap_title),
                                        "critique_feedback": f"DATA_GAP: The writer needs more source material. Searching for: {previous_feedback[:300]}",
                                        "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                                        "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                                        "current_chapter_index": state.get('current_chapter_index', 0),
                                        "approved_chapters": state.get("approved_chapters", []),
                                        "messages": [HumanMessage(content=f"🔍 **SUPERVISOR: DATA GAP DETECTED** 🔍\nRouting to Deep Researcher for additional data collection on: {chap_title}")]
                                    }
                            except Exception as e:
                                print(f"⚠️ Smart Diagnosis Failed: {e}. Falling back to coaching intervention.")
                                # Fallback: Original coaching intervention
                                intervention_prompt = f"""
                                **COACHING INTERVENTION MODE (EARLY - STUCK DETECTION)**
                                The subordinate has submitted 3+ drafts with the SAME unfixed issue on Chapter {curr_chap_idx+1}: "{chap_title}".
                                The recurring problem: {previous_feedback[:1000]}
                                Rewrite the content to fix this persistent issue. Output ONLY the fixed chapter content.
                                - YOU MUST WRITE IN ENGLISH ONLY. Do NOT use any other language.
                                Original Goal: {messages[0].content[:2000]}
                                Current Draft: {last_output[:25000]}
                                """
                                try:
                                    fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                                    fixed_content = extract_text_content(fix_response)
                                    return {
                                        "next": effective_worker,
                                        "iteration_count": step_iterations + 1,
                                        "_consecutive_same_critique": 0,
                                        "shared_knowledge": str(fixed_content),
                                        "critique_feedback": f"I have rewritten Chapter {curr_chap_idx+1} to fix the recurring issue. Use this as baseline.",
                                        "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                                        "current_chapter_index": state.get('current_chapter_index', 0),
                                        "approved_chapters": state.get("approved_chapters", []),
                                        "sub_plan": state.get("sub_plan", []),
                                        "messages": [HumanMessage(content=f"🚨 **SUPERVISOR EARLY INTERVENTION (Stuck Detection)** 🚨\nYou submitted 3+ drafts with the same issue. I fixed it. Review and finalize.")]
                                    }
                                except Exception as e2:
                                    print(f"⚠️ Early Stuck Intervention Failed: {e2}.")
                    else:
                        consecutive_same = 0
                except Exception as e:
                    print(f"⚠️ Similarity check failed: {e}. Skipping.")
                    consecutive_same = 0
            
            # Level 2: Hard Intervention (Force Success) -> 15+ attempts (v6.0: lowered from 30)
            if step_iterations >= 15:
                print(f"🔥 Supervisor Hard Intervention (Attempt {step_iterations}). Commissioning Final Draft.")
                save_artifact(critique_filename, f"# 🔥 Supervisor HARD INTERVENTION (Attempt {step_iterations})\n\n**Action:** Force-writing final chapter draft.\n**Reason:** {step_iterations} failed attempts exceeded maximum tolerance.", "md", thread_id=thread_id)
                curr_chap_idx = state.get('current_chapter_index', 0)
                chap_plan = state.get('chapter_plan', [])
                chap_title = chap_plan[curr_chap_idx].get('title', 'Unknown Chapter') if curr_chap_idx < len(chap_plan) else "Current Chapter"
                
                force_prompt = f"""
                **FINAL EMERGENCY OVERRIDE**
                The subordinate has failed {step_iterations} times on Chapter {curr_chap_idx+1}: "{chap_title}".
                YOU MUST WRITE THE FINAL, PRODUCTION-READY VERSION OF THIS CHAPTER.
                
                **Goal:** {messages[0].content[:2000]}
                **Target:** CHAPTER {curr_chap_idx+1}: {chap_title}
                
                **Requirements:**
                - Absolute technical accuracy and addressing all critiques.
                - Output ONLY the final chapter text.
                - YOU MUST WRITE IN ENGLISH ONLY. Do NOT use any other language.
                """
                
                try:
                    fix_response = llm_pro.invoke([HumanMessage(content=force_prompt)])
                    fixed_content = extract_text_content(fix_response)
                    
                    # Force approve this chapter and move to next
                    approved_chaps = state.get('approved_chapters', []) or []
                    approved_chaps.append(str(fixed_content))
                    
                    # Log for artifact
                    save_artifact(f"Step{current_index+1}_Sub{current_sub_index+1}_ForceChapter{curr_chap_idx+1}", fixed_content, "md", thread_id=thread_id)
                    
                    next_chap = curr_chap_idx + 1
                    
                    # v5.6 BOUNDS CHECK: If all chapters are now done, assemble and advance
                    if next_chap >= len(chap_plan):
                        print(f"🎉 All {len(chap_plan)} chapters complete (including forced). Assembling and advancing.")
                        
                        active_sub = sub_plan[current_sub_index] if (sub_plan and current_sub_index < len(sub_plan)) else plan[current_index]
                        sub_title = active_sub.get('title', 'Unknown Topic')
                        full_report = f"# Step {current_index+1}.{current_sub_index+1}: {sub_title}\n\n"
                        for ch_text in approved_chaps:
                            full_report += f"\n\n{ch_text}\n\n"
                        save_artifact(f"step{current_index+1}_sub{current_sub_index+1}_report_final", full_report, "md", thread_id=thread_id)
                        
                        # Append to master report
                        # incremental_path = state.get('incremental_report_path', '') # REMOVED: Do not overwrite local variable
                        if incremental_path and os.path.exists(incremental_path):
                            try:
                                with open(incremental_path, "a", encoding="utf-8") as f:
                                    f.write(f"\n\n{full_report}\n\n---\n\n")
                            except Exception as e:
                                print(f"⚠️ Master Report Append Error: {e}")
                        
                        sub_plan = state.get("sub_plan", [])
                        total_subs = len(sub_plan) if isinstance(sub_plan, list) else 0
                        if total_subs > 0 and current_sub_index < total_subs - 1:
                            return {
                                "next": "SUPERVISOR",
                                "current_sub_step_index": current_sub_index + 1,
                                "current_chapter_index": 0,
                                "approved_chapters": [],
                                "chapter_plan": [],
                                "sub_plan": sub_plan,  # v6.4: Preserve sub_plan
                                "iteration_count": 0,
                                "critique_feedback": "",
                                "shared_knowledge": f"Deep Report:\n{full_report}",
                                "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} FORCE-COMPLETED. Moving to Sub-Step {current_sub_index+2}.")]
                            }
                        else:
                            return {
                                "next": "SUPERVISOR",
                                "current_step_index": current_index + 1,
                                "current_sub_step_index": 0,
                                "current_chapter_index": 0,
                                "approved_chapters": [],
                                "chapter_plan": [],
                                "sub_plan": [],
                                "iteration_count": 0,
                                "shared_knowledge": f"Deep Report:\n{full_report}",
                                "messages": [SystemMessage(content=f"Main Step {current_index+1} FORCE-COMPLETED. Moving to Step {current_index+2}.")]
                            }
                    else:
                        # More chapters remain
                        return {
                            "next": "RESEARCHER",
                            "current_chapter_index": next_chap,
                            "approved_chapters": approved_chaps,
                            "chapter_plan": chap_plan, # v12.2 Explicit Persistence
                            "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                            "iteration_count": 0,
                            "critique_feedback": "",
                            "messages": [SystemMessage(content=f"⚠️ Chapter {curr_chap_idx+1} force-approved. Now write Chapter {next_chap+1}.")]
                        }
                except Exception as e:
                    print(f"⚠️ Hard Intervention Failed: {e}. Moving on.")

            # ===== v6.5 FIX: Targeted Soft Intervention =====
            # Instead of a destructive total rewrite, the Supervisor acts as a precision editor.
            # It explicitly preserves the Researcher's deep context and ONLY fixes the flagged issues.
            elif step_iterations in [5, 10]:
                print(f"⚠️ Supervisor Soft Intervention (Attempt {step_iterations}).")
                save_artifact(critique_filename, f"# ⚠️ Supervisor SOFT INTERVENTION (Attempt {step_iterations})\n\n**Action:** Precision editing of chapter draft.\n**Reason:** Writer struggling after {step_iterations} attempts. Preserving context while fixing specific flagged errors.", "md", thread_id=thread_id)
                curr_chap_idx = state.get('current_chapter_index', 0)
                chap_plan = state.get('chapter_plan', [])
                chap_title = chap_plan[curr_chap_idx].get('title', 'Unknown Chapter') if curr_chap_idx < len(chap_plan) else "Current Chapter"
                
                # We need the previous critique to know WHAT to fix
                prev_critique = state.get('critique_feedback', 'No specific critique provided.')
                
                intervention_prompt = f"""
                **PRECISION EDITING INTERVENTION MODE**
                The subordinate researcher is struggling to address the feedback for Chapter {curr_chap_idx+1}: "{chap_title}".
                
                **CRITICAL RULES:**
                1. DO NOT rewrite the entire document from scratch.
                2. PRESERVE the existing structure, depth, citations, and valuable research context.
                3. ONLY modify the specific sentences, formatting, or sections necessary to resolve the feedback.
                4. Output the FULL, corrected chapter content markdown.
                
                **Previous Rejection Reason (What needs fixing):**
                {prev_critique}
                
                **Subordinate's Current Draft (Preserve this as much as possible):**
                {last_output[:30000]}
                """
                try:
                    fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                    fixed_content = extract_text_content(fix_response)
                    
                    # v10.6: Route back to SUPERVISOR for self-evaluation (not to Researcher!)
                    # This mirrors the Early Stuck Intervention pattern.
                    # Gemini Pro's fix should be critiqued directly — if good, approve immediately.
                    save_artifact(f"Step{current_index+1}_Sub{current_sub_index+1}_SoftFix_v{step_iterations}", fixed_content, "md", thread_id=thread_id)
                    print(f"✅ Soft Intervention draft ready ({len(str(fixed_content))} chars). Routing to self for critique.")
                    save_dialogue_message(thread_id, "Supervisor", f"🔧 Soft Intervention complete. Now self-evaluating the fixed draft before deciding next step.")
                    
                    updates = {
                        "sender": "Researcher",  # Pretend Researcher sent it so Supervisor re-critiques
                        "next": "SUPERVISOR",     # Loop back to Supervisor for critique
                        "iteration_count": step_iterations + 1,
                        "sub_plan": state.get("sub_plan", []),  # v6.4: CRITICAL - Preserve sub_plan
                        "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                        "current_chapter_index": state.get('current_chapter_index', 0),
                        "approved_chapters": state.get("approved_chapters", []),
                        "critique_feedback": "",  # Clear old critique — fresh evaluation
                        "gemma_fail_count": 0,     # Reset pre-critique counter
                        "shared_knowledge": str(fixed_content),
                        "messages": [SystemMessage(content=f"🔧 Soft Intervention Complete. Gemini Pro has precision-edited Chapter {curr_chap_idx+1}. Please critique this version.")]
                    }
                    return updates
                except Exception as e:
                    print(f"⚠️ Soft Intervention Failed: {e}.")

            # ===== v5.7: LOCAL PRE-CRITIQUE GUARD (Gemma3 32B on RTX 5090) =====
            # Before burning Gemini Pro quota, Gemma does a fast structural check.
            # Gemma NEVER writes content — it only classifies PASS/FAIL on a checklist.
            # v6.3: Circuit breaker — skip Gemma after 3 consecutive failures to prevent infinite loops
            gemma_fails = state.get('gemma_fail_count', 0)
            
            if gemma_fails >= 3:
                print(f"⚡ Gemma Circuit Breaker ACTIVE: {gemma_fails} consecutive failures. Bypassing Gemma → Gemini Pro directly.")
                save_artifact(critique_filename, f"# ⚡ Gemma Circuit Breaker\n\n**Consecutive Gemma Failures:** {gemma_fails}\n\n**Action:** Bypassing Gemma pre-critique, sending directly to Gemini Pro for full review.", "md", thread_id=thread_id)
            else:
              try:
                from langchain_ollama import ChatOllama
                local_guard = ChatOllama(
                    model=os.getenv("LOCAL_LLM_MODEL", "qwen3:32b"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                    temperature=0.0,
                    timeout=120
                )
                
                curr_chap_idx = state.get('current_chapter_index', 0)
                chap_plan = state.get('chapter_plan', [])
                chap_title = chap_plan[curr_chap_idx].get('title', 'Chapter') if curr_chap_idx < len(chap_plan) else "Current Chapter"
                
                # v6.4 FIX: Gemma ONLY checks trivially fixable formatting issues.
                # REMOVED: SCOPE check (false positives), CONSISTENCY check (too ambitious).
                # Gemma now checks ONLY surface-level formatting that Researcher can instantly fix.
                
                guard_prompt = f"""/no_think
**ROLE: FORMAT CHECKER (Classification Only)**
You are a formatting checker. You do NOT judge content quality or topic relevance.
Output exactly ONE line: "PASS" or "FAIL: [reason]"

**CHECK ONLY THESE 3 ITEMS:**
1. BROKEN FORMATTING: Are there broken markdown elements (e.g., unclosed code blocks, malformed tables, garbled LaTeX)?
2. DUPLICATE NUMBERING: Are there duplicate section numbers (e.g., two "Section 3" or two "## 1.2")?
3. EMPTY SECTIONS: Are there section headers with NO content below them (completely empty)?

**IMPORTANT RULES:**
- Do NOT check topic relevance or scope. That is not your job.
- Do NOT check for factual accuracy or citations. That is not your job.
- If the document is readable and well-formatted, output PASS.
- Only output FAIL if there is a clear, objective formatting error.

**DRAFT TO CHECK:**
{last_output[:8000]}

**OUTPUT (one line only):**"""
                
                guard_response = local_guard.invoke([HumanMessage(content=guard_prompt)])
                guard_result = extract_text_content(guard_response).strip().split('\n')[0].strip()
                print(f"🛡️ Gemma Pre-Critique: {guard_result}")
                
                if guard_result.upper().startswith("FAIL"):
                    # v6.3: Circuit breaker — if Gemma fails 3+ times, bypass and go to Gemini Pro
                    if gemma_fails >= 2:
                        print(f"🛡️ Gemma FAIL STREAK ({gemma_fails + 1}/3) — CIRCUIT BREAKER: Bypassing Gemma, proceeding to Gemini Pro critique.")
                        save_dialogue_message(thread_id, "Gemma (QC)", f"⚡ Gemma Fail Streak {gemma_fails + 1}/3 hit circuit breaker. Bypassing format check and forwarding to Gemini Pro.")
                        # Fall through to Gemini Pro critique below (do NOT return)
                    else:
                        # Normal Gemma rejection path — return to researcher for quick fix
                        print(f"🛡️ Gemma REJECTED (saving Gemini Pro quota). Reason: {guard_result}")
                        save_dialogue_message(thread_id, "Gemma (QC)", f"🛡️ Format check **FAILED**: {guard_result}. Sending back for quick fix. (Streak: {gemma_fails + 1}/3)")
                        feedback = f"PRE-SCREENING FAILURE: {guard_result}. This is a minor structural issue. Fix it quickly and resubmit."
                        save_artifact(critique_filename, f"# 🛡️ Gemma Pre-Critique: REJECTED (Minor Fix)\n\n**Reason:** {guard_result}\n\n**Action:** Sent back to {effective_worker} for quick fix. Iteration NOT incremented.\n\n**Gemma Fail Streak:** {gemma_fails + 1}/3", "md", thread_id=thread_id)
                        return {
                            "sender": "Supervisor",
                            "next": effective_worker,
                            "iteration_count": step_iterations,  # v6.3: Do NOT increment — minor fix cycle
                            "gemma_fail_count": gemma_fails + 1,   # v6.3: Track for circuit breaker
                            "critique_feedback": feedback,
                            "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                            "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                            "current_chapter_index": state.get('current_chapter_index', 0),
                            "approved_chapters": state.get("approved_chapters", []),
                            "messages": [HumanMessage(content=f"🛡️ **PRE-SCREENING FAILED (Quick Fix {gemma_fails + 1}/3)**\n\n{guard_result}\n\nThis is a minor issue. Fix it and resubmit immediately.")]
                        }
                # else: PASS → proceed to Gemini Pro for detailed critique
                print(f"🛡️ Gemma PASSED. Proceeding to Gemini Pro for detailed critique.")
                save_dialogue_message(thread_id, "Gemma (QC)", "✅ Format check **PASSED**. Forwarding to Gemini Pro for detailed review.")
                    
              except Exception as guard_err:
                print(f"⚠️ Gemma Guard unavailable: {guard_err}. Proceeding directly to Gemini Pro.")

            # Regular Critique Path (Gemini Pro — only reached if Gemma PASS or unavailable)
            response = llm_pro.invoke([HumanMessage(content=critique_prompt)])
            review_result = extract_text_content(response).strip()
            save_artifact(critique_filename, f"# 🕵️ Supervisor Critique\n\n**Verdict**: {review_result}\n\n## Reviewed Content\n{last_output[:2000]}...", "md", thread_id=thread_id)
            
            # --- EARLY INTERVENTION LOGIC (Repetition Check) ---
            # v12.1: Only trigger after at least 2 rejected attempts. On the first critique, nothing can be "repeated".
            if review_result.startswith("REPEAT_FAILURE") and step_iterations >= 2:
                print(f"⚠️ Repeated Failure Detected (Attempt {step_iterations}). Triggering IMMEDIATE Intervention.")
                
                # v13.0: Add Reference Registry rules to Supervisor Intervention
                registry = state.get('verified_reference_registry', [])
                registry_str = ""
                for r in registry[-20:]:  # Pass recent registry items
                    registry_str += f"- [{r['ref_id']}] {r['type'].upper()}: {r['title']}\n"
                
                intervention_prompt = f"""
                **COACHING INTERVENTION MODE (EARLY TRIGGER)**
                The subordinate is STUCK and ignoring feedback.
                You, the Mentor, must **REWRITE THE DRAFT** yourself to break the loop.
                
                **Original Goal:** {messages[0].content[:5000]}
                **Previous Feedback:** {previous_feedback}
                **Current Draft:** {last_output[:20000]}
                
                **AVAILABLE REFERENCES (MUST USE THESE EXACT IDs):**
                {registry_str}
                
                **TASK:**
                - Rewrite the content to fix the persistent error (e.g. add the missing math).
                - Output ONLY the fixed content.
                - YOU MUST WRITE IN ENGLISH ONLY. Do NOT use any other language.
                - **CRITICAL CITATION RULE**: You MUST ONLY cite using the [REF-XXX] format provided above. NEVER use formats like [File: ...] or [Web: ...].
                """
                
                try:
                    fix_response = llm_pro.invoke([HumanMessage(content=intervention_prompt)])
                    fixed_content = extract_text_content(fix_response)
                    
                    # ===== v13.0: REGISTRY-BASED CITATION GUARD (Supervisor Intervention) =====
                    import re
                    valid_ref_ids = {r.get('ref_id') for r in registry if r.get('ref_id')}
                    
                    # 1. Guard [REF-XXX]
                    for ref_id in set(re.findall(r'(REF-\d{3})', fixed_content)):
                        if ref_id not in valid_ref_ids:
                            fixed_content = fixed_content.replace(f'[{ref_id}]', '')
                            
                    # 2. Strip legacy format
                    for lt in ['File', 'Web', 'Paper', 'Patent', 'File✓', 'Web✓', 'Paper✓', 'Patent✓']:
                        for lf in re.findall(rf'\[{lt}:\s*[^\]]*\]', fixed_content):
                            fixed_content = fixed_content.replace(lf, '')
                            
                    # 3. Strip unverified URLs
                    registry_urls = {r['url'].strip().lower().rstrip('/#?') for r in registry if r.get('url')}
                    urls_in_md = re.findall(r'(\[.*?\])\((https?://[^\s\)]+)\)', fixed_content)
                    if urls_in_md:
                        for text_part, url_part in set(urls_in_md):
                            url_clean = url_part.strip().lower().rstrip('/#?')
                            if 'example.com' in url_clean: continue
                            if not any(url_clean.startswith(wu) or wu.startswith(url_clean) for wu in registry_urls):
                                fixed_content = fixed_content.replace(f"{text_part}({url_part})", f"{text_part}(Link_Unverified)")
                                
                    # 4. Rebuild References section
                    fixed_content = re.sub(r'\n##\s*References?\n.*', '', fixed_content, flags=re.DOTALL)
                    cited_ref_ids = sorted(set(re.findall(r'(REF-\d{3})', fixed_content)))
                    if cited_ref_ids:
                        ref_section = "\n\n## References\n\n"
                        for ref_id in cited_ref_ids:
                            ref = next((r for r in registry if r.get('ref_id') == ref_id), None)
                            if ref:
                                if ref.get('type') == 'web': ref_section += f"- [{ref_id}] Web: [{ref.get('title')}]({ref.get('url', '#')})\n"
                                elif ref.get('type') == 'paper': ref_section += f"- [{ref_id}] Paper: {ref.get('title')}\n"
                                elif ref.get('type') == 'patent': ref_section += f"- [{ref_id}] Patent: {ref.get('patent_id', '')} — {ref.get('title')}\n"
                                elif ref.get('type') == 'file': ref_section += f"- [{ref_id}] File: {ref.get('title')}\n"
                        fixed_content += ref_section
                    # ==========================================================================
                    
                    # v10.1: Gemini Pro's rewrite goes DIRECTLY to critique (skip Writer re-write)
                    # Save the fixed draft as an artifact immediately
                    chapter_version = step_iterations + 1
                    chap_artifact_name = f"Step{current_index+1}_Sub{current_sub_index+1}_Ch{state.get('current_chapter_index', 0)+1}_v{chapter_version}"
                    save_artifact(chap_artifact_name, str(fixed_content), "md", thread_id=thread_id)
                    print(f"⚠️ Supervisor COACHING: Gemini Pro rewrote draft → saved as {chap_artifact_name}. Sending directly to critique (no Writer re-write).")
                    save_dialogue_message(thread_id, "Supervisor (Coach)", f"📝 Coaching Intervention: Rewrote chapter draft directly. Sending to critique cycle (skipping Writer).")
                    
                    updates = {
                        "sender": "Researcher",  # Pretend Researcher sent it so Supervisor re-critiques
                        "next": "SUPERVISOR",     # Loop back to Supervisor for critique
                        "iteration_count": chapter_version,
                        "critique_feedback": "",  # Clear old critique — fresh evaluation
                        "gemma_fail_count": 0,     # Reset pre-critique counter
                        "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                        "current_chapter_index": state.get('current_chapter_index', 0),
                        "approved_chapters": state.get("approved_chapters", []),
                        "messages": [SystemMessage(content=f"🚨 Coaching Intervention Complete. Gemini Pro has rewritten the draft. Please critique this version.")]
                    }
                    
                    if assigned_to in ["RESEARCHER", "DEEP_RESEARCHER"]:
                        updates["shared_knowledge"] = str(fixed_content)
                    elif assigned_to == "ARCHITECT":
                        updates["slide_code"] = {1: str(fixed_content)} 
                    return updates

                except Exception as e:
                    print(f"⚠️ Early Intervention Failed: {e}. Falling back to standard rejection.")
                    # Fallthrough to standard rejection if intervention fails
            
            # --- DYNAMIC REDIRECTION (Autonomous Deep Research) ---
            if "🚨 DEEP_RESEARCH_REQUIRED" in str(last_output) or review_result.startswith("DEEP_RESEARCH_REQUIRED"):
                print(f"📡 Help Signal Detected or Supervisor Requested Deep Research. Redirecting to DEEP_RESEARCHER (Support Role).")
                save_artifact(critique_filename, f"# 📡 Supervisor: DEEP RESEARCH REDIRECT\n\n**Verdict:** {review_result[:1000]}\n\n**Action:** Routing to Deep Researcher for supplemental data collection.", "md", thread_id=thread_id)
                
                # Update feedback to guide the Deep Researcher
                feedback = review_result.replace("DEEP_RESEARCH_REQUIRED:", "").strip()
                if not feedback:
                    feedback = "The Lead Researcher requested technical supplementation. Perform a deep web/academic dive to find formulas, code, or specific technical specs. DO NOT draft the final report; provide raw/summarized data to the Lead Researcher."
                
                return {
                    "sender": "Supervisor",
                    "next": "DEEP_RESEARCHER",
                    "research_topic": current_sub_step.get('description', current_sub_step.get('title', 'Unknown')),
                    # v3.11: FORCE Web Research Mode. If Supervisor asks for help, it means local data is not enough.
                    "research_mode": "deep_web",
                    "iteration_count": step_iterations,  # v10.6: Don't increment — requesting external research is not a failed attempt
                    "critique_feedback": feedback,
                    "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                    "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                    "current_chapter_index": state.get('current_chapter_index', 0),
                    "approved_chapters": state.get("approved_chapters", []),
                    "messages": [HumanMessage(content=f"🚨 **AUTONOMOUS REDIRECTION: TECHNICAL SUPPORT** 🚨\n\nTechnical gaps detected. {assigned_to} (Lead Researcher) requires supplemental data. DeepResearcher, find the missing technical specifics and pass them back for synthesis.")]
                }

            if review_result.startswith("APPROVED"):
                # --- v5.4 CHAPTER-LEVEL APPROVAL ---
                chapter_plan = state.get('chapter_plan', [])
                current_chapter_idx = state.get('current_chapter_index', 0)
                approved_chapters = list(state.get('approved_chapters', []) or [])
                
                # Failsafe: if LangGraph dropped chapter_plan but we are approving a chapter
                if not chapter_plan or len(chapter_plan) == 0:
                    print(f"⚠️ WARNING: chapter_plan is empty! Recovering state for last_output assembly.")
                    # Force it to think it's a 1-chapter plan
                    chapter_plan = [{"title": "Analysis Report"}]
                    current_chapter_idx = 0
                
                if chapter_plan and current_chapter_idx < len(chapter_plan):
                    # We're in chapter-by-chapter mode
                    # Lock this chapter and move to next
                    approved_chapters.append(last_output)
                    next_chapter_idx = current_chapter_idx + 1
                    
                    if next_chapter_idx < len(chapter_plan):
                        # More chapters remain — route back to RESEARCHER for next chapter
                        print(f"✅ Chapter {current_chapter_idx+1}/{len(chapter_plan)} Approved! Moving to Chapter {next_chapter_idx+1}.")
                        return {
                            "sender": "Supervisor",
                            "next": effective_worker,  # Back to RESEARCHER (or original assigned_to)
                            "current_chapter_index": next_chapter_idx,
                            "approved_chapters": approved_chapters,
                            "chapter_plan": chapter_plan,
                            "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan across chapter transitions
                            "iteration_count": 0,  # Reset iteration for new chapter
                            "critique_feedback": "",  # Clear critique for fresh chapter
                            "messages": [SystemMessage(content=f"✅ Chapter {current_chapter_idx+1} APPROVED and locked. Now write Chapter {next_chapter_idx+1}: '{chapter_plan[next_chapter_idx].get('title', 'Unknown')}'.")]
                        }
                    else:
                        # ALL chapters approved — DIRECTLY assemble and advance (v5.6)
                        # DO NOT re-route to Researcher. Assemble here and skip to next sub-step.
                        print(f"🎉 ALL {len(chapter_plan)} chapters approved! Assembling final report directly.")
                        
                        # Assemble by concatenating approved chapters
                        active_sub = sub_plan[current_sub_index] if (sub_plan and current_sub_index < len(sub_plan)) else plan[current_index]
                        sub_title = active_sub.get('title', 'Research Report')
                        clean_title = f"Step {current_index+1}.{current_sub_index+1}: {sub_title}"
                        full_report = f"# {clean_title}\n\n"
                        for ch_idx, ch_text in enumerate(approved_chapters):
                            full_report += f"\n\n{ch_text}\n\n"
                        
                        # Save artifact
                        from app.utils import save_artifact
                        report_filename = f"step{current_index+1}_sub{current_sub_index+1}_report_final"
                        save_artifact(report_filename, full_report, "md", thread_id=thread_id)
                        print(f"✅ Final Report saved: {report_filename}")
                        
                        # Append to Master Report
                        # incremental_path = state.get('incremental_report_path', '') # REMOVED: Do not overwrite local variable
                        results_dir = state.get('results_dir', '')
                        if incremental_path and os.path.exists(incremental_path):
                            try:
                                sub_plan = state.get("sub_plan", [])
                                sub_step_title = sub_plan[current_sub_index]['title'] if sub_plan and current_sub_index < len(sub_plan) else current_step.get('title', '')
                                with open(incremental_path, "a", encoding="utf-8") as f:
                                    f.write(f"## 📍 Step {current_index+1}.{current_sub_index+1}: {sub_step_title}\n\n")
                                    f.write(f"{full_report}\n\n---\n\n")
                                print(f"📝 Appended to Master Report: {incremental_path}")
                            except Exception as e:
                                print(f"⚠️ Failed to append to master report: {e}")
                        
                        # Determine next destination
                        sub_plan = state.get("sub_plan", [])
                        total_subs = len(sub_plan) if isinstance(sub_plan, list) else 0
                        print(f"🔍 DEBUG sub_plan check: total_subs={total_subs}, current_sub_index={current_sub_index}, sub_plan_type={type(sub_plan).__name__}, sub_plan_len={len(sub_plan) if sub_plan else 0}")
                        if total_subs > 0:
                            print(f"🔍 DEBUG sub_plan titles: {[s.get('title','?') for s in sub_plan[:5]]}")
                        
                        if total_subs > 0 and current_sub_index < total_subs - 1:
                            # Move to next sub-step
                            print(f"👉 Advancing to Sub-Step {current_sub_index+2}/{total_subs}")
                            return {
                                "sender": "Supervisor",
                                "next": "SUPERVISOR",
                                "current_sub_step_index": current_sub_index + 1,
                                "current_step_index": current_index, # FORCE MAINTAIN CURRENT MAIN STEP
                                "current_chapter_index": 0,
                                "approved_chapters": [],
                                "chapter_plan": [],
                                "iteration_count": 0,
                                "critique_feedback": "",
                                "sub_plan": sub_plan,  # v6.4: Explicitly preserve sub_plan
                                "shared_knowledge": f"Deep Report:\n{full_report}",
                                "incremental_report_path": incremental_path,
                                "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} COMPLETE (all chapters approved). Moving to Sub-Step {current_sub_index+2}.")]
                            }
                        elif total_subs > 1 and current_sub_index == 0:
                            # v11.0 FAILSAFE: If total_subs > 1 but we somehow evaluated false above, force it statically
                            print(f"⚠️ [Failsafe Triggered] Forcing Sub-Step Advance (Index {current_sub_index} -> 1) because total_subs={total_subs}")
                            return {
                                "sender": "Supervisor",
                                "next": "SUPERVISOR",
                                "current_sub_step_index": current_sub_index + 1,
                                "current_step_index": current_index,
                                "current_chapter_index": 0,
                                "approved_chapters": [],
                                "chapter_plan": [],
                                "iteration_count": 0,
                                "critique_feedback": "",
                                "sub_plan": sub_plan,
                                "shared_knowledge": f"Deep Report:\n{full_report}",
                                "incremental_report_path": incremental_path,
                                "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} COMPLETE (all chapters approved). Moving to Sub-Step {current_sub_index+2}.")]
                            }
                        else:
                            # Move to next main step
                            print(f"👉 All sub-steps done. Advancing to Main Step {current_index+2}")
                            return {
                                "sender": "Supervisor",
                                "next": "SUPERVISOR",
                                "current_step_index": current_index + 1,
                                "current_sub_step_index": 0,
                                "current_chapter_index": 0,
                                "approved_chapters": [],
                                "chapter_plan": [],
                                "sub_plan": [],
                                "iteration_count": 0,
                                "critique_feedback": "",
                                "shared_knowledge": f"Deep Report:\n{full_report}",
                                "incremental_report_path": incremental_path,
                                "messages": [SystemMessage(content=f"Main Step {current_index+1} COMPLETE. All sub-steps and chapters approved. Moving to Step {current_index+2}.")]
                            }
                
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
                step_report_path = ""
                try:
                    current_sub_step = sub_plan[current_sub_index] if sub_plan else plan[current_index]
                    
                    # 1. Save Individual Step Report (User Request)
                    sanitized_title = re.sub(r'[\\/*?:"<>| ]', '_', current_sub_step['title'])
                    step_filename = f"Step_{current_index+1}_Sub_{current_sub_index+1}_{sanitized_title}.md"
                    step_report_path = os.path.join(results_dir, step_filename)
                    
                    with open(step_report_path, "w", encoding="utf-8") as f:
                        f.write(f"# 📍 Step {current_index+1}.{current_sub_index+1}: {current_sub_step['title']}\n\n")
                        f.write(f"**Goal**: {current_sub_step['description']}\n\n")
                        f.write(f"{last_output}\n\n")
                    print(f"📄 Saved Individual Report: {step_report_path}")

                    # 2. Append to Master Report
                    with open(incremental_path, "a", encoding="utf-8") as f:
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
                        "current_step_index": current_index, # FORCE MAINTAIN CURRENT MAIN STEP
                        "current_chapter_index": 0,      # Reset for new sub-step
                        "approved_chapters": [],         # Clear locks
                        "chapter_plan": [],              # v12.2: Reset for new sub-step
                        "sub_plan": state.get("sub_plan", []), # v6.4: Preserve sub_plan
                        "cached_master_fact_sheet": "",  # v13.1: Clear fact sheet for new sub-step
                        "verified_reference_registry": state.get("verified_reference_registry", []), # Fix: Preserve globally
                        "deep_research_sources": [],     # v13.1: Clear deep sources for new sub-step
                        "iteration_count": 0,
                        "incremental_report_path": incremental_path,
                        "last_completed_step_path": step_report_path,
                        "critique_feedback": "",
                        "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} Passed. Moving to Sub-Step {current_sub_index+2}.")]
                    }
                elif sub_plan and len(sub_plan) > 1 and current_sub_index == 0:
                    print(f"⚠️ [Failsafe Triggered] Forcing Main Advance (Index {current_sub_index} -> 1)")
                    return {
                        "sender": "Supervisor",
                        "next": "SUPERVISOR",
                        "current_sub_step_index": current_sub_index + 1,
                        "current_step_index": current_index,
                        "current_chapter_index": 0,
                        "approved_chapters": [],
                        "chapter_plan": [],              # v12.2: Reset for new sub-step
                        "sub_plan": state.get("sub_plan", []),
                        "cached_master_fact_sheet": "",  # v13.1: Clear fact sheet for new sub-step
                        "verified_reference_registry": state.get("verified_reference_registry", []), # Fix: Preserve globally
                        "deep_research_sources": [],     # v13.1: Clear deep sources for new sub-step
                        "iteration_count": 0,
                        "incremental_report_path": incremental_path,
                        "last_completed_step_path": step_report_path,
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
                    "current_chapter_index": 0,      # Reset for new main step
                    "approved_chapters": [],         # Clear locks
                    "chapter_plan": [],              # v12.2: Reset for new main step
                    "sub_plan": [], 
                    "cached_master_fact_sheet": "",  # v13.1: Clear fact sheet for new step
                    "verified_reference_registry": state.get("verified_reference_registry", []), # Fix: Preserve globally
                    "deep_research_sources": [],     # v13.1: Clear deep sources for new step
                    "iteration_count": 0, # Reset for next step
                    "incremental_report_path": incremental_path,
                    "last_completed_step_path": step_report_path,
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
                            "current_chapter_index": 0,
                            "approved_chapters": [],
                            "chapter_plan": [],
                            "sub_plan": state.get("sub_plan", []),  # v6.4: CRITICAL - Preserve sub_plan
                            "iteration_count": 0,
                            "critique_feedback": f"TIMEOUT: User did not provide document in 1hr. Proceeding with best available data. DO NOT ask for this file again. (Ref: {current_sub_step_index+1})",
                            "messages": [SystemMessage(content=f"Sub-step {current_sub_index+1} Force-Approved due to user inactivity (1hr timeout). Proceeding autonomously.")]
                        }
                
                print(f"❌ Step Rejected. Sending back to {effective_worker}.")
                return {
                    "sender": "Supervisor",
                    "next": effective_worker,
                    "iteration_count": step_iterations + 1,
                    "gemma_fail_count": 0,  # v6.3: Reset after Gemini Pro full review
                    "critique_feedback": review_result, # Explicitly pass critique state
                    "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                    "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                    "current_chapter_index": state.get('current_chapter_index', 0),
                    "approved_chapters": state.get("approved_chapters", []),
                    "_topic_type_cache": _topic_cache,  # v10.7: Persist topic classification
                    "messages": [HumanMessage(content=f"🚨 **SUPERVISOR REJECTED YOUR WORK** 🚨\n\n{review_result}\n\nExisting content was insufficient. Refine it or restart deep research.")]
                }
            else:
                # --- v3.11 SAFETY FALLBACK: If verdict is unclear, assume REJECTION to prevent infinite loops ---
                print(f"⚠️ Unclear Verdict from Supervisor: '{review_result[:50]}...'. Assuming REJECTED to force progress.")
                save_artifact(critique_filename, f"# ⚠️ Supervisor: UNCLEAR VERDICT (Assumed REJECT)\n\n**Raw Verdict:** {review_result[:1000]}\n\n**Action:** Treating as rejection to prevent stall.", "md", thread_id=thread_id)
                return {
                    "sender": "Supervisor",
                    "next": effective_worker,
                    "iteration_count": step_iterations + 1,
                    "sub_plan": state.get("sub_plan", []),  # v6.4: Preserve sub_plan
                    "chapter_plan": state.get("chapter_plan", []), # v12.2 Explicit Persistence
                    "current_chapter_index": state.get('current_chapter_index', 0),
                    "approved_chapters": state.get("approved_chapters", []),
                    "_topic_type_cache": _topic_cache,  # v10.7: Persist topic classification
                    "critique_feedback": f"VERDICT_UNCLEAR: The Chief Editor didn't give a clear APPROVED/REJECTED signal. Review the following notes and refine: {review_result}",
                    "messages": [HumanMessage(content=f"🚨 **SUPERVISOR UNCERTAIN** 🚨\n\nThe verdict was unclear. Re-evaluating and refining the draft (Iteration {step_iterations+1}).")]
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
                "sub_plan": sub_plan,  # v6.4: CRITICAL - Preserve sub_plan across delegation
                "messages": [SystemMessage(content=f"Sub-Step {current_sub_index+1} 시작: {active_step['title']}")]
            }

    except Exception as e:
        print(f"⚠️ Supervisor Node Critical Failure: {e}")
        log_night_audit("Supervisor", f"Critical Failure: {str(e)}")
        # Attempt to recover by routing back to supervisor or end
        return {"next": "SUPERVISOR", "sender": "Supervisor", "error": str(e)}
