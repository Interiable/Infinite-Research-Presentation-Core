from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatInput(BaseModel):
    message: str
    thread_id: str = "default_thread"

class ChatOutput(BaseModel):
    response: str
    current_step: Optional[str] = None
    artifacts: Optional[Dict[str, Any]] = None
