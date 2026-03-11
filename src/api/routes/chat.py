from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_agent_ref: Any = None


def set_agent(agent: Any) -> None:
    global _agent_ref
    _agent_ref = agent


class ChatRequest(BaseModel):
    text: str
    chat_id: str = "debug"
    open_id: str = "debug"


class ChatResponse(BaseModel):
    reply: str


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if _agent_ref is None:
        return ChatResponse(reply="Agent not initialized")

    reply = await _agent_ref.run(req.text, req.chat_id, req.open_id)
    return ChatResponse(reply=reply)
