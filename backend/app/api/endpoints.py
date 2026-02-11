from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from typing import Dict, List
import json
import asyncio
import os
import signal
import threading
import time
import sqlite3
import re

from app.api.schemas import ChatInput, ChatOutput
from app.api.schemas import ChatInput, ChatOutput
import app.core.graph as graph_module
from langchain_core.messages import HumanMessage

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
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
async def pick_folder():
    """
    Opens a native folder picker dialog on the server (user's machine).
    Updates the LOCAL_RESEARCH_DIR environment variable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Create a hidden root window
        root = tk.Tk()
        root.withdraw() # Hide the main window
        root.attributes('-topmost', True) # Bring to front
        
        # Open dialog
        folder_path = filedialog.askdirectory(title="Select Research Folder")
        root.destroy()
        
        if folder_path:
            # Update Environment Variable dynamically (Append logic)
            current_paths = os.environ.get("LOCAL_RESEARCH_DIR", "")
            if current_paths:
                # Avoid duplicates
                if folder_path not in current_paths.split(','):
                    new_paths = f"{current_paths},{folder_path}"
                else:
                    new_paths = current_paths
            else:
                new_paths = folder_path
            
            os.environ["LOCAL_RESEARCH_DIR"] = new_paths
            
            # Also invoke a log message via websocket broadcast if possible? 
            # (We don't have client_id here easily, so we just return it)
            return {"status": "success", "path": new_paths}
        else:
            return {"status": "cancelled", "path": None}
            
    except Exception as e:
        print(f"Error opening folder picker: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/config/folders")
async def get_folders():
    """
    Returns the current list of research folders.
    """
    raw = os.environ.get("LOCAL_RESEARCH_DIR", "")
    folders = [f.strip() for f in raw.split(',') if f.strip()]
    return {"folders": folders}

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
    files.sort(reverse=True) # Timestamp prefix usually handles sort
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
async def get_threads():
    """
    Returns a list of unique thread_ids stored in the SQLite DB.
    """
    import sqlite3
    # Resolve absolute path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "data", "checkpoints.sqlite")
    if not os.path.exists(db_path):
        return {"threads": []}
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC")
        threads = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"threads": threads}
    except Exception as e:
        print(f"Error fetching threads: {e}")
        return {"threads": []}

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

# Track active graph execution tasks
active_tasks: Dict[str, asyncio.Task] = {}

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # ... (WebSocket loop same as before)
            raw_data = await websocket.receive_text()
            print(f"DEBUG: WS Received: {raw_data}")
            
            try:
                message_obj = json.loads(raw_data)
                msg_type = message_obj.get("type", "message")
                content = message_obj.get("content", "")
            except json.JSONDecodeError:
                msg_type = "message"
                content = raw_data

            if msg_type == "command":
                if content == "pause":
                    if client_id in active_tasks and not active_tasks[client_id].done():
                        active_tasks[client_id].cancel()
                        await manager.broadcast(json.dumps({"type": "log", "content": "⏸️ Task Paused by User."}), client_id)
                    continue

            if client_id in active_tasks and not active_tasks[client_id].done():
                active_tasks[client_id].cancel() 
                await manager.broadcast(json.dumps({"type": "log", "content": "⚡ Interrupting... Integrating new feedback."}), client_id)
                await asyncio.sleep(0.5)

            task = asyncio.create_task(run_graph_execution(client_id, content))
            active_tasks[client_id] = task

    except WebSocketDisconnect:
        if client_id in active_tasks:
            active_tasks[client_id].cancel()
        manager.disconnect(client_id)

async def run_graph_execution(client_id: str, user_input: str):
    """
    Runs the LangGraph logic. Cancellable.
    """
    await manager.broadcast(json.dumps({"type": "log", "content": f"User: {user_input}"}), client_id)
    
    config = {"configurable": {"thread_id": client_id}, "recursion_limit": 500}
    
    if graph_module.graph is None:
        await manager.broadcast(json.dumps({"type": "error", "content": "System Error: Graph not initialized."}), client_id)
        return

    # Resumption Logic: If input is RESUME, we pass None to astream_events to continue existing state
    input_data = {"messages": [HumanMessage(content=user_input)]} if user_input != "RESUME" else None
    
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

                    # --- AGENT DIALOGUE BROADCAST ---
                    if 'sender' in data:
                        # Extract the main message (dialogue)
                        # We use the LAST message in the 'messages' list as the "Spoken" text
                        dialogue_text = "..."
                        if 'messages' in data and isinstance(data['messages'], list) and data['messages']:
                            last_msg = data['messages'][-1]
                            if hasattr(last_msg, 'content'):
                                dialogue_text = str(last_msg.content)
                            else:
                                dialogue_text = str(last_msg)
                        
                        # Broadcast specialized dialogue event
                        # TRUNCATION LOGIC: If message is too long (e.g. Supervisor Critique), truncate it for the UI.
                        # The full content is usually in an artifact anyway.
                        display_content = dialogue_text
                        if len(display_content) > 150:
                            display_content = display_content[:150] + "... (Click Artifacts to view full report)"
                            
                        await manager.broadcast(json.dumps({
                            "type": "agent_message",
                            "sender": data['sender'],
                            "content": display_content
                        }), client_id)

    except asyncio.CancelledError:
        print(f"Task for {client_id} was cancelled.")
    except Exception as e:
        import traceback
        print(f"Graph Error: {e}\n{traceback.format_exc()}")
        await manager.broadcast(json.dumps({"type": "error", "content": str(e)}), client_id)

