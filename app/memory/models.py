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


class CodebaseFileRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)
    package: str = Field(index=True)
    content_hash: str = Field(default="")
    summary: str = Field(default="")
    last_suggestion: str | None = Field(default=None)
    last_confidence: str | None = Field(default=None)
    last_scanned_at: datetime | None = Field(default=None, index=True)
