"""Mistral Voxtral voice creation and management."""
from __future__ import annotations

import base64
from pathlib import Path


def create_voice(client, name: str, clip_path, languages: list[str]) -> str:
    """Create a saved Voxtral voice from a reference clip; return the voice id.

    `client` is an authenticated mistralai.Mistral instance. `clip_path` points
    to a short reference audio file (Voxtral works best with 3-10 s of clean
    speech).
    """
    clip_path = Path(clip_path)
    sample_b64 = base64.b64encode(clip_path.read_bytes()).decode()
    voice = client.audio.voices.create(
        name=name,
        sample_audio=sample_b64,
        sample_filename=clip_path.name,
        languages=languages,
    )
    return voice.id
