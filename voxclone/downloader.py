"""Download audio from a YouTube URL using yt-dlp."""
from __future__ import annotations

from pathlib import Path

import yt_dlp


def download_audio(url: str, out_dir) -> Path:
    """Download the best audio track from `url` as a WAV file in `out_dir`.

    Returns the path to the downloaded WAV file. Raises RuntimeError if the
    download produced no file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    audio_path = out_dir / f"{info['id']}.wav"
    if not audio_path.exists():
        raise RuntimeError(
            f"Download did not produce the expected file: {audio_path}"
        )
    return audio_path
