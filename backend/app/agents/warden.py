import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.utils import save_artifact

# Warden uses Local Model (Llama 4 Scout) to save Gemini Quota
from app.agents.local_model import local_llm

def warden_node(state: AgentState, config=None):
    """
    The Global Knowledge Guardian (Warden).
    Synthesizes massive context into a precise 'Strategic Brief' for Workers.
    """
    plan = state.get('plan', [])
    current_index = state.get('current_step_index', 0)
    sub_plan = state.get('sub_plan', [])
    sub_index = state.get('current_sub_step_index', 0)
    
    if not sub_plan and current_index < len(plan):
        # Fallback to main step if sub_plan is missing for some reason
        current_step = plan[current_index]
    else:
        current_step = sub_plan[sub_index] if sub_index < len(sub_plan) else plan[current_index]

    local_knowledge = state.get('local_knowledge', '')
    master_report_path = state.get('incremental_report_path', '')
    master_report_content = ""
    
    if master_report_path and os.path.exists(master_report_path):
        with open(master_report_path, "r") as f:
            master_report_content = f.read()

    # Maximized context slicing for Local Model (Thorough reading prioritized over speed)
    # Master Report: up to 50k chars, Local Knowledge: up to 50k chars
    master_report_slice = master_report_content[:50000]
    local_knowledge_slice = local_knowledge[:50000]

    prompt = f"""
    You are the **Global Knowledge Guardian (Warden)**.
    Provide a **Strategic Brief** to the Researcher for the following task.
    
    **Worker's Current Task:**
    "{current_step['description']}"
    
    **Master Report (Context):**
    {master_report_slice} 
    
    **Local Knowledge (Context):**
    {local_knowledge_slice}
    
    **Your Mission (KOREAN):**
    1. **핵심 데이터 추출**: 지식 베이스에서 이 작업에 반드시 필요한 파일/데이터를 식별하십시오.
    2. **주의사항(Warn)**: 기존 마스터 보고서와 충돌하거나 주의해야 할 의존 관계를 지적하십시오.
    3. **가이드라인(Direct)**: 이 단계가 전체 리포트와 완벽히 조화되도록 3~5개의 핵심 규칙(Must-Include)을 제시하십시오.
    
    **Output Format**:
    - **Language**: KOREAN
    """
    
    response = local_llm.invoke(prompt)
    strategic_brief = response.content
    
    # Extract Thread ID for Artifact Isolation
    thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"
    
    # Save Brief as Artifact for User Review
    brief_filename = f"Step{current_index+1}_Sub{sub_index+1}_Warden_Brief"
    save_artifact(brief_filename, f"# 🛡️ Warden Strategic Brief: {current_step['title']}\n\n{strategic_brief}", "md", thread_id=thread_id)

    # We store the brief in shared_knowledge temporarily for the worker to pick up
    return {
        "shared_knowledge": f"--- WARDEN STRATEGIC BRIEF ---\n{strategic_brief}\n\n{state.get('shared_knowledge', '')}",
        "next": "SUPERVISOR", # Return to supervisor to delegate to the worker
        "sender": "Warden",
        "messages": [SystemMessage(content=f"Warden이 '{current_step['title']}' 단계를 위한 전략적 브리핑을 생성했습니다.")]
    }
