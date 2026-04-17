# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

ARG TORCH_VERSION=2.11.0+cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    XDG_CACHE_HOME=/models/.cache \
    POCKETTTS_MODEL_VARIANT=/app/pockettts-server/config/b6369a24-ungated.yaml \
    POCKETTTS_VOICES_DIR=/models/voices \
    POCKETTTS_DEFAULT_VOICE=alba

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install --prefix=/install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      "torch==${TORCH_VERSION}" \
      "pocket-tts==1.1.1" \
      "fastapi==0.115.12" \
      "uvicorn==0.34.2"

WORKDIR /app
COPY pockettts-server /app/pockettts-server

RUN mkdir -p /models/voices /models/huggingface /models/.cache \
    && curl -fL "https://huggingface.co/kyutai/tts-voices/resolve/main/alba-mackenna/casual.wav" -o /models/voices/alba.wav

# Download model weights and pre-warm default voice cache at build time.
RUN PYTHONPATH=/install/lib/python3.12/site-packages:/app/pockettts-server \
    python /app/pockettts-server/warmup.py


FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    XDG_CACHE_HOME=/models/.cache \
    POCKETTTS_MODEL_VARIANT=/app/pockettts-server/config/b6369a24-ungated.yaml \
    POCKETTTS_VOICES_DIR=/models/voices \
    POCKETTTS_DEFAULT_VOICE=alba \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages:/app/pockettts-server

RUN apt-get update && apt-get install -y --no-install-recommends \
      adduser \
      tini \
      curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system pockettts \
    && adduser --system --ingroup pockettts --home /home/pockettts pockettts

COPY --from=builder /install /usr/local
COPY --from=builder /app/pockettts-server /app/pockettts-server
COPY --from=builder /models /models

RUN mkdir -p /models/huggingface /models/.cache /models/voices /tmp \
    && chown -R pockettts:pockettts /app /models /home/pockettts /tmp

WORKDIR /app/pockettts-server
USER pockettts

EXPOSE 8000

VOLUME ["/models/huggingface", "/models/.cache", "/models/voices"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=10 \
  CMD curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
