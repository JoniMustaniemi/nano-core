# Nano — Technical Overview

User-facing capabilities and model overview: [README.md](../README.md).

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

## Remote deployment

1. Set `API_KEY` and `CORS_ALLOWED_ORIGINS` on the Pi.
2. Expose the API via Tailscale Funnel, Cloudflare Tunnel, or port forwarding.
3. Deploy **nano-ui** and enter the Pi URL + API key in connection settings.

All processing happens on the Pi. The UI displays state from `GET /api/events` (SSE) and sends commands via REST.

## Pi deployment

One-time setup on the Raspberry Pi:

1. Clone the repo via SSH: `git clone git@github.com:ORG/nano-core.git`
2. Generate a deploy key on the Pi and add the read-only public key to the GitHub repo.
3. Create a venv, install extras, copy models, and configure `.env`:

```env
API_KEY=...
CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
AUTO_UPDATE_ON_START=true
AUTO_UPDATE_BRANCH=main
```

4. Install passwordless sudo rules for reboot and service restart (required before enabling system control in `.env`):

```bash
sudo cp deploy/sudoers/nano-reboot /etc/sudoers.d/nano-reboot
sudo cp deploy/sudoers/nano-service /etc/sudoers.d/nano-service
sudo chmod 440 /etc/sudoers.d/nano-reboot /etc/sudoers.d/nano-service
sudo visudo -c
```

Test as the `nano` user (should not ask for a password):

```bash
sudo -n /bin/systemctl status nano-core
# sudo -n /usr/sbin/reboot   # only when you intend to reboot
```

5. Install and enable the systemd unit:

```bash
sudo cp deploy/nano-core.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nano-core
```

With `AUTO_UPDATE_ON_START=true`, every boot or service restart runs `git fetch` + `git merge --ff-only origin/main` before `nano-core serve`. Pull failures (no network, dirty tree, merge conflict) are logged and startup continues with the local checkout.

Optional: set `AUTO_UPDATE_INSTALL=true` to run `pip install -e ".[local-llm,voice]"` after a successful pull (slow on Pi; only needed when dependencies change).

After the initial setup, push to `main` and restart the service (or reboot) to deploy code changes — no manual `scp` required.

To let Nano reboot or restart itself from chat, enable the flags in `.env` **only after** sudoers is configured:

```env
REBOOT_ENABLED=true
SERVICE_RESTART_ENABLED=true
```

Never grant `NOPASSWD: ALL` — use only the narrow command lists in `deploy/sudoers/`.
Keep both flags `false` on dev machines and non-Pi hosts.

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
| `app/integrations/google_calendar/` | Google Calendar auth, client, and formatting |
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
| `POST /api/voice` | TTS request |
| `GET /api/voice/mode` | Current Pi wake-word listening mode |
| `PUT /api/voice/mode` | Enable/disable Pi wake-word listening |
| `POST /api/voice/transcribe` | STT for uploaded audio |
| `POST /api/voice/command` | STT + agent command in one call |

Protected routes require `Authorization: Bearer <API_KEY>`. SSE also accepts `?api_key=`.

## Background jobs

Registered in `app/scheduler/jobs.py`:

| Job | Interval setting | Action |
|-----|------------------|--------|
| `check_due_timers` | `timer_poll_interval_seconds` | Fire due timers, announce via voice |
| `check_system_health` | `health_check_interval_seconds` | DB, LLM, voice checks; log/announce failures |

## Configuration

Settings live in `app/config.py`. Override any value in `.env` if needed — most
defaults work out of the box, including model paths under `models/`.

Remote API: `API_KEY`, `CORS_ALLOWED_ORIGINS`, `API_BIND_HOST`, `API_BIND_PORT`.

Pi auto-update: `AUTO_UPDATE_ON_START`, `AUTO_UPDATE_BRANCH`, `AUTO_UPDATE_INSTALL`.

Pi reboot: `REBOOT_ENABLED` (requires passwordless reboot commands for the service user).

Pi service restart: `SERVICE_RESTART_ENABLED`, `SERVICE_UNIT_NAME` (default `nano-core`).

On the Pi, install narrow sudoers rules from the repo (do this before enabling the flags above):

```bash
sudo cp deploy/sudoers/nano-reboot /etc/sudoers.d/nano-reboot
sudo cp deploy/sudoers/nano-service /etc/sudoers.d/nano-service
sudo chmod 440 /etc/sudoers.d/nano-reboot /etc/sudoers.d/nano-service
sudo visudo -c
```

`nano-reboot` allows only: `/usr/sbin/reboot`, `/usr/sbin/shutdown`, `/bin/systemctl reboot`, `/bin/systemctl poweroff`.

`nano-service` allows only: `/bin/systemctl restart nano-core`, `/bin/systemctl status nano-core`.

Without sudoers, `sudo` prompts for a password and reboot/restart fails from the systemd service.

Voice: `VOICE_INPUT_ENABLED` (boot default for Pi wake-word listening; runtime toggle via `PUT /api/voice/mode`),
`VOICE_INPUT_DEVICE`, `VOICE_OUTPUT_DEVICE`, `STT_MODEL_PATH`,
`VOICE_WAKE_PHRASE`, `VOICE_PLAYBACK_MODE` (`local`, `browser`, or `both`).

Google Calendar settings: `GOOGLE_CREDENTIALS_PATH`, `GOOGLE_TOKEN_PATH`,
`GOOGLE_CALENDAR_TIMEZONE`, `GOOGLE_CALENDAR_IDS`. CLI: `auth-google-calendar`,
`google-calendars`.

Weather: `WEATHER_TIMEOUT_SECONDS` (default 10). No API key — forecasts come from
Open-Meteo. Location is not configured in `.env`; the web UI reports coordinates via
`POST /api/location` (browser geolocation). Weather endpoints and the
`get_current_weather` tool use that in-memory location until the next UI report.

Install extras from `pyproject.toml` as needed: `local-llm` for GGUF models,
`voice` for Vosk STT, `dev` for tests and linting.

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
