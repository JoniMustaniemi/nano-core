# Nano Core

[![CodeFactor](https://www.codefactor.io/repository/github/jonimustaniemi/nano-core/badge)](https://www.codefactor.io/repository/github/jonimustaniemi/nano-core)

Nano is a local-first personal assistant built in Python. It runs on your own machine,
keeps data local, and uses a self-hosted AI model for reasoning. The current default
model is Qwen2.5-1.5B-Instruct in GGUF format. The project is aimed at everyday use today and
installable assistant hardware like Raspberry Pi longer term.

## What Nano can do

- **Conversation** — answer questions and chat when no tool is needed
- **Notes and memory** — save, list, and look up notes; review internal follow-up notes
- **Reminders and timers** — schedule reminders; start, check, and cancel timers
- **Files and workspace** — read, write, and list files; run small Python scripts locally
- **Health checks** — diagnose database, voice, and model issues in plain language
- **GitHub pull requests** — inspect your changes, run lint and verification, name the work,
  create a feature branch, commit, push, and open a pull request on GitHub when you ask
- **Self-improvement plans** — during idle time, review its own codebase and draft readable
  improvement plans; read them in the **Plans** tab and mark them processed when done
- **Voice** — optional spoken replies and wake-phrase listening with `"hey nano"` in the web UI

## Web interface

Open the home screen in your browser after starting Nano. The UI includes:

- A main response area and optional voice controls
- Quick commands drawer for common actions
- **Nano sheet** in the bottom-left corner with three views:
  - **Brains** — internal activity log
  - **Plans** — improvement plans Nano has drafted; click to read, then mark as processed
  - **Stored Data** — snapshot of notes, reminders, chat, and internal notes

## Quick start

Requires Python 3.12+.

```bash
pip install -e ".[dev,local-llm]"
cp .env.example .env
# Set LLM_MODEL_PATH to your GGUF model file in .env
start-nano
# or: nano-core dev
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

CLI examples:

```bash
nano-core chat "What can you do?"
nano-core notes add "Buy milk" --name groceries
nano-core reminders add "Stand up" 2026-07-23T15:00:00
```

Copy `.env.example` to `.env` and adjust settings for your model path, voice backend,
and GitHub tooling if you use pull requests.

## Documentation

For a technical overview — architecture, components, privacy, and capabilities in more
detail — see [docs/README.md](docs/README.md).
