# PocketTTS for OpenClaw (OpenAI-compatible local TTS)

This project runs PocketTTS in Docker and exposes an **OpenAI-compatible** speech endpoint:

- `POST /v1/audio/speech`
- `GET /health`
- `GET /` (simple built-in demo UI)

The server is CPU-only and intended as a local sidecar for OpenClaw.

---

## Current direction (important)

This repository still includes an OpenClaw plugin, but the container now speaks an OpenAI-style TTS API directly.

Because of that, we may **deprecate the plugin** in favor of using OpenClaw's standard OpenAI TTS configuration directly (simpler and more portable).

---

## What changed vs the old setup

Previously, PocketTTS used a form-based `/tts` endpoint (`text` + `voice_url`).

Now the main container serves an OpenAI-compatible endpoint with JSON payloads:

```json
{
  "model": "tts-1",
  "input": "Hello world",
  "voice": "alba",
  "response_format": "wav"
}
```

### Supported subset

- `model`: accepted, ignored
- `input`: required
- `voice`: voice clone file name lookup (`name` or `name.wav`)
  - fallback to `alba` if missing
- `response_format`: `wav` or `pcm`
- `speed`: accepted, ignored
- `stream_format`: accepted, ignored (defaults to audio)

Responses are streamed with chunked transfer encoding.

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- OpenClaw CLI (if using plugin path)

---

## Deployment modes

You can run in three common patterns:

1. **Host OpenClaw (safe default):** publish to `127.0.0.1`
2. **Docker OpenClaw via host:** publish to `0.0.0.0`, connect via `host.docker.internal`
3. **Docker-to-Docker network:** attach to OpenClaw network and use `http://pockettts:8000`

---

## Mode 1: Host OpenClaw (127.0.0.1)

```bash
cd docker
cp .env.example .env   # optional
# default bind is 127.0.0.1, default host port is 8711
docker compose up -d --build
```

Provider URL:

- `http://127.0.0.1:8711`

---

## Mode 2: Docker OpenClaw via host.docker.internal

```bash
cd docker
POCKETTTS_BIND=0.0.0.0 POCKETTTS_PORT=8711 docker compose up -d --build
```

Provider URL from OpenClaw container:

- `http://host.docker.internal:8711`

> Linux note: if `host.docker.internal` is unavailable in your Docker setup, add host-gateway mapping in OpenClaw container config.

---

## Mode 3: Same Docker network as OpenClaw

1) Find OpenClaw network (for example `openclaw_default`):

```bash
docker network ls
```

2) Start with network override:

```bash
cd docker
OPENCLAW_NETWORK=openclaw_default docker compose \
  -f docker-compose.openclaw-network.yml \
  up -d --build
```

Provider URL from OpenClaw container:

- `http://pockettts:8000`

---

## Health check

```bash
curl -fsS http://127.0.0.1:8711/health
```

---

## Quick API test (OpenAI-compatible)

```bash
curl -X POST http://127.0.0.1:8711/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "tts-1",
    "input": "Hello from local PocketTTS",
    "voice": "alba",
    "response_format": "wav"
  }' \
  --output /tmp/pockettts-test.wav
```

PCM test:

```bash
curl -X POST http://127.0.0.1:8711/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "tts-1",
    "input": "Hello PCM",
    "voice": "alba",
    "response_format": "pcm"
  }' \
  --output /tmp/pockettts-test.pcm
```

---

## Built-in demo UI

Open:

- `http://127.0.0.1:8711/`

It provides a small page to test text, voice name, and output format.

---

## About Hugging Face warning at startup

You may see:

> "You are sending unauthenticated requests to the HF Hub..."

This is from `huggingface_hub`. It does **not always** mean a large download happened at that moment.

- If model/tokenizer/voice artifacts already exist in cache volumes, startup generally reuses them.
- On a fresh volume, first startup may fetch assets.

This compose setup persists these volumes:

- `/models/huggingface`
- `/models/.cache`
- `/models/voices`

So normal restarts should be warm.

---

## Plugin usage (optional for now)

If you still want to use this repo's plugin:

```bash
openclaw plugins install .
openclaw plugins enable pockettts
```

Current plugin defaults to OpenAI-style endpoint behavior.

Example plugin provider config in `~/.openclaw/openclaw.json`:

```jsonc
{
  "messages": {
    "tts": {
      "provider": "pockettts",
      "auto": "always",
      "providers": {
        "pockettts": {
          "baseUrl": "http://127.0.0.1:8711",
          "endpointPath": "/v1/audio/speech",
          "timeoutMs": 180000,
          "defaultVoice": "alba",
          "responseFormat": "wav"
        }
      }
    }
  }
}
```

---

## Security notes

Current Docker setup includes:

- non-root runtime user
- read-only root filesystem (compose)
- dropped Linux capabilities (`cap_drop: [ALL]`)
- `no-new-privileges`
- loopback binding by default (`127.0.0.1`)
- health checks
- `tini` init process

---

## Troubleshooting

```bash
cd docker
docker compose ps
docker compose logs -f pockettts
```

If audio requests fail, verify:

- `GET /health` is 200
- voice exists under `/models/voices` (or fallback `alba` exists)
- endpoint path is `/v1/audio/speech`

---

## Acknowledgements

- [Kyutai PocketTTS](https://github.com/kyutai-labs/pocket-tts)
- Thanks to the Kyutai team for open-sourcing PocketTTS.

## License

MIT (see `LICENSE`).
