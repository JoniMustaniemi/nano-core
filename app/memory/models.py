from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
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


class MeetingReminder(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("calendar_id", "event_id", "start", name="uq_meeting_reminder_instance"),
    )

    id: str = Field(primary_key=True)
    calendar_id: str = Field(index=True)
    event_id: str = Field(index=True)
    start: datetime = Field(index=True)
    end: datetime
    summary: str
    all_day: bool = Field(default=False)
    lead_minutes: int
    remind_at: datetime = Field(index=True)
    fired_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
