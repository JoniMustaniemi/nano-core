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
- **Self-improvement plans** — while idle, review its own codebase and draft readable
  improvement plans in the **Plans** tab for you to review and implement if you so choose
- **Voice** — spoken replies and wake-phrase listening with `"hey nano"`

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


## Documentation

For a technical overview — architecture and capabilities in more
detail — see [docs/README.md](docs/README.md).
