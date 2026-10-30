
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=2)


class ChatResponse(BaseModel):
    user_id: int
    question: str
    answer: str
    context_used: list[str]
