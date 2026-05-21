"""Reference clip extraction: trim and normalize audio with ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import (
    CLIP_WARN_CEILING,
    MAX_CLIP_SECONDS,
    MIN_CLIP_SECONDS,
    SAMPLE_RATE,
)


def parse_timestamp(value: str) -> float:
    """Parse 'SS', 'MM:SS', or 'HH:MM:SS' (plain seconds allowed) into seconds."""
    parts = str(value).strip().split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid timestamp: {value!r}")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"Invalid timestamp: {value!r}") from None
    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds
