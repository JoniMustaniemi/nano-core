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

External local services such as GLaDOS-TTS and systemd are installed and
managed outside the Python package.

## Raspberry Pi / Linux

This project is designed to install cleanly on Raspberry Pi or other Linux
systems with Python 3.12+ available.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,local-llm]"
```

The app starts with:

```bash
nano-core dev
```

For a true local model, set `LLM_PROVIDER=local` and point `LLM_MODEL_PATH`
at a `.gguf` file on disk. Nano loads that model directly in-process through
`llama-cpp-python`.

The web UI now expects a local `GLaDOS-TTS` backend import on the server side.
Clone the repository into `vendor/GLaDOS-TTS` or otherwise make the `glados`
module importable to Python.

If you still want to use a server-based backend for testing, you can switch
`LLM_PROVIDER` to `ollama` or `llama_cpp_server`, but the default path is
local.

## Model Download

Download the GGUF file into `models/` and keep it out of Git.

Recommended source:

- [Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)

For a Raspberry Pi 5, start with a 4-bit or 5-bit quantization if available,
such as `Q4_K_M` or `Q5_K_M`.

Then point `LLM_MODEL_PATH` at the downloaded file, for example:

```text
LLM_MODEL_PATH=./models/qwen2.5-1.5b-instruct-q5_k_m.gguf
```


## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,local-llm]"
```

## Run

```powershell
uvicorn app.main:app --reload
```

Or start the full app through the project CLI:

```powershell
nano-core dev
```

Or, from the project root, run the launcher directly:

```powershell
.\nano-core.cmd
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
