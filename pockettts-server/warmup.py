from __future__ import annotations

import os
from pathlib import Path

from pocket_tts.models.tts_model import TTSModel

MODEL_VARIANT = os.environ.get("POCKETTTS_MODEL_VARIANT", "b6369a24")
VOICES_DIR = Path(os.environ.get("POCKETTTS_VOICES_DIR", "/models/voices"))
DEFAULT_VOICE = os.environ.get("POCKETTTS_DEFAULT_VOICE", "alba")


def resolve_default_voice() -> Path:
    candidates = [VOICES_DIR / DEFAULT_VOICE, VOICES_DIR / f"{DEFAULT_VOICE}.wav"]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Default voice '{DEFAULT_VOICE}' missing under {VOICES_DIR}. "
        f"Expected one of: {', '.join(str(c) for c in candidates)}"
    )


def main() -> None:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    model = TTSModel.load_model(MODEL_VARIANT)
    voice_path = resolve_default_voice()
    # Create/cache the default voice conditioning state during build.
    model.get_state_for_audio_prompt(str(voice_path), truncate=True)


if __name__ == "__main__":
    main()
