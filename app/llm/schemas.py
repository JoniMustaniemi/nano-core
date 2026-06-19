from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    mode: Literal["chat", "agent"] = "agent"


class ChatResponse(BaseModel):
    content: str
