# Technical Notes

## Architecture

Nano's assistant layer separates multi-turn UX from single-shot tool execution:

| Layer | Module pattern | Responsibility |
|-------|----------------|----------------|
| **Interaction flows** | `*InteractionHandler` in `app/assistant/flows/` | Keyword routing, pending state, confirmations, follow-ups |
| **Tools** | `*_tools.py` in `app/tools/` | One-shot actions invoked by the router or planner |
| **Router** | `AgentRouter` | Fast-path routing before the planner runs |
| **Planner** | `AgentPlanner` | JSON tool loop for non-deterministic requests |

Use an interaction handler when the user may need multiple turns (notes, timers, wipe).
Use a registered tool when a single call is enough (health check, file read, pull request).

Flow-owned tools (`add_note`, `list_notes`, timer tools) are excluded from the planner
prompt because their UX is handled by interaction handlers.

`AgentChatFlow` builds planner messages only; it is not an interaction handler.

## Answer Pipeline

Every user-facing reply follows one path:

```
User message
  → AgentRouter.decide() (or AnswerExecutor.draft in chat mode)
  → ResponseSource (facts + kind)
  → finalize_response()
      → ResponseComposer.compose()   # apply voice to facts
      → enforce_user_facing_answer() # bounded guard loop with alignment check
      → polish_user_facing_answer()  # tighten repetitive final wording
      → persist + activity.standby
```

**Invariant:** compose runs once; guard may run up to two rewrite passes with an alignment check on every reply; polish runs once when needed; persist runs once.

`ResponseSource.kind` compose strategy:

| Kind | Compose strategy |
|------|------------------|
| `answer` | pass-through (draft already used `SYSTEM_PROMPT`) |
| `follow_up` | pass-through |
| `confirmation` | LLM wording for wipe prompts; pass-through otherwise |
| `tool_result` | deterministic for health; hinted/LLM for JSON payloads |
| `tool_error` | LLM for JSON payloads; pass-through for plain text |

## Routing

`AgentRouter` is the single routing table for new agent messages:

1. Timer status/cancel (clears pending timer follow-ups)
2. Pending interaction resume
3. Timer start/duration
4. Wipe confirmation
5. Note add/list/lookup
6. Health check tool
7. Pull request tool
8. Direct answer without tools
9. Planner fallback

## Prompt Guide

Edit [`app/assistant/prompts.py`](app/assistant/prompts.py) to change Nano's behavior.

- **Shared primitives** (`_IDENTITY`, `_VOICE`, `_EVIDENCE`, etc.) define reusable rules.
- **Composed constants** (`SYSTEM_PROMPT`, `AGENT_SYSTEM_PROMPT`, `GUARD_REWRITE_SYSTEM_PROMPT`, etc.) combine primitives for each call site.
- **`COMPOSE_HINTS`** holds tool-specific composition rules (for example pull requests).
- **`NOTE_CONTEXT_PREFIX`** formats note context injected in chat mode.

Flow handler `facts` strings (timer follow-ups, note prompts) live in `app/assistant/flows/` and are UX copy, not system prompts.


- `app/main.py` creates the FastAPI application and registers routers.
- `app/api/*` contains the HTTP endpoints.
- `app/cli.py` exposes the command-line interface.
- `app/memory/*` handles the local note and reminder store.
- `app/voice/*` wraps the voice backend.
- `app/tools/*` contains agent tools discovered at runtime.

## Requirements

- Python 3.12 or newer
- SQLite
- A local model file if `LLM_PROVIDER=local`
- A clone of `GLaDOS-TTS` in `vendor/GLaDOS-TTS`, or another importable
  `glados` module, if voice synthesis is enabled

Optional dependencies are grouped in `pyproject.toml`:

- `dev` for tests and linting
- `local-llm` for `llama-cpp-python`
- `voice` for voice synthesis dependencies (currently empty placeholder)

## Install

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,local-llm]"
```

Linux or Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,local-llm]"
```

## Configure

Settings are loaded from environment variables and `.env`.

Common values from `app/config.py`:

- `APP_NAME`
- `APP_ENV`
- `DATABASE_URL`
- `WORKSPACE_ROOT`
- `LLM_PROVIDER`
- `LLM_MODEL_PATH`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_CONTEXT_SIZE`
- `LLM_MAX_TOKENS`
- `LLM_TEMPERATURE`
- `VOICE_BACKEND`
- `VOICE_GLADOS_REPO_PATH`
- `VOICE_SAMPLE_RATE`
- `CHAT_HISTORY_LIMIT`
- `NOTE_CONTEXT_LIMIT`
- `REMINDER_POLL_INTERVAL_SECONDS`
- `HEALTH_CHECK_INTERVAL_SECONDS`
- `HEALTH_TEST_FAILURE_ENABLED`
- `HEALTH_TEST_FAILURE_DETAIL`
- `DATABASE_SIZE_WARNING_BYTES`
- `GIT_EXECUTABLE`
- `GITHUB_CLI_PATH`
- `GITHUB_DEFAULT_BASE_BRANCH`
- `GITHUB_PR_VERIFY_COMMAND`
- `GITHUB_PR_VERIFY_TIMEOUT_SECONDS`
- `PR_NAMING_DIFF_MAX_CHARS`

To intentionally trigger a failing health check while testing diagnostics:

```text
HEALTH_TEST_FAILURE_ENABLED=true
HEALTH_TEST_FAILURE_DETAIL=Testing the warning path.
```

For a local GGUF model, point `LLM_MODEL_PATH` at the file on disk:

```text
LLM_PROVIDER=local
LLM_MODEL_PATH=./models/qwen2.5-1.5b-instruct-q5_k_m.gguf
```

The `models/` directory is the expected place for local model files.

## Database

The SQLite schema is created automatically on startup via `SQLModel.metadata.create_all()`.
Alembic scaffolding under `migrations/` is not used in this project.

## Run

Start the web app:

```powershell
.\.venv\Scripts\python.exe -m app.cli dev
```

Or use the launcher:

```powershell
start-nano
```

The app listens on `127.0.0.1:8000` by default.

## CLI

```powershell
.\.venv\Scripts\python.exe -m app.cli health
.\.venv\Scripts\python.exe -m app.cli chat "Hello"
.\.venv\Scripts\python.exe -m app.cli notes add "Buy milk"
.\.venv\Scripts\python.exe -m app.cli notes list
.\.venv\Scripts\python.exe -m app.cli reminders add "Take meds" "2026-06-21T18:00:00+03:00"
.\.venv\Scripts\python.exe -m app.cli reminders list
```

### Entry Points

- `start-nano` starts the local web app.
- `nano-core` exposes the same Typer application under the package script.

## HTTP API

- `GET /` renders the web UI.
- `GET /health` returns basic service status.
- `GET /api/status` returns the current runtime snapshot.
- `GET /events` streams runtime activity as server-sent events.
- `POST /chat` sends a message to the assistant.
- `GET /api/notes` and `POST /api/notes` manage notes.
- `GET /api/reminders` and `POST /api/reminders` manage reminders.
- `GET /api/voice/status` reports voice backend availability.
- `POST /api/voice` synthesizes speech as `audio/wav`.

## Testing

```powershell
pytest
ruff check .
mypy app
```

## Pull Requests

Nano can open a GitHub pull request when you ask in agent mode (for example: "create a PR").

Prerequisites:

- `git` and the GitHub CLI (`gh`) installed
- If Nano cannot find them automatically, set `GIT_EXECUTABLE` and/or `GITHUB_CLI_PATH` in `.env`
- `gh auth login` completed on the machine
- `WORKSPACE_ROOT` pointing at the repository you want to publish
- A detectable test command in that repository, or `GITHUB_PR_VERIFY_COMMAND` set in `.env`

Nano verifies the project before committing, uses the local model to name the branch and PR in snake_case, creates `feature/<slug>`, commits current changes, pushes, and opens the PR via `gh pr create`.
