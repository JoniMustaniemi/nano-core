# Nano — Technical Reference

Product overview and capabilities: [README.md](../README.md).

This document covers the stack, HTTP API, request pipeline, project layout,
background jobs, and architecture.

## Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Persistence | SQLite via SQLModel |
| Scheduling | APScheduler (background jobs) |
| Local LLM | `llama-cpp-python` (optional `local-llm` extra) |
| Voice | GLaDOS-TTS, Vosk STT (optional `voice` extra) |
| Calendar | Google Calendar API (read-only OAuth) |
| Weather | Open-Meteo forecast API (read-only, no API key) |
| Web UI | Separate **nano-ui** repo — thin client over REST + SSE |

Entry points: `app.main` (API server), `app.cli` (`dev`, `serve`, `start-nano`).

## Local model

Nano uses a single GGUF chat model for conversation, agent coordination, and response polish.
The model loads on first use.

| Role | Default file | Used for |
|------|--------------|----------|
| Chat | `qwen2.5-1.5b-instruct-q5_k_m.gguf` | Conversation, agent planning, response polish |

For config paths, context sizing, and remote providers, see [LLM routing](#llm-routing) below.

## Remote deployment

1. Set `API_KEY` and `CORS_ALLOWED_ORIGINS` on the Pi.
2. Expose the API via Tailscale Funnel, Cloudflare Tunnel, or port forwarding.
3. Deploy **nano-ui** and enter the Pi URL + API key in connection settings.

All processing happens on the Pi. The UI displays state from `GET /api/events` (SSE) and sends commands via REST.

## Request pipeline

Agent mode (`AgentOrchestrator`) is the main path for tool-capable chat:

1. Persist user message → `repository.add_chat_message`
2. Route via `AgentRouter` (rule-based intents before LLM planner)
3. Execute: direct answer, tool call, pending interaction, or `AgentPlanner` JSON loop
4. Compose via `ResponseComposer` → polish/guard pipeline → persist assistant reply

`AssistantService` delegates to `AgentOrchestrator` for both agent and chat modes.
Chat mode (`mode=chat`) skips routing/tools and uses `AnswerExecutor` directly inside the orchestrator.

```mermaid
flowchart TD
    UserMsg[User message] --> Orchestrator
    Orchestrator --> Router[AgentRouter]
    Router -->|tool| ToolRunner
    Router -->|planner| Planner[AgentPlanner]
    Router -->|answer| AnswerExecutor
    Planner --> ToolRunner
    ToolRunner --> Composer[ResponseComposer]
    AnswerExecutor --> Composer
    Composer --> ChatModel[Chat LLM]
    Composer --> Persist[(SQLite)]
```

## LLM routing

`get_llm_client()` in `app/llm/factory.py` implements `LLMClient.complete()`.
Local models are loaded lazily via `load_local_model` in `app/llm/context_sizing.py`
(RAM-aware ladder: 32k → 512). If configured context is too large, Nano probes free
memory, tries smaller sizes, and prefixes the next reply with a downgrade notice.
Use the **System analysis** command (or `analyze_system` tool) to inspect specs and
estimated context limits.

| Role | Config path | Context setting | Call sites |
|------|-------------|-----------------|------------|
| Chat | `llm_model_path` | `llm_context_size` (32k) | Orchestrator, service, planner, answer/response pipeline |

Remote providers (`ollama`, `llama_cpp_server`) use `llm_model` for the model name.
Defaults live in `app/config.py`.

## Project layout

| Path | Responsibility |
|------|----------------|
| `app/api/` | REST routers under `/api/*`, API key auth, tool command metadata |
| `app/common/` | Shared JSON parsing, duration parsing, and domain types (`ProactiveOffer`) |
| `app/integrations/google/` | Shared Google OAuth (Calendar + Drive read-only scopes) |
| `app/integrations/google_calendar/` | Google Calendar client and formatting |
| `app/integrations/google_drive/` | Google Drive read-only client, ID parsing, and formatting |
| `app/integrations/weather/` | Open-Meteo client, WMO formatting, and weather errors |
| `app/runtime/location.py` | In-memory client-reported geographic location |
| `app/workspace/` | Workspace file-walking and inventory hashing |
| `app/assistant/` | Orchestrator, dispatch, router, planner, flows, response pipeline |
| `app/assistant/guard/` | Response quality detectors and LLM rewrite pass |
| `app/tools/` | Registered tool handlers (`*_tools.py` register via `registry.py`) |
| `app/tools/files.py` | Core file I/O used by tools; `file_tools.py` registers the tool wrappers |
| `app/timers/` | Timer parsing, operations, formatting, and API serialization |
| `app/memory/` | SQLModel tables, repositories, and schema migrations |
| `app/proactive/` | Proactive offer state for the web UI |
| `app/llm/` | Client, factory, protocol, and provider backends |
| `app/scheduler/` | Timer and health jobs |
| `app/voice/` | `VoiceOutput` protocol, GLaDOS synthesis, Vosk STT, wake listener |
| `app/system/specs/` | Host memory/CPU probes and system analysis report |

## Database

SQLite file from `database_url` (default `./data/nano_core.sqlite3`). Tables in `app/memory/models.py`:

| Table | Purpose |
|-------|---------|
| `ChatMessage` | Per-conversation history |
| `Timer` | Countdown timers |
| `InternalNote` | Deferred follow-ups |

## HTTP API

| Route | Notes |
|-------|-------|
| `POST /api/chat` | Agent or chat mode |
| `GET /api/chat/wake` | Wake acknowledgement |
| `GET /api/health` | Aggregated health checks (public) |
| `GET /api/status` | Activity state + UI copy constants (includes last reported `location`) |
| `GET /api/system/metrics` | CPU temperature and throttle state |
| `POST /api/location` | Store browser-reported latitude/longitude |
| `GET /api/location` | Last reported location (404 if unset) |
| `GET /api/weather/current` | Current weather for last reported location |
| `GET /api/events` | SSE activity stream |
| `GET /api/tool-commands` | Web UI quick commands |
| `GET /api/storage` | Storage snapshot |
| `GET /api/proactive` | Proactive offer state |
| `GET /api/calendar/calendars` | Available Google calendars |
| `GET /api/calendar/default` | Default configured calendar ID |
| `GET /api/calendar/events` | Events in a date range for one calendar |
| `GET /api/drive/files/{file_id}` | Google Drive file metadata (read-only) |
| `GET /api/drive/files/{file_id}/content` | Google Drive file content as text (read-only) |
| `POST /api/voice` | TTS request |
| `GET /api/voice/mode` | Current Pi wake-word listening mode |
| `PUT /api/voice/mode` | Enable/disable Pi wake-word listening |
| `POST /api/voice/transcribe` | STT for uploaded audio |
| `POST /api/voice/command` | STT + agent command in one call |
| `POST /api/timers` | Create countdown timer (`duration_seconds`, optional `label`, optional `start_at`) |
| `PATCH /api/timers/{id}` | Rename active countdown timer |
| `DELETE /api/timers/{id}` | Cancel active countdown timer |
| `PATCH /api/stopwatches/{id}` | Rename active stopwatch |
| `DELETE /api/stopwatches/{id}` | Stop active stopwatch |

`GET /api/status` includes `active_timers[]` entries with `id`, `kind` (`countdown`), `label`, `duration_seconds`, `started_at`, `due_at`, and `remaining_seconds` (UTC instants in ISO-8601).

Protected routes require `Authorization: Bearer <API_KEY>`. SSE also accepts `?api_key=`.

### nano-ui Google Drive contract

Read-only Drive integration for the nano-ui Drive view. Bookmarks stay in browser `localStorage` (`nano.driveLinks`); nano-core has no link registry.

**Preview (optional, non-blocking for chat)**

| Route | Response |
|-------|----------|
| `GET /api/drive/files/{file_id}` | JSON: `id`, `name`, `mime_type`, `size` |
| `GET /api/drive/files/{file_id}/content` | `text/plain`; headers `X-File-Name`, `X-Content-Truncated=true` when clipped |

`file_id` is parsed client-side (same rules as `parse_drive_file_id` / `extract_drive_file_reference` on the server).

**HTTP errors (UI mapping)**

| Status | Meaning |
|--------|---------|
| 503 | Google token missing or invalid — run `nano-core auth-google` on the Pi |
| 404 | File not found |
| 403 | Access denied (sharing) |
| 415 | Binary/non-text file not supported for text preview |
| 502 | Google API failure |

Preview failure does not block chat; the UI may still `POST /api/chat`.

**Ask flow**

- `POST /api/chat` with `mode: "agent"` (unchanged).
- Typical body from nano-ui: `{drive_url_or_file_id}\n\n{user_question}` (question verbatim, any language; no extra scaffolding).
- Agent routing treats a leading Drive URL or file ID as `read_google_drive_file` intent; the planner should call that tool then answer in the user's language.
- Content size is capped by `GOOGLE_DRIVE_MAX_EXPORT_BYTES` (default 1_000_000).

## Background jobs

Registered in `app/scheduler/jobs.py`:

| Job | Interval setting | Action |
|-----|------------------|--------|
| `check_due_timers` | `timer_poll_interval_seconds` | Fire due timers, announce via voice |
| `check_system_health` | `health_check_interval_seconds` | DB, LLM, voice checks; log/announce failures |

## Architecture

```mermaid
flowchart TB
    subgraph client [nano-ui]
        WebUI[Thin display client]
    end

    subgraph api [nano-core API]
        FastAPI
    end

    subgraph assistant [Assistant]
        Orchestrator
        Tools
    end

    subgraph models [Local models]
        direction LR
        ChatModel[Chat model]
    end

    subgraph services [Services]
        direction LR
        Voice
        Scheduler
    end

    SQLite[(SQLite)]

    WebUI -->|REST + SSE| FastAPI --> Orchestrator
    Orchestrator --> ChatModel
    Orchestrator --> Tools
    Orchestrator --> Voice
    Orchestrator --> SQLite
    Tools --> SQLite
    Scheduler --> Tools
```

Data stays on disk (SQLite, workspace files). LLM inference is local unless
`llm_provider` targets Ollama or an external llama.cpp server.
