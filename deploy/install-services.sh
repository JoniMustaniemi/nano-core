#!/usr/bin/env bash
# Install nano-core and hailo-ollama systemd units on Raspberry Pi.
# Run on the Pi: sudo ./deploy/install-services.sh

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HAILO_BIN="$(command -v hailo-ollama || true)"

if [[ -z "${HAILO_BIN}" ]]; then
  echo "hailo-ollama not found. Install the GenAI package first:" >&2
  echo "  sudo dpkg -i hailo_gen_ai_model_zoo_5.1.1_arm64.deb" >&2
  exit 1
fi

install -m 644 "${SCRIPT_DIR}/hailo-ollama.service" /etc/systemd/system/hailo-ollama.service
install -m 644 "${SCRIPT_DIR}/nano-core.service" /etc/systemd/system/nano-core.service

if [[ "${HAILO_BIN}" != "/usr/bin/hailo-ollama" ]]; then
  sed -i "s|^ExecStart=.*|ExecStart=${HAILO_BIN} serve|" /etc/systemd/system/hailo-ollama.service
fi

chmod +x "${SCRIPT_DIR}/wait-for-llm.sh"

systemctl daemon-reload
systemctl enable hailo-ollama.service nano-core.service
systemctl restart hailo-ollama.service
systemctl restart nano-core.service || systemctl start nano-core.service

echo "Installed and enabled:"
echo "  hailo-ollama.service  (LLM on http://127.0.0.1:8000)"
echo "  nano-core.service     (API; configure API_BIND_PORT in .env)"
echo
systemctl status hailo-ollama.service --no-pager -l || true
