"""Download audio from a YouTube URL using yt-dlp."""
from __future__ import annotations

from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadError


def download_audio(url: str, out_dir: Path | str) -> Path:
    """Download the best audio track from `url` as a WAV file in `out_dir`.

    Returns the path to the downloaded WAV file. Raises RuntimeError if the
    download fails or produces no file.
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
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    if not info:
        raise RuntimeError(f"yt-dlp returned no info for URL: {url}")

    audio_path = out_dir / f"{info['id']}.wav"
    if not audio_path.exists():
        raise RuntimeError(
            f"Download did not produce the expected file: {audio_path}"
        )
    return audio_path
