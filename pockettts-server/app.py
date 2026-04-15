from __future__ import annotations

import io
import logging
import os
import threading
from pathlib import Path
from queue import Queue
from typing import Generator, Literal

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from pocket_tts.data.audio import stream_audio_chunks
from pocket_tts.models.tts_model import TTSModel

logger = logging.getLogger("pockettts_server")

MODEL_VARIANT = os.environ.get("POCKETTTS_MODEL_VARIANT", "b6369a24")
VOICES_DIR = Path(os.environ.get("POCKETTTS_VOICES_DIR", "/models/voices"))
DEFAULT_VOICE = os.environ.get("POCKETTTS_DEFAULT_VOICE", "alba")


class SpeechRequest(BaseModel):
    # OpenAI-compatible request body (subset)
    model: str = "gpt-4o-mini-tts"  # ignored
    input: str = Field(..., min_length=1)
    voice: str | None = None
    response_format: Literal["wav", "pcm"] = "wav"
    speed: float | None = None  # ignored
    stream_format: str | None = None  # ignored (defaults to audio)


class QueueFile(io.IOBase):
    """Tiny file-like writer that streams bytes through a Queue."""

    def __init__(self, queue: Queue):
        self.queue = queue
        self._closed = False

    def write(self, data: bytes) -> int:
        self.queue.put(data)
        return len(data)

    def flush(self) -> None:  # noqa: D401
        return None

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.queue.put(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class PocketRuntime:
    """Holds model + cached voice states. Guarded by a lock (model is not thread-safe)."""

    def __init__(self):
        self.model: TTSModel | None = None
        self._generation_lock = threading.Lock()
        self._voice_state_cache: dict[Path, dict] = {}

    def load(self) -> None:
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Loading PocketTTS model variant=%s", MODEL_VARIANT)
        self.model = TTSModel.load_model(MODEL_VARIANT)
        logger.info("PocketTTS ready (sample_rate=%s)", self.model.sample_rate)

    def resolve_voice_path(self, requested: str | None) -> Path:
        # keep this intentionally strict + simple: names only (no URL fetch here)
        chosen = (requested or "").strip()
        if not chosen:
            chosen = DEFAULT_VOICE
        chosen = Path(chosen).name  # strip any path traversal

        candidates = [VOICES_DIR / chosen, VOICES_DIR / f"{chosen}.wav"]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        # fallback to default "alba"
        default_candidates = [VOICES_DIR / DEFAULT_VOICE, VOICES_DIR / f"{DEFAULT_VOICE}.wav"]
        for candidate in default_candidates:
            if candidate.exists() and candidate.is_file():
                logger.warning("Voice '%s' not found. Falling back to '%s'.", chosen, DEFAULT_VOICE)
                return candidate

        raise HTTPException(
            status_code=500,
            detail=(
                f"Requested voice '{chosen}' not found and default voice '{DEFAULT_VOICE}' is missing. "
                f"Expected files under {VOICES_DIR}."
            ),
        )

    def _get_state_for_voice(self, voice_path: Path) -> dict:
        cached = self._voice_state_cache.get(voice_path)
        if cached is not None:
            return cached

        assert self.model is not None
        state = self.model.get_state_for_audio_prompt(str(voice_path), truncate=True)
        self._voice_state_cache[voice_path] = state
        return state

    def pcm_stream(self, text: str, voice_path: Path) -> Generator[bytes, None, None]:
        assert self.model is not None
        with self._generation_lock:
            model_state = self._get_state_for_voice(voice_path)
            for chunk in self.model.generate_audio_stream(
                model_state=model_state,
                text_to_generate=text,
                copy_state=True,
            ):
                pcm16 = (chunk.clamp(-1, 1) * 32767).to(torch.int16).cpu().numpy().tobytes()
                if pcm16:
                    yield pcm16

    def wav_stream(self, text: str, voice_path: Path) -> Generator[bytes, None, None]:
        assert self.model is not None
        queue: Queue = Queue(maxsize=32)

        def worker() -> None:
            writer = QueueFile(queue)
            try:
                with self._generation_lock:
                    model_state = self._get_state_for_voice(voice_path)
                    audio_chunks = self.model.generate_audio_stream(
                        model_state=model_state,
                        text_to_generate=text,
                        copy_state=True,
                    )
                    stream_audio_chunks(writer, audio_chunks, self.model.sample_rate)
            except Exception as exc:  # pragma: no cover - defensive path
                logger.exception("WAV streaming failed")
                queue.put(exc)
                writer.close()

        threading.Thread(target=worker, daemon=True).start()

        while True:
            item = queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item


runtime = PocketRuntime()
app = FastAPI(title="PocketTTS OpenAI-Compatible Server", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    runtime.load()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/audio/speech")
def create_speech(payload: SpeechRequest):
    text = payload.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="'input' must not be empty")

    voice_path = runtime.resolve_voice_path(payload.voice)

    if payload.response_format == "pcm":
        return StreamingResponse(
            runtime.pcm_stream(text, voice_path),
            media_type="audio/pcm",
            headers={"Transfer-Encoding": "chunked"},
        )

    return StreamingResponse(
        runtime.wav_stream(text, voice_path),
        media_type="audio/wav",
        headers={"Transfer-Encoding": "chunked"},
    )
