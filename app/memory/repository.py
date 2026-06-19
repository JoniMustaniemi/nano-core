from sqlmodel import Session, select

from app.memory.db import engine
from app.memory.models import Note


def add_note(content: str) -> Note:
    with Session(engine) as session:
        note = Note(content=content)
        session.add(note)
        session.commit()
        session.refresh(note)
        return note


def list_notes() -> list[Note]:
    with Session(engine) as session:
        return list(session.exec(select(Note)))
