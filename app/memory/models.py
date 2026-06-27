from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Note(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="Untitled note", index=True)
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, default="default")
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class Reminder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    due_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = Field(default=None, index=True)
