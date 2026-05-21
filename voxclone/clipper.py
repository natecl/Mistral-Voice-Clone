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


def extract_clip(src: Path | str, start: str, end: str, out_path: Path | str) -> Path:
    """Trim src to [start, end], convert to mono 24 kHz WAV, loudness-normalize.

    Returns the output Path. Warns (does not fail) when the clip length falls
    outside the range Voxtral works best with.
    """
    start_s = parse_timestamp(start)
    end_s = parse_timestamp(end)
    duration = end_s - start_s
    if duration <= 0:
        raise ValueError(
            f"end ({end}) must be after start ({start})"
        )
    if duration < MIN_CLIP_SECONDS or duration > CLIP_WARN_CEILING:
        print(
            f"Warning: reference clip is {duration:.1f}s. Voxtral works "
            f"best with {MIN_CLIP_SECONDS:.0f}-{MAX_CLIP_SECONDS:.0f}s "
            f"of clean speech."
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s),
        "-i", str(src),
        "-t", str(duration),
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-af", "loudnorm",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract clip:\n{result.stderr}")
    return out_path
