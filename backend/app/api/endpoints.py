from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import asyncio
import os
import signal
import threading
import time
import sqlite3
import re
import uuid
import shutil
from datetime import datetime

from app.api.schemas import ChatInput, ChatOutput
import app.core.graph as graph_module
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            if self.active_connections[client_id] == websocket:
                del self.active_connections[client_id]

    async def broadcast(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()


@router.post("/stop")
async def stop_server():
    """
    Gracefully shuts down the Backend Server.
    """
    def shutdown():
        time.sleep(1) # Give time for response to be sent
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=shutdown).start()
    return {"status": "shutting_down", "message": "Server halting in 1 second..."}

@router.post("/config/pick-folder")
async def pick_folder(project_id: str = "default"):
    """
    Opens a native folder picker dialog on the server (user's machine).
    Updates the project-specific configuration.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Create a hidden root window
        root = tk.Tk()
        root.withdraw() # Hide the main window
        root.attributes('-topmost', True) # Bring to front
        
        # Open dialog
        folder_path = filedialog.askdirectory(title=f"Select Research Folder for Project: {project_id}")
        root.destroy()
        
        if folder_path:
            from app.utils.config_manager import ConfigManager
            cm = ConfigManager()
            cm.add_project_folder(project_id, folder_path)
            
            new_paths = ",".join(cm.get_project_folders(project_id))
            return {"status": "success", "path": new_paths}
        else:
            return {"status": "cancelled", "path": None}
            
    except Exception as e:
        print(f"Error opening folder picker: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/config/folders")
async def get_folders(project_id: str = "default"):
    """
    Returns the list of research folders for the specified project.
    """
    from app.utils.config_manager import ConfigManager
    cm = ConfigManager()
    folders = cm.get_project_folders(project_id)
    return {"folders": folders}

@router.get("/config/projects")
async def get_projects():
    """
    Returns the list of all configured workspace projects.
    """
    from app.utils.config_manager import ConfigManager
    cm = ConfigManager()
    projects = cm.get_all_projects()
    return {"projects": projects}

@router.get("/artifacts")
async def list_artifacts(thread_id: str = None):
    """
    Lists all slide artifacts (.tsx) in backend/artifacts AND backend/results.
    If thread_id is provided, also scans artifacts/{thread_id}/ and results/{thread_id}/.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_root = os.path.join(base_dir, "artifacts")
    results_root = os.path.join(base_dir, "results")
    
    files = []
    
    # helper to scan a dir
    def scan_dir(path):
        found = []
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.endswith(".tsx") or f.endswith(".md"):
                    found.append(f)
        return found

    # 1. Scan Root Artifacts
    files.extend(scan_dir(artifacts_root))
    
    # 2. Scan Root Results
    files.extend(scan_dir(results_root))
    
    # 3. Scan Thread Subdirs
    if thread_id:
        safe_thread_id = "".join([c for c in thread_id if c.isalnum() or c in ('-', '_')])
        
        # Artifacts/{thread_id}
        thread_art_dir = os.path.join(artifacts_root, safe_thread_id)
        files.extend(scan_dir(thread_art_dir))
        
        # Results/{thread_id}
        thread_res_dir = os.path.join(results_root, safe_thread_id)
        files.extend(scan_dir(thread_res_dir))

    # Sort by creation time (approximation or just name)
    files = list(set(files))
    files.sort(reverse=True) 
    
    # --- v3.9 UI Polish: Pin Master Report to Top ---
    master_files = [f for f in files if f.startswith("00_")]
    other_files = [f for f in files if not f.startswith("00_")]
    files = master_files + other_files
    
    return {"files": files}

@router.get("/artifacts/{filename}")
async def read_artifact(filename: str, thread_id: str = None):
    """
    Reads the content of a specific artifact.
    Prioritizes artifacts/{thread_id}/{filename} if it exists.
    Also checks results/ and results/{thread_id}/.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_root = os.path.join(base_dir, "artifacts")
    results_root = os.path.join(base_dir, "results")
    
    target_path = None
    
    # 1. Try Thread Dir (Artifacts)
    if thread_id:
        safe_thread_id = "".join([c for c in thread_id if c.isalnum() or c in ('-', '_')])
        
        # Check artifacts/{thread_id}
        p = os.path.join(artifacts_root, safe_thread_id, filename)
        if os.path.exists(p): target_path = p
        
        # Check results/{thread_id} (New)
        if not target_path:
            p = os.path.join(results_root, safe_thread_id, filename)
            if os.path.exists(p): target_path = p
            
    # 2. Fallback to Roots
    if not target_path:
        # Check artifacts/
        p = os.path.join(artifacts_root, filename)
        if os.path.exists(p): target_path = p
        
        # Check results/
        if not target_path:
            p = os.path.join(results_root, filename)
            if os.path.exists(p): target_path = p
            
    if not target_path:
        return {"error": "File not found"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content, "filename": filename}
    except Exception as e:
        return {"error": str(e)}

@router.get("/threads")
async def get_threads(request: Request):
    """
    Returns a list of unique thread_ids stored in the SQLite DB.
    """
    # Migration: Use the SHARED connection from app.state to avoid "database is locked" conflicts
    db = request.app.state.db_conn
        
    try:
        async with db.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC") as cursor:
            rows = await cursor.fetchall()
            
            from app.utils.config_manager import ConfigManager
            cm = ConfigManager()
            mapping = cm.get_thread_projects()
            
            threads = [{"id": row[0], "project_id": mapping.get(row[0], "default")} for row in rows]
            return {"threads": threads}
    except Exception as e:
        print(f"Error fetching threads: {e}")
        return {"threads": []}

@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, request: Request):
    """
    Deletes all data associated with a thread: Checkpoints, Artifacts, and Results.
    """
    import shutil
    
    # Resolve paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    safe_thread_id = "".join([c for c in thread_id if c.isalnum() or c in ('-', '_')])
    
    deleted_items = []
    
    # Migration: Use the SHARED connection from app.state
    db = request.app.state.db_conn
    
    # 1. Delete DB Checkpoints (with Retry Loop)
    max_retries = 5
    retry_delay = 1.0
    for attempt in range(max_retries):
        try:
            # Migration: Use the existing shared connection
            # Corrected Table Names: LangGraph AsyncSqliteSaver uses 'checkpoints' and 'writes'
            await db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
            await db.commit()
            deleted_items.append("database_checkpoints")
            break # Success!
        except Exception as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"🔄 DB locked, retrying deletion for {thread_id} (Attempt {attempt+1}/{max_retries})...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            else:
                print(f"⚠️ Failed to delete DB entries for {thread_id}: {e}")
                break

    # 2. Delete Artifacts Folder
    art_dir = os.path.join(base_dir, "artifacts", safe_thread_id)
    if os.path.exists(art_dir):
        try:
            shutil.rmtree(art_dir)
            deleted_items.append("artifacts_folder")
        except Exception as e:
            print(f"⚠️ Failed to delete artifact dir {art_dir}: {e}")

    # 3. Delete Results Folder
    res_dir = os.path.join(base_dir, "results", safe_thread_id)
    if os.path.exists(res_dir):
        try:
            shutil.rmtree(res_dir)
            deleted_items.append("results_folder")
        except Exception as e:
            print(f"⚠️ Failed to delete results dir {res_dir}: {e}")

    return {
        "status": "success",
        "thread_id": thread_id,
        "deleted": deleted_items
    }

@router.post("/artifacts/export-pdf")
async def export_pdf(payload: dict):
    """
    Exports a clean PDF version of the artifact.
    Removes citation markers and other artifacts.
    """
    filename = payload.get("filename")
    thread_id = payload.get("thread_id")
    
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
        
    # Logic to find file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_root = os.path.join(base_dir, "artifacts")
    results_root = os.path.join(base_dir, "results")
    target_path = None
    
    if thread_id:
        safe_thread_id = "".join([c for c in thread_id if c.isalnum() or c in ('-', '_')])
        
        # Check artifacts/{thread_id}
        p = os.path.join(artifacts_root, safe_thread_id, filename)
        if os.path.exists(p): target_path = p
        
        # Check results/{thread_id}
        if not target_path:
            p = os.path.join(results_root, safe_thread_id, filename)
            if os.path.exists(p): target_path = p
            
    if not target_path:
        # Check artifacts/
        p = os.path.join(artifacts_root, filename)
        if os.path.exists(p): target_path = p

        # Check results/
        if not target_path:
            p = os.path.join(results_root, filename)
            if os.path.exists(p): target_path = p
            
    if not target_path:
        raise HTTPException(status_code=404, detail="File not found")
        
    # Read & Clean
    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    # --- Advanced Content Parsing ---
    # The file may contain mixed Markdown and Python string representations of lists/dicts.
    # Pattern: [{'type': 'text', ... }]
    # We use regex to find these blocks and ast.literal_eval to safely parse them and extract 'text'.
    
    import ast

    def parse_block(match):
        try:
            # literal_eval safely evaluates a string containing a Python literal
            data = ast.literal_eval(match.group(0))
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                # Extract text and unescape if needed (though literal_eval handles standard escapes)
                return data[0].get('text', '')
            elif isinstance(data, dict):
                 return data.get('text', '')
        except Exception as e:
            print(f"⚠️ Parsing failed for block: {e}")
            return match.group(0) # Return original if parse fails
        return match.group(0)

    # Regex to find the blocks: starts with [{ or { followed by 'type': 'text'
    # We use DOTALL to match across newlines.
    # We match roughly things looking like python structures.
    # Pattern explanation: 
    # \[?\s*\{  -> Optional [ then {
    # .*?       -> Content
    # \}\s*\]?  -> } then Optional ]
    # But specifically anchoring on 'type': 'text' to avoid false positives
    
    # Robust pattern for the specific artifact format seen:
    # [{'type': 'text', ... }]
    pattern = r"\[\s*\{'type':\s*'text'.*?\}\s*\]"
    
    content = re.sub(pattern, parse_block, content, flags=re.DOTALL)
    
    # Fallback for simple dicts not in list: {'type': 'text'...}
    # Be careful not to double replace if regex above caught it (it expects brackets)
    # If the file uses bare dicts, we might need another pass or adjusted regex.
    # The artifact sample showed list wrapping.
    
    # Final cleanup of common escape artifacts if still present
    if "\\n" in content:
        content = content.replace("\\n", "\n").replace("\\t", "  ")
        
    # Regex Cleaning (Citations)
        
    # Regex Cleaning (Citations)
    # Remove [1], [doc.pdf], Refs: ...
    content = re.sub(r'\[\d+\]', '', content)
    content = re.sub(r'\[.*?\.pdf\]', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\[source:.*?\]', '', content, flags=re.IGNORECASE)
    content = re.sub(r'Refs: \d+ files\.\.\.', '', content)
    
    # Convert using existing utility
    from app.utils import convert_to_pdf
    # Temp file
    temp_pdf_path = target_path.replace(".md", "_clean.pdf")
    # Temp MD
    temp_md_path = target_path.replace(".md", "_clean_temp.md")
    
    try:
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        success = convert_to_pdf(temp_md_path, temp_pdf_path)
        
        if success and os.path.exists(temp_pdf_path):
            return FileResponse(temp_pdf_path, filename=f"Clean_{filename.replace('.md', '.pdf')}")
        else:
            raise HTTPException(status_code=500, detail="PDF Generation Failed in Utility")
            
    except Exception as e:
         print(f"PDF Export Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))
    finally:
         # Cleanup Temp MD
         if os.path.exists(temp_md_path):
             try: os.remove(temp_md_path)
             except: pass

@router.post("/chat", response_model=ChatOutput)
async def chat_endpoint(payload: ChatInput):
    """
    Standard HTTP endpoint for synchronous interaction (Optional)
    """
    config = {"configurable": {"thread_id": payload.thread_id}}
    
    # Send user message to graph
    if graph_module.graph is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
        
    response = await graph_module.graph.ainvoke(
        {"messages": [HumanMessage(content=payload.message)]},
        config=config
    )
    
    return ChatOutput(
        response=response['messages'][-1].content,
        current_step=str(response.get('next'))
    )

@router.get("/chat/history/{thread_id}")
async def get_chat_history(thread_id: str):
    """
    Retrieves the strictly 'User Prompt' history for a given thread.
    Useful for the 'Command History' UI.
    """
    if graph_module.graph is None:
        return {"history": []}
        
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Fetch State Snapshot
        state_snapshot = await graph_module.graph.aget_state(config)
        messages = state_snapshot.values.get("messages", [])
        
        # Filter for HumanMessage only
        history = []
        for m in messages:
            if isinstance(m, HumanMessage):
                history.append({
                    "role": "user",
                    "content": m.content,
                    "timestamp": getattr(m, 'additional_kwargs', {}).get('timestamp', '')
                })
                
        return {"history": history}
        
    except Exception as e:
        print(f"Error fetching history: {e}")
        return {"history": []}

# ============================================================
# DIALOGUE PERSISTENCE (Agent Chat History)
# ============================================================
DIALOGUE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dialogue_history")
os.makedirs(DIALOGUE_DIR, exist_ok=True)

def _dialogue_path(thread_id: str) -> str:
    """Returns the file path for a thread's dialogue history."""
    safe_id = thread_id.replace("/", "_").replace("..", "")
    return os.path.join(DIALOGUE_DIR, f"{safe_id}.json")

def save_dialogue_message(thread_id: str, sender: str, content: str):
    """Appends a dialogue message to the thread's history file."""
    path = _dialogue_path(thread_id)
    messages = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, IOError):
            messages = []
    
    messages.append({
        "type": "agent_message",
        "sender": sender,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

@router.get("/dialogue/history/{thread_id}")
async def get_dialogue_history(thread_id: str):
    """Returns the full agent dialogue history for a thread."""
    path = _dialogue_path(thread_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
            return {"dialogue": messages}
        except (json.JSONDecodeError, IOError):
            pass
    return {"dialogue": []}

# ============================================================
# CONVERSATIONAL DIALOGUE GENERATOR
# ============================================================
import random

def _make_conversational(sender: str, raw_text: str, next_agent: str, data: dict) -> str:
    """
    Transforms raw agent output into natural, conversational dialogue.
    Each agent has a distinct personality and speaking style.
    v6.3: Enhanced with richer context extraction for ALL 9 agents.
    """
    s = sender.lower()
    text = raw_text.strip()
    
    # Skip empty or system-only messages
    if not text or text == "..." or len(text) < 5:
        return ""
    
    # --- PLANNER ---
    if s == "planner":
        step_count = len(data.get("plan", []))
        if step_count > 0:
            scope = "간단한" if step_count <= 3 else "체계적인" if step_count <= 7 else "심층적인"
            selected = data.get("selected_files", [])
            if isinstance(selected, list) and selected:
                return f"프로젝트를 분석 완료! {scope} 연구 계획을 수립했습니다. 총 {step_count}단계 계획이고, 핵심 참고 파일 {len(selected)}건을 선별했습니다. Supervisor, 검토 부탁드립니다! 🚀"
            return f"프로젝트를 분석하고 {scope} 연구 계획을 수립했습니다. 총 {step_count}단계로 진행합니다. 팀, 시작하겠습니다! 🚀"
        if "planning" in text.lower() or "complete" in text.lower():
            return "분석 완료! 연구 계획을 수립했으니, Supervisor에게 넘기겠습니다."
        if "failed" in text.lower() or "fallback" in text.lower():
            return "계획 수립 중 문제가 발생해서 비상 계획으로 전환했습니다. 제한된 범위로 진행합니다. ⚠️"
        return _smart_truncate(text, 200)
    
    # --- SUPERVISOR ---
    if s == "supervisor":
        # Detect approval
        if "APPROVED" in text or "approved" in text.lower():
            chap_idx = data.get("current_chapter_index", 0)
            chap_plan = data.get("chapter_plan", [])
            if chap_plan and chap_idx < len(chap_plan):
                chap_title = chap_plan[chap_idx].get("title", "")
                if chap_title:
                    remaining = len(chap_plan) - chap_idx - 1
                    if remaining > 0:
                        return f"'{chap_title}' 챕터, 퀄리티 기준 충족. 승인 완료! 남은 {remaining}개 챕터 계속 진행하자. ✅"
                    return f"마지막 챕터 '{chap_title}' 승인! 모든 챕터가 완성됐어. 조립 시작하겠다. 🎉"
            praises = [
                "좋아, 이 정도면 품질 기준을 충족해. 다음 단계로 넘어가자.",
                "검토 완료. 훌륭한 결과물이야. 다음 스텝으로 진행하겠어.",
                "LGTM! 이 퀄리티면 충분해. 다음으로 가자.",
                "잘 했어. 이번 결과는 승인이야. 바로 다음 단계 시작하자."
            ]
            return random.choice(praises)
        
        # Detect rejection  
        if "REJECTED" in text or "rejected" in text.lower():
            reject_reason = _extract_after(text, "REJECTED:")
            iteration = data.get("iteration_count", 0)
            if reject_reason:
                if iteration >= 5:
                    return f"이번이 {iteration}번째 시도야. {_smart_truncate(reject_reason, 120)} 이번에는 확실히 수정해."
                return f"아직 부족해. {_smart_truncate(reject_reason, 150)} 수정해서 다시 제출해."
            return "품질 기준 미달이야. 피드백을 참고해서 다시 작업해줘."
        
        # Detect structure reset
        if "STRUCTURE_RESET" in text:
            return "챕터 구조에 근본적인 문제가 있어. 챕터 계획을 처음부터 다시 세워줘. 🏗️"
        
        # Detect data gap
        if "DATA_GAP" in text:
            return "자료가 부족한 것 같아. Deep Researcher, 추가 검색 들어가자. 🔍"
        
        # Detect deep research trigger
        if "DEEP_RESEARCH" in text:
            topic = _extract_after(text, "DEEP_RESEARCH_REQUIRED:")
            if topic:
                return f"데이터가 부족해. Deep Researcher, {_smart_truncate(topic, 100)} 관련 자료를 외부에서 찾아와."
            return "추가 데이터가 필요해. Deep Researcher 팀, 외부 검색 시작해."

        # Detect intervention
        if "INTERVENTION" in text:
            if "HARD" in text or "FORCE" in text:
                return "충분히 기다렸어. 내가 직접 작성할게. 이 버전으로 확정하고 다음으로 넘어가자. 🔥"
            if "SOFT" in text or "COACHING" in text:
                return "방향을 잡아줄게. 내가 수정한 버전을 참고해서 마무리해. ⚠️"
        
        # Detect delegation / routing
        if next_agent:
            agent_names = {
                "RESEARCHER": "Researcher",
                "DEEP_RESEARCHER": "Deep Researcher",
                "ARCHITECT": "Architect",
                "FINALIZER": "Finalizer",
                "PLAN_REFINER": "Plan Refiner",
                "WARDEN": "Warden",
                "ARCHIVIST": "Archivist",
                "END": "최종 완료"
            }
            target = agent_names.get(next_agent, next_agent)
            
            step_idx = data.get("current_step_index", 0)
            plan = data.get("plan", [])
            if plan and step_idx < len(plan):
                step_title = plan[step_idx].get("title", "")
                if step_title:
                    return f"이번 태스크는 '{step_title}'야. {target}, 진행해줘."
            
            if next_agent == "PLAN_REFINER":
                return f"이 단계의 세부 계획이 필요해. Plan Refiner, sub-plan을 만들어줘."
            if next_agent == "WARDEN":
                return f"다음 단계 진행 전에 Warden, 지금까지 연구 맥락 브리핑 부탁해."
            if next_agent == "END":
                return "모든 연구가 완료됐어. 최종 보고서를 마무리하겠다."
            return f"좋아, {target} 팀에게 넘기겠어. 시작해줘."
        
        # Detect repetition failure
        if "REPEAT_FAILURE" in text:
            return "같은 실수가 반복되고 있어. 이전 피드백을 다시 확인하고 정확히 수정해줘."
        
        return _smart_truncate(text, 200)
    
    # --- RESEARCHER ---
    if s == "researcher":
        chap_idx = data.get("current_chapter_index", 0)
        chap_plan = data.get("chapter_plan", [])
        iteration = data.get("iteration_count", 0)
        
        if chap_plan and chap_idx < len(chap_plan):
            chap_title = chap_plan[chap_idx].get("title", "")
            version = f"v{iteration + 1}" if iteration else "초안"
            if "complete" in text.lower() or "report" in text.lower():
                return f"챕터 {chap_idx+1}/{len(chap_plan)} '{chap_title}' {version} 작성을 완료했습니다. Supervisor, 검토 부탁드립니다. 📝"
            return f"챕터 {chap_idx+1} '{chap_title}' 작성 중입니다... ({version}) ✍️"
        
        if "complete" in text.lower() or "report" in text.lower():
            return "조사 결과를 정리해서 보고서를 작성했습니다. Supervisor, 검토 부탁드립니다. 📝"
        if "research" in text.lower() and "start" in text.lower():
            return "자료 분석을 시작합니다. 로컬 라이브러리와 웹 자료를 종합하겠습니다."
        return f"작업 결과를 보고합니다: {_smart_truncate(text, 180)}"
    
    # --- DEEP RESEARCHER ---
    if s == "deepresearcher" or "deep" in s:
        if "academic" in text.lower() or "paper" in text.lower() or "arxiv" in text.lower():
            return "학술 논문 검색을 완료했습니다. ArXiv에서 관련 논문들을 분석해서 팀에 전달합니다. 🔬"
        if "patent" in text.lower():
            return "특허 검색을 완료했습니다. 관련 특허와 선행기술을 분석해서 보고서에 반영합니다. 📋"
        if "web" in text.lower() or "tavily" in text.lower() or "search" in text.lower():
            return "웹 리서치를 마쳤습니다. 최신 자료를 수집했고, 캐시에 저장해두었습니다. 🌐"
        if "cache" in text.lower():
            return "이전에 검색한 캐시 데이터를 활용합니다. API 호출 없이 빠르게 진행합니다. 💾"
        return f"심층 조사 완료. Researcher에게 데이터를 전달합니다: {_smart_truncate(text, 150)}"
    
    # --- ARCHITECT ---
    if s == "architect":
        if "slide" in text.lower() or "presentation" in text.lower():
            return "프레젠테이션 슬라이드 3가지 컨셉을 디자인했습니다. React + Tailwind + Framer Motion 기반이에요. 미리보기를 확인해주세요! 🎨"
        if "html" in text.lower():
            return "HTML 슬라이드 컴포넌트를 조립 완료했습니다. 인터랙티브 프레젠테이션 준비 완료! 🏗️"
        return f"디자인 작업을 완료했습니다: {_smart_truncate(text, 180)}"
    
    # --- ARCHIVIST ---
    if s == "archivist":
        knowledge = data.get("local_knowledge", "")
        knowledge_len = len(knowledge) if knowledge else 0
        if knowledge_len > 0:
            return f"로컬 문서를 벡터 DB에 색인화 완료했습니다. {knowledge_len:,}자 분량의 지식 기반을 구축했습니다. Planner에게 넘기겠습니다. 📂"
        if "fail" in text.lower():
            return "문서 색인화 중 일부 오류가 발생했지만. 제한된 컨텍스트로 진행하겠습니다. ⚠️"
        return "모든 문서를 아카이브에 정리하고 색인화했습니다. 연구 시작 준비 완료! 📂"
    
    # --- FINALIZER ---
    if s == "finalizer":
        if "english" in text.lower() or "korean" in text.lower() or "pdf" in text.lower():
            return "영문 및 한국어 최종 보고서를 컴파일하고 PDF로 변환을 완료했습니다. 결과물을 확인해주세요! ✅📄"
        if "error" in text.lower() or "fail" in text.lower():
            return "최종 보고서 합성 중 오류가 발생했습니다. 사용 가능한 데이터로 최선의 결과물을 생성했습니다. ⚠️"
        return "최종 보고서를 컴파일하고 품질 검토를 완료했습니다. 결과물을 확인해주세요! ✅"
    
    # --- PLAN REFINER ---
    if "refiner" in s or s == "plan refiner":
        sub_plan = data.get("sub_plan", [])
        if isinstance(sub_plan, list) and sub_plan:
            step_idx = data.get("current_step_index", 0) + 1
            sub_titles = [sp.get("title", "") for sp in sub_plan[:3]]
            preview = ", ".join([f"'{t}'" for t in sub_titles if t])
            return f"Step {step_idx}의 세부 실행 계획을 수립했습니다. {len(sub_plan)}개의 sub-step으로 분할: {preview}{'...' if len(sub_plan) > 3 else ''}. Supervisor에게 보고합니다. 📋"
        return "이번 단계의 세부 계획을 수립했습니다. 연구 범위를 구체적인 작업 단위로 분할했습니다."
    
    # --- WARDEN ---
    if "warden" in s:
        knowledge = data.get("shared_knowledge", "")
        if "strategic" in text.lower() or "brief" in text.lower():
            return "지금까지의 연구 맥락을 분석하고 전략적 브리핑을 작성했습니다. 핵심 용어와 주의사항을 Researcher에게 전달합니다. 🛡️"
        if knowledge and len(knowledge) > 500:
            return f"전체 연구 흐름을 검토하고 브리핑을 준비했습니다. Researcher가 일관된 방향으로 작성할 수 있도록 가이드합니다. 🛡️"
        return "보안 및 품질 감사를 수행했습니다. 연구 방향에 이상 없음을 확인합니다. 🛡️"
    
    # --- FALLBACK ---
    return _smart_truncate(text, 200)


def _smart_truncate(text: str, max_len: int) -> str:
    """Truncates text at a sentence boundary if possible."""
    if len(text) <= max_len:
        return text
    # Try to cut at a sentence boundary
    truncated = text[:max_len]
    last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'), truncated.rfind('。'))
    if last_period > max_len * 0.5:
        return truncated[:last_period + 1]
    return truncated + "..."


def _extract_after(text: str, keyword: str) -> str:
    """Extracts text after a keyword."""
    idx = text.find(keyword)
    if idx >= 0:
        return text[idx + len(keyword):].strip()
    return ""


# Track active graph execution tasks
active_tasks: Dict[str, asyncio.Task] = {}

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # ... (WebSocket loop same as before)
            raw_data = await websocket.receive_text()
            # Only log non-ping messages to keep terminal clean
            if '"ping"' not in raw_data:
                print(f"DEBUG: WS Received: {raw_data}")
            
            try:
                message_obj = json.loads(raw_data)
                msg_type = message_obj.get("type", "message")
                content = message_obj.get("content", "")
                search_options = message_obj.get("search_options", {})
                project_id = message_obj.get("project_id")
                
                # Register this thread with the specified project if provided
                if project_id:
                    from app.utils.config_manager import ConfigManager
                    ConfigManager().set_thread_project(client_id, project_id)
                
            except json.JSONDecodeError:
                msg_type = "message"
                content = raw_data
                search_options = {}
                project_id = "default"

            # --- Keep-Alive / Ping Handling ---
            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
                continue

            if msg_type == "command":
                if content == "pause":
                    if client_id in active_tasks and not active_tasks[client_id].done():
                        active_tasks[client_id].cancel()
                        await manager.broadcast(json.dumps({"type": "log", "content": "⏸️ Task Paused by User."}), client_id)
                    continue


            # --- v3.10 Background & Resume Fix ---
            if client_id in active_tasks and not active_tasks[client_id].done():
                # If a task is already running and user sends "RESUME", just log it and skip starting a new task
                if content == "RESUME":
                    await manager.broadcast(json.dumps({"type": "log", "content": "⚡ Agent is already working in background. Resuming stream..."}), client_id)
                    continue
                
                # Only cancel if it's a NEW manual input
                active_tasks[client_id].cancel() 
                await manager.broadcast(json.dumps({"type": "log", "content": "⚡ New request received. Interrupting current flow."}), client_id)
                await asyncio.sleep(0.5)

            task = asyncio.create_task(run_graph_execution(client_id, content, search_options, project_id))
            active_tasks[client_id] = task

    except WebSocketDisconnect:
        # --- v3.9 Background Mode: DON'T cancel task on disconnect ---
        print(f"📡 WebSocket Disconnected for {client_id}. Task continues in BACKGROUND.")
        manager.disconnect(websocket, client_id)

async def run_graph_execution(client_id: str, user_input: str, search_options: dict = None, project_id: str = "default"):
    """
    Runs the LangGraph logic. Cancellable.
    """
    await manager.broadcast(json.dumps({"type": "log", "content": f"User: {user_input}"}), client_id)
    
    # Broadcast user message to Agent Chat dialogue
    if user_input != "RESUME":
        user_msg = {"type": "agent_message", "sender": "User", "content": user_input}
        await manager.broadcast(json.dumps(user_msg), client_id)
        save_dialogue_message(client_id, "User", user_input)
    
    config = {"configurable": {"thread_id": client_id}, "recursion_limit": 100000}
    
    if graph_module.graph is None:
        await manager.broadcast(json.dumps({"type": "error", "content": "System Error: Graph not initialized."}), client_id)
        return

    # Resumption Logic: Check if state exists before sending None
    state_snapshot = await graph_module.graph.aget_state(config)
    has_history = len(state_snapshot.values.get("messages", [])) > 0
    
    if user_input == "RESUME" and not has_history:
        # Fallback: Treat RESUME as "Start" if no history
        await manager.broadcast(json.dumps({"type": "log", "content": "⚠️ No checkpoint found. Starting new session..."}), client_id)
        input_data = {"messages": [HumanMessage(content="Start Research")]}
        if search_options is not None:
            input_data["search_options"] = search_options
        input_data["project_id"] = project_id
    else:
        if user_input != "RESUME":
            input_data = {"messages": [HumanMessage(content=user_input)]}
            if search_options is not None:
                input_data["search_options"] = search_options
            input_data["project_id"] = project_id
        else:
            input_data = None
    
    if user_input == "RESUME":
        await manager.broadcast(json.dumps({"type": "log", "content": "🔄 Resuming Research from Checkpoint..."}), client_id)

    try:
        async for event in graph_module.graph.astream_events(
            input_data,
            config=config,
            version="v1"
        ):
            kind = event["event"]
            
            # Events Processing (Same as before)
            if kind == "on_chain_end":
                data = event['data'].get('output')
                if data and isinstance(data, dict):
                    # Slide Update
                    if 'slide_code' in data:
                        slide_payload = list(data['slide_code'].values())[0]
                        await manager.broadcast(json.dumps({
                            "type": "slide_update", 
                            "code": slide_payload
                        }), client_id)
                    
                    # Agent Logs
                    if 'messages' in data:
                        messages = data['messages']
                        if isinstance(messages, list) and len(messages) > 0:
                            last_msg = messages[-1]
                            if hasattr(last_msg, 'content'):
                                content = last_msg.content
                                if len(content) > 300: content = content[:300] + "..."
                                await manager.broadcast(json.dumps({
                                    "type": "log", 
                                    "content": f"🤖 {data.get('next', 'System')}: {content}"
                                }), client_id)

                    # Context Switch Log
                    if 'next' in data:
                        await manager.broadcast(json.dumps({
                            "type": "log", 
                            "content": f"🔄 Switching Context -> {data['next']}"
                        }), client_id)
                        
                        
                    # v7.0: Progress Tracker — parse plan from project_plan.md artifact file
                    # Runs on any node output to guarantee UI updates
                    try:
                        import glob, os, re
                        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        artifact_dir = os.path.join(base_dir, "artifacts", client_id)
                        plan_files = sorted(glob.glob(os.path.join(artifact_dir, "*_project_plan.md")), reverse=True)
                        
                        if plan_files:
                            with open(plan_files[0], 'r', encoding='utf-8') as pf:
                                plan_text = pf.read()
                            
                            steps = re.findall(r'### \[([ x>])\] Step (\d+):', plan_text)
                            sub_steps = re.findall(r'- \[([ x>])\] \*\*Step \d+\.\d+\*\*:', plan_text)
                            
                            total_steps = len(steps)
                            if total_steps > 0:
                                current_step = 0
                                for mark, num in steps:
                                    if mark == '>':
                                        current_step = int(num)
                                        break
                                    elif mark == 'x':
                                        current_step = int(num)
                                
                                total_subs = len(sub_steps)
                                current_sub = 0
                                for i, (mark, ) in enumerate([(s[0],) for s in sub_steps]):
                                    if mark == '>':
                                        current_sub = i + 1
                                        break
                                    elif mark == 'x':
                                        current_sub = i + 1
                                
                                if total_subs > 0:
                                    step_pct = (current_step - 1) / total_steps
                                    sub_pct = (current_sub / total_subs) / total_steps
                                    percent = round((step_pct + sub_pct) * 100, 1)
                                else:
                                    percent = round(((current_step) / total_steps) * 100, 1)
                                
                                await manager.broadcast(json.dumps({
                                    "type": "progress",
                                    "current_step": current_step,
                                    "total_steps": total_steps,
                                    "current_sub": current_sub,
                                    "total_subs": total_subs,
                                    "percent": min(percent, 99.9),
                                    "next_agent": data.get('next', 'WORKING')
                                }), client_id)
                    except Exception as prog_err:
                        print(f"   ⚠️ Progress tracker error: {prog_err}")

                    # --- AGENT DIALOGUE BROADCAST (Conversational) ---
                    if 'sender' in data:
                        sender = data['sender']
                        next_agent = data.get('next', '')
                        
                        # Extract raw text for context
                        raw_text = ""
                        if 'messages' in data and isinstance(data['messages'], list) and data['messages']:
                            last_msg = data['messages'][-1]
                            if hasattr(last_msg, 'content'):
                                raw_text = str(last_msg.content)
                            else:
                                raw_text = str(last_msg)
                        
                        # Generate conversational dialogue based on agent role and context
                        display_content = _make_conversational(sender, raw_text, next_agent, data)
                        
                        if display_content:  # Only broadcast non-empty dialogue
                            await manager.broadcast(json.dumps({
                                "type": "agent_message",
                                "sender": sender,
                                "content": display_content
                            }), client_id)
                            # Persist to dialogue history file
                            save_dialogue_message(client_id, sender, display_content)

    except asyncio.CancelledError:
        print(f"Task for {client_id} was cancelled.")
    except Exception as e:
        import traceback
        print(f"Graph Error: {e}\n{traceback.format_exc()}")
        await manager.broadcast(json.dumps({"type": "error", "content": str(e)}), client_id)

