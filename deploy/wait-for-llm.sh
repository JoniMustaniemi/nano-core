#!/usr/bin/env bash
# Wait for the configured remote LLM backend before starting nano-core.
# Used as ExecStartPre in nano-core.service on Raspberry Pi deployments.

set -euo pipefail

provider="${LLM_PROVIDER:-local}"
base_url="${LLM_BASE_URL:-}"

case "${provider}" in
  ollama | auto | llama_cpp_server)
    ;;
  *)
    exit 0
    ;;
esac

if [[ -z "${base_url}" ]]; then
  exit 0
fi

base_url="${base_url%/}"
max_attempts=60
sleep_seconds=2

for ((attempt = 1; attempt <= max_attempts; attempt++)); do
  if curl -sf --connect-timeout 2 "${base_url}/hailo/v1/list" >/dev/null 2>&1; then
    exit 0
  fi
  if curl -sf --connect-timeout 2 "${base_url}/api/tags" >/dev/null 2>&1; then
    exit 0
  fi
  sleep "${sleep_seconds}"
done

echo "Timed out waiting for LLM backend at ${base_url}" >&2
exit 1
