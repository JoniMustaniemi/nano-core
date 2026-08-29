# Nano Core

Nano is a local-first personal assistant built in Python. It runs on your own machine,
keeps data local, and uses self-hosted AI models for reasoning. Nano routes two local
Qwen2.5 GGUF models by task: a general instruct model for conversation and a coder
model for pull-request naming and other code tasks. The project is
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
- **System control** — reboot the Raspberry Pi or restart the nano-core service from the UI after confirmation (when enabled)
- **Google Calendar** — connect a Google account, browse calendars in the UI and switch between calendars.
- **Voice** — spoken replies on the Pi speaker, push-to-talk from the remote UI, and wake-phrase listening with `"hey nano"` on Pi hardware

## Web UI

The web UI lives in the sibling [**nano-ui**](../nano-ui) repository. Nano Core is API-only: run `nano-core serve` on your Pi and connect the hosted UI with your API URL and key.

## Local models

Nano uses two GGUF models and tasks are routed automatically based on type of task:
the **chat** model handles conversation and agent coordination and the **code** model
handles reading source files and naming pull requests. Each model loads on first use. If no separate code model is
configured, code tasks use the chat model instead.

| Role | Default file | Used for |
|------|--------------|----------|
| Chat | `qwen2.5-1.5b-instruct-q5_k_m.gguf` | Conversation, agent planning, response polish |
| Code | `qwen2.5-coder-1.5b-instruct-q5_k_m.gguf` | PR naming and other code tasks |

## Documentation

For a technical overview — architecture and capabilities in more
detail — see [docs/README.md](docs/README.md).
