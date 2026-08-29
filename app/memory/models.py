from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, default="default")
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class Timer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(default="countdown", index=True)
    label: str = Field(default="Timer")
    due_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InternalNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    title: str
    content: str
    payload_json: str
    status: str = Field(default="pending", index=True)
    attempt_count: int = Field(default=0)
    next_attempt_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    last_attempt_at: datetime | None = Field(default=None)
    delivered_at: datetime | None = Field(default=None)
