from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    session_id: str
    activity_state: str
    tool_status: str
    intent: Optional[str] = None
    hotels: Optional[List[dict]] = None
    flights: Optional[List[dict]] = None
    error: Optional[str] = None