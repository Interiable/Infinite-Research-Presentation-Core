from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio
import os
import signal
import threading
import time

from app.api.schemas import ChatInput, ChatOutput
from app.core.graph import graph
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

@router.post("/chat", response_model=ChatOutput)
async def chat_endpoint(payload: ChatInput):
    """
    Standard HTTP endpoint for synchronous interaction (Optional)
    """
    # For now, we mainly rely on Websockets for the infinite loop, 
    # but this triggers a single step.
    config = {"configurable": {"thread_id": payload.thread_id}}
    
    # Send user message to graph
    response = await graph.ainvoke(
        {"messages": [HumanMessage(content=payload.message)]},
        config=config
    )
    
    return ChatOutput(
        response=response['messages'][-1].content,
        current_step=str(response.get('next'))
    )

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Parse input
            # Assume data is just the user message string for now
            
            await manager.broadcast(json.dumps({"type": "log", "content": f"User: {data}"}), client_id)
            
            config = {"configurable": {"thread_id": client_id}}
            
            try:
                # Streaming events from the graph
                async for event in graph.astream_events(
                    {"messages": [HumanMessage(content=data)]},
                    config=config,
                    version="v1"
                ):
                    kind = event["event"]
                    
                    # Filter interesting events and send logs
                    if kind == "on_chat_model_stream":
                        # Stream tokens if needed (too verbose for now)
                        pass
                    elif kind == "on_chain_end":
                        # Check for updates in state
                        data = event['data'].get('output')
                        if data and isinstance(data, dict):
                            # Detect if artifacts like slides were generated
                            if 'slide_code' in data:
                                slide_payload = list(data['slide_code'].values())[0] # Get first slide
                                await manager.broadcast(json.dumps({
                                    "type": "slide_update", 
                                    "code": slide_payload
                                }), client_id)
                            
                            # Log the next step
                            if 'next' in data:
                                await manager.broadcast(json.dumps({
                                    "type": "log", 
                                    "content": f"Agent Switching to: {data['next']}"
                                }), client_id)
            except Exception as e:
                import traceback
                error_msg = f"Graph Execution Error: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                await manager.broadcast(json.dumps({"type": "error", "content": str(e)}), client_id)
                await manager.broadcast(json.dumps({"type": "log", "content": "⚠️ System Error. Check console."}), client_id)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
