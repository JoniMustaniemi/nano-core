# Nano Core

Nano is a local-first virtual assistant.

## Stack

- Python 3.12
- FastAPI and Uvicorn
- httpx
- Pydantic and pydantic-settings
- SQLite with SQLModel
- APScheduler
- Typer CLI
- pytest, ruff, and mypy

External local services such as `hailo-ollama`, `llama.cpp`, Whisper, Piper,
and systemd are installed and managed outside the Python package.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run

```powershell
uvicorn app.main:app --reload
```

## CLI

```powershell
nano-core health
nano-core chat "Hello"
```

## Test

```powershell
pytest
ruff check .
mypy app
```
