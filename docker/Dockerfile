FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    XDG_CACHE_HOME=/models/.cache

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      tini \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system pockettts && adduser --system --ingroup pockettts --home /home/pockettts pockettts

RUN pip install --disable-pip-version-check "pocket-tts==1.1.1"

RUN mkdir -p /models/huggingface /models/.cache /tmp \
    && chown -R pockettts:pockettts /models /home/pockettts /tmp

WORKDIR /home/pockettts
USER pockettts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["pocket-tts", "serve", "--host", "0.0.0.0", "--port", "8000"]
