"""Mistral Voxtral speech generation."""
from __future__ import annotations

import base64
import time
from pathlib import Path

from .config import MODEL

# 500 is included because the Mistral API surfaces some transient errors as 500.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def synthesize(client, voice_id: str, text: str, out_path: str | Path,
               response_format: str = "mp3", max_retries: int = 3) -> Path:
    """Generate speech in `voice_id` from `text`, writing audio to `out_path`.

    Retries with exponential backoff on rate-limit (429) and server (5xx)
    errors. Returns the output Path.
    """
    attempt = 0
    while True:
        try:
            response = client.audio.speech.complete(
                model=MODEL,
                input=text,
                voice_id=voice_id,
                response_format=response_format,
            )
            break
        except Exception as exc:  # noqa: BLE001 - re-raised below if not retryable
            status = getattr(exc, "status_code", None)
            attempt += 1
            if status in RETRYABLE_STATUS and attempt <= max_retries:
                time.sleep(2 ** attempt)
                continue
            raise

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(response.audio_data))
    return out_path
