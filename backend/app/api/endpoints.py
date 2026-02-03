from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, List
import json
import asyncio
import os
import signal
import threading
import time
import sqlite3

from app.api.schemas import ChatInput, ChatOutput
from app.api.schemas import ChatInput, ChatOutput
# from app.core.graph import graph # REMOVED: Static import causes initialization issues
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
async def list_artifacts():
    """
    Lists all slide artifacts (.tsx) in the backend/artifacts directory.
    """
    # Assuming running from root or finding path relative to this file
    # Base path: /home/hgeon/gravity/LangAIAgent/backend/artifacts
    # We can use a safer way to find it relative to 'app' package
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_dir = os.path.join(base_dir, "artifacts")
    
    if not os.path.exists(artifacts_dir):
        return {"files": []}
        
    files = []
    for f in os.listdir(artifacts_dir):
        if f.endswith(".tsx") or f.endswith(".md"): # Scan TSX slides and MD documents
            files.append(f)
            
    # Sort by creation time (newest first)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(artifacts_dir, x)), reverse=True)
    return {"files": files}

@router.get("/artifacts/{filename}")
async def read_artifact(filename: str):
    """
    Reads the content of a specific artifact.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    artifacts_dir = os.path.join(base_dir, "artifacts")
    file_path = os.path.join(artifacts_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": "File not found"}
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content, "filename": filename}
    except Exception as e:
        return {"error": str(e)}

@router.get("/threads")
async def get_threads():
    """
    Returns a list of unique thread_ids stored in the SQLite DB.
    """
    db_path = "./backend/data/checkpoints.sqlite"
    if not os.path.exists(db_path):
        return {"threads": []}
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # LangGraph stores thread_id in JSON encoded metadata or config typically. 
        # But correct generic schema usually has thread_id column in checkpoints table.
        # Let's target the 'checkpoints' table.
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY created_at DESC")
        threads = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"threads": threads}
    except Exception as e:
        print(f"Error fetching threads: {e}")
        return {"threads": ["current_session"]} # Fallback

# Import module to access the global 'graph' variable which is initialized at startup
import app.core.graph as graph_module

# ... (ConnectionManager and previous endpoints remain same)

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

    try:
        async for event in graph_module.graph.astream_events(
            {"messages": [HumanMessage(content=user_input)]},
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

    except asyncio.CancelledError:
        print(f"Task for {client_id} was cancelled.")
    except Exception as e:
        import traceback
        print(f"Graph Error: {e}\n{traceback.format_exc()}")
        await manager.broadcast(json.dumps({"type": "error", "content": str(e)}), client_id)

