# Nano Core

Nano is a local-first personal assistant built in Python. It runs on your own machine,
keeps data local, and uses a self-hosted AI model for reasoning. The project is
aimed at everyday use today and installable assistant hardware like Raspberry Pi longer
term.

## What Nano can do

- **Conversation** — answer questions and chat when no tool is needed
- **Memory** — review internal follow-up notes; wipe stored data after confirmation
- **Timers** — start, check, and cancel countdown timers
- **Files and workspace** — read, write, and list files; run small Python scripts locally
- **Health checks** — diagnose database, voice, and model issues in plain language
- **System control** — reboot the Raspberry Pi or restart the nano-core service from the UI after confirmation (when enabled)
- **Google Calendar** — connect a Google account, browse calendars in the UI and switch between calendars.
- **Voice** — spoken replies on the Pi speaker, push-to-talk from the remote UI, and wake-phrase listening with `"hey nano"` on Pi hardware

## Web UI

The web UI lives in the sibling [**nano-ui**](../nano-ui) repository. Nano Core is API-only: run `nano-core serve` on your Pi and connect the hosted UI with your API URL and key.

## Local model

Nano uses a single GGUF chat model for conversation, agent coordination, and response polish.
The model loads on first use.

| Role | Default file | Used for |
|------|--------------|----------|
| Chat | `qwen2.5-1.5b-instruct-q5_k_m.gguf` | Conversation, agent planning, response polish |

## Documentation

For a technical overview — architecture and capabilities in more
detail — see [docs/README.md](docs/README.md).

## Local development

```bash
python -m pip install -e ".[dev]"
nano-core dev
```

Run the test suite:

```bash
pytest
```

Lint and type-check:

```bash
ruff check app tests
mypy app
```
