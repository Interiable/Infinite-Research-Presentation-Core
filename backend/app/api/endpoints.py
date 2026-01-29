from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio

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

    except WebSocketDisconnect:
        manager.disconnect(client_id)
