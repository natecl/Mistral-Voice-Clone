"""Checks for required external command-line tools."""
from __future__ import annotations

import shutil


class MissingDependencyError(RuntimeError):
    """Raised when a required external tool is not installed."""


REQUIRED_TOOLS = {
    "ffmpeg": "Install ffmpeg (macOS: brew install ffmpeg) — https://ffmpeg.org/download.html",
    "ffprobe": "ffprobe ships with ffmpeg — https://ffmpeg.org/download.html",
}


def check_dependencies() -> None:
    """Raise MissingDependencyError if any required external tool is absent."""
    missing = [
        f"  - {tool}: {hint}"
        for tool, hint in REQUIRED_TOOLS.items()
        if shutil.which(tool) is None
    ]
    if missing:
        raise MissingDependencyError(
            "Missing required external tools:\n" + "\n".join(missing)
        )
