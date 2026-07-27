# Nano Core

Nano is a local-first personal assistant built in Python. It runs on your own machine,
keeps data local, and uses self-hosted AI models for reasoning. Nano routes two local
Qwen2.5 GGUF models by task: a general instruct model for conversation and a coder
model for self-improvement, codebase review, and pull-request naming. The project is
aimed at everyday use today and installable assistant hardware like Raspberry Pi longer
term.

## What Nano can do

- **Conversation** — answer questions and chat when no tool is needed
- **Memory** — review internal follow-up notes; wipe stored data after confirmation
- **Timers** — start, check, and cancel countdown timers
- **Files and workspace** — read, write, and list files; run small Python scripts locally
- **Health checks** — diagnose database, voice, and model issues in plain language
- **GitHub pull requests** — inspect your changes, run lint and verification, name the work,
  create a feature branch, commit, push, and open a pull request on GitHub when you ask
- **Self-improvement plans** — while idle, review its own codebase and silently draft
  improvement plans in the **Plans** tab; use **Implement** there to apply changes and open a PR
- **Google Calendar** — connect a Google account, browse calendars in the web UI (month, week,
  and day views), switch between calendars, and jump to today; say **"show my calendar"** or use
  the **Open calendar** quick action
- **Voice** — spoken replies, a standby greeting on startup, and wake-phrase listening with
  `"hey nano"`

## Local models

Nano uses two GGUF models and tasks are routed automatically based on type of task:
the **chat** model handles conversation and agent coordination and the **code** model
handles reading source files, drafting improvement plans, scanning the codebase, and
naming pull requests. Each model loads on first use. If no separate code model is
configured, code tasks use the chat model instead.

| Role | Default file | Used for |
|------|--------------|----------|
| Chat | `qwen2.5-1.5b-instruct-q5_k_m.gguf` | Conversation, agent planning, response polish |
| Code | `qwen2.5-coder-1.5b-instruct-q5_k_m.gguf` | Self-improvement plans, codebase crawl, PR naming |

## Google Calendar

Nano can read your Google Calendar events (read-only). Authorization is a one-time OAuth step
on a machine with a browser; the token is saved locally and reused by the app.

1. Create a Google Cloud OAuth client (Desktop app) and download `credentials.json`.
2. Place `credentials.json` in the project root (or set `GOOGLE_CREDENTIALS_PATH` in `.env`).
3. Run authorization:

   ```bash
   nano-core auth-google-calendar
   ```

   This writes `token.json` (gitignored). Re-run if the token expires or is revoked.

4. Optional: list calendar IDs and configure which calendars Nano should use:

   ```bash
   nano-core google-calendars
   ```

   Set `GOOGLE_CALENDAR_IDS` in `.env` to a comma-separated list (default: `primary`).
   `GOOGLE_CALENDAR_TIMEZONE` defaults to `Europe/Helsinki`.

In the web UI, open **Open calendar** or ask Nano to show your calendar. The calendar view
supports month, week, and day layouts, a **Today** shortcut, English/Finnish labels, and
per-calendar color coding. Tests mock the Google API and do not need real credentials.

## Documentation

For a technical overview — architecture and capabilities in more
detail — see [docs/README.md](docs/README.md).
