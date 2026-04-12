# PocketTTS Speech Plugin for OpenClaw

When running OpenClaw on your local machine, you may want fast TTS that does not consume additional GPU RAM. This PocketTTS setup uses small models (roughly ~250MB) and runs fully on CPU.

This plugin connects OpenClaw to a local PocketTTS server (typically run in Docker).

## Why this exists

- Local/offline-friendly TTS path
- CPU-only runtime (no extra GPU VRAM pressure)
- Low-friction development and testing with a sidecar container

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- OpenClaw CLI installed

## Deployment modes

You have 3 good connection patterns:

1. **Host OpenClaw (safe default):** publish to `127.0.0.1`
2. **Docker OpenClaw via host:** publish to `0.0.0.0`, connect using `host.docker.internal`
3. **Docker-to-Docker network:** attach PocketTTS to OpenClaw's Docker network and use `http://pockettts:8000`

---

## Mode 1: Host OpenClaw (127.0.0.1)

```bash
cd docker
cp .env.example .env   # optional
# default bind is 127.0.0.1, default host port is 8711
docker compose up -d --build
```

OpenClaw provider URL:

- `http://127.0.0.1:8711`

---

## Mode 2: Docker OpenClaw via host.docker.internal

```bash
cd docker
POCKETTTS_BIND=0.0.0.0 POCKETTTS_PORT=8711 docker compose up -d --build
```

OpenClaw container provider URL:

- `http://host.docker.internal:8711`

> Linux note: if `host.docker.internal` is unavailable in your Docker setup, add host-gateway mapping in the OpenClaw container config.

---

## Mode 3: Same Docker network as OpenClaw (recommended for Docker OpenClaw)

This lets you keep PocketTTS in a separate compose project while still joining OpenClaw's network.

1) Find OpenClaw network (example: `openclaw_default`):

```bash
docker network ls
```

2) Start PocketTTS with the network override:

```bash
cd docker
OPENCLAW_NETWORK=openclaw_default docker compose \
  -f docker-compose.openclaw-network.yml \
  up -d --build
```

OpenClaw container provider URL:

- `http://pockettts:8000`

In this mode, no host port publish is required.

---

## Health check

```bash
curl -fsS http://127.0.0.1:8711/health
```

## Install and enable the plugin

From this project root:

```bash
openclaw plugins install .
openclaw plugins enable pockettts
```

## Configure OpenClaw

In `~/.openclaw/openclaw.json`:

```jsonc
{
  "plugins": {
    "entries": {
      "pockettts": {
        "enabled": true
      }
    }
  },
  "messages": {
    "tts": {
      "provider": "pockettts",
      "auto": "always",
      "providers": {
        "pockettts": {
          "baseUrl": "http://127.0.0.1:8711",
          "endpointPath": "/tts",
          "timeoutMs": 180000,
          "defaultVoice": "alba"
        }
      }
    }
  }
}
```

> `defaultVoiceUrl` is still accepted for compatibility, but recommended values are voice names: `alba`, `marius`, `javert`, `jean`, `fantine`, `cosette`, `eponine`, `azelma`.

Restart OpenClaw gateway after install/config changes.

## Auto-start on machine restart

- `restart: unless-stopped` is already set in compose.
- Ensure Docker itself starts on login/boot:
  - macOS/Windows (Docker Desktop): enable "Start Docker Desktop when you log in"
  - Linux: `sudo systemctl enable docker`

Then your PocketTTS container will come back automatically after reboot.

## Security notes

Current docker setup includes:

- non-root container user
- read-only root filesystem
- dropped Linux capabilities (`cap_drop: [ALL]`)
- `no-new-privileges`
- loopback binding by default (`127.0.0.1`)
- health checks
- `tini` as init process for safe signal handling / child reaping

Extra hardening options you can consider:

- Run behind a local reverse proxy with auth/rate limits if exposing beyond localhost
- Pin image digests for base image and dependencies in CI
- Scan image regularly (Trivy/Grype)

## Troubleshooting

Container status and logs:

```bash
cd docker
docker compose ps
docker compose logs -f pockettts
```

Manual synth test:

```bash
curl -X POST http://127.0.0.1:8711/tts \
  -F 'text=Hello from PocketTTS sidecar' \
  -F 'voice_url=alba' \
  --output /tmp/pockettts-test.wav
```

or make it play directly to aplay (on Linux)

```bash
curl -X POST http://127.0.0.1:8711/tts \
  -F 'text=Hello from PocketTTS HTTP sidecar' \
  -F 'voice_url=azelma' \
  | aplay
```

## Acknowledgements

- This plugin uses [Kyutai PocketTTS](https://github.com/kyutai-labs/pocket-tts).
- Huge thanks to the Kyutai team for releasing PocketTTS.

## License

MIT (see `LICENSE`).
