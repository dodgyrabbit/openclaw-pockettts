# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

ARG POCKETTTS_CPP_REPO=https://github.com/VolgaGerm/PocketTTS.cpp.git
ARG POCKETTTS_CPP_REF=master
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      git \
      pkg-config \
    && rm -rf /var/lib/apt/lists/*

# CMake >= 3.28 is required by PocketTTS.cpp
RUN pip install --upgrade pip setuptools wheel \
    && pip install cmake ninja

RUN git clone "${POCKETTTS_CPP_REPO}" /src/PocketTTS.cpp \
    && git -C /src/PocketTTS.cpp checkout "${POCKETTTS_CPP_REF}"

WORKDIR /src/PocketTTS.cpp

# Dependencies for export_onnx.py
RUN pip install \
      --extra-index-url "${TORCH_INDEX_URL}" \
      torch \
    && pip install \
      "pocket-tts @ git+https://github.com/kyutai-labs/pocket-tts.git" \
      onnx \
      onnxruntime

# 1) Convert/download upstream PocketTTS models to ONNX
RUN python export_onnx.py --no-validate

# 2) Build C++ runtime + HTTP server executable
RUN cmake -S . -B .build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    && cmake --build .build --config Release -j"$(nproc)"

# 3) Seed voices directory with one voice sample named exactly "alba"
RUN mkdir -p voices \
    && curl -fL "https://huggingface.co/kyutai/tts-voices/resolve/main/alba-mackenna/casual.wav" -o voices/alba

# 4) Warm up once so voices/.cache is populated in the image
RUN ./pocket-tts \
      --models-dir models \
      --voices-dir voices \
      --tokenizer models/tokenizer.model \
      "Container warmup voice-cache generation." \
      alba \
      /tmp/warmup.wav \
    && rm -f /tmp/warmup.wav


FROM debian:bookworm-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    LD_LIBRARY_PATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      libgcc-s1 \
      libgomp1 \
      libstdc++6 \
      tini \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system pockettts \
    && adduser --system --ingroup pockettts --home /home/pockettts pockettts

WORKDIR /app

COPY --from=builder /src/PocketTTS.cpp/pocket-tts /app/pocket-tts
COPY --from=builder /src/PocketTTS.cpp/libonnxruntime.so* /app/
COPY --from=builder /src/PocketTTS.cpp/models /app/models
COPY --from=builder /src/PocketTTS.cpp/voices /app/voices

RUN if [ -f /app/libonnxruntime.so ] && [ ! -e /app/libonnxruntime.so.1 ]; then \
      ln -s /app/libonnxruntime.so /app/libonnxruntime.so.1; \
    fi \
    && chown -R pockettts:pockettts /app /home/pockettts

# Persist voice files and generated cache between container lifecycles.
VOLUME ["/app/voices"]

USER pockettts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=10 \
  CMD curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/pocket-tts", "--server", "--port", "8000", "--models-dir", "/app/models", "--voices-dir", "/app/voices", "--tokenizer", "/app/models/tokenizer.model"]
