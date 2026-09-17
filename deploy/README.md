# Deploy on Raspberry Pi

## AI HAT+ 2 + Nano

Nano uses `hailo-ollama` on port **8000** for LLM inference on the Hailo-10H NPU.
Nano's HTTP API should use a different port (default in `.env.example`: **8080**).

### Prerequisites on the Pi

1. Raspberry Pi 5 with AI HAT+ 2, `hailo-h10-all` installed, `hailortcli fw-control identify` shows `HAILO10H`.
2. GenAI package installed: `hailo_gen_ai_model_zoo_5.1.1_arm64.deb`.
3. `.env` in the repo root with at least:

```env
API_BIND_PORT=8080
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:8000
LLM_MODEL=qwen2.5-instruct:1.5b
```

Pull the model once:

```bash
curl http://localhost:8000/api/pull \
  -H 'Content-Type: application/json' \
  -d '{"model": "qwen2.5-instruct:1.5b", "stream": true}'
```

### Install systemd services

On the Pi, from the nano-core repo:

```bash
sudo ./deploy/install-services.sh
sudo reboot
```

After reboot, both services start automatically:

- `hailo-ollama.service` — Hailo LLM backend (port 8000)
- `nano-core.service` — Nano API (port from `API_BIND_PORT`)

Verify:

```bash
sudo systemctl status hailo-ollama nano-core
curl --silent http://localhost:8000/hailo/v1/list
curl --silent http://localhost:8080/api/health
```

### Kernel updates

If Hailo stops working after `apt full-upgrade`, rebuild the driver:

```bash
sudo apt install --reinstall h10-hailort-pcie-driver
sudo reboot
```
