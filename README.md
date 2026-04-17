# PocketTTS (Python) in Docker for OpenClaw

## Overview

This repository runs the **Python PocketTTS** implementation locally in Docker and exposes an **OpenAI-compatible** speech endpoint for OpenClaw.

- Uses `pocket_tts` as a Python library (`TTSModel`) with a custom FastAPI server
- CPU-only runtime (no GPU required)
- No OpenAI API key/subscription required
- Works with OpenClaw's built-in OpenAI TTS provider (no custom plugin needed)

## What's in this repo

- `pockettts-server/` - minimal OpenAI-compatible FastAPI server + simple demo UI
- `Dockerfile` - multi-stage image build
- `docker-compose.yml` - host mode
- `docker-compose.openclaw-network.yml` - docker-to-docker mode

The image build:

- installs PocketTTS + server runtime dependencies
- downloads a default voice sample (`alba.wav`)
- preloads model/voice state during build
- starts the FastAPI server on port `8000`

---

## Build the container

```bash
docker build -t pockettts-python:local .
```

---

## OpenClaw on Host

### Start the container

```bash
docker compose up -d
```

By default this binds to `127.0.0.1:8711`.

Health check:

- http://127.0.0.1:8711/health

### Test audio generation

```bash
curl http://localhost:8711/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello from PocketTTS Python",
    "voice": "alba",
    "response_format": "wav"
  }' \
  --output output.wav
```

### Configure OpenClaw

```bash
openclaw config set --batch-json '[
    { "path": "messages.tts.provider", "value": "openai" },
    { "path": "messages.tts.auto", "value": "always" },
    { "path": "messages.tts.providers.openai.apiKey", "value": "ignored" },
    { "path": "messages.tts.providers.openai.baseUrl", "value": "http://localhost:8711/v1" },
    { "path": "messages.tts.providers.openai.model", "value": "ignored" },
    { "path": "messages.tts.providers.openai.voice", "value": "alba" },
    { "path": "messages.tts.providers.openai.responseFormat", "value": "wav" }
  ]'
```

Restart gateway:

```bash
openclaw gateway restart
```

---

## OpenClaw in Docker

### Start the container

```bash
docker compose -f docker-compose.openclaw-network.yml up -d
```

This attaches PocketTTS to the Docker network `openclaw_default` (override via `OPENCLAW_NETWORK`).

Service name on that network is `pockettts-python`.

### Configure OpenClaw (ClawDock)

```bash
clawdock-cli config set --batch-json '[
    { "path": "messages.tts.provider", "value": "openai" },
    { "path": "messages.tts.auto", "value": "always" },
    { "path": "messages.tts.providers.openai.apiKey", "value": "ignored" },
    { "path": "messages.tts.providers.openai.baseUrl", "value": "http://pockettts-python:8000/v1" },
    { "path": "messages.tts.providers.openai.model", "value": "ignored" },
    { "path": "messages.tts.providers.openai.voice", "value": "alba" },
    { "path": "messages.tts.providers.openai.responseFormat", "value": "wav" }
  ]'
```

Restart gateway:

```bash
clawdock-cli gateway restart
```

---

## API surface (OpenAI-compatible subset)

- `POST /v1/audio/speech`
- `GET /health`
- `GET /` (simple test UI)

Supported request behavior:

- `model`: accepted, ignored
- `voice`: resolves `name` or `name.wav` in `/models/voices`
- missing voice falls back to `alba`
- `response_format`: `wav` or `pcm`
- `speed`: ignored
- `stream_format`: ignored

---

## Notes

- Persistent volumes:
  - `/models/huggingface`
  - `/models/.cache`
  - `/models/voices`
- You may see a Hugging Face unauthenticated warning at startup; this is usually benign.

---

## Troubleshooting

```bash
docker compose ps
docker compose logs -f pockettts-python
```

If needed, verify endpoint directly:

```bash
curl -fsS http://127.0.0.1:8711/health
```

