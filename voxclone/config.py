"""Configuration: API key loading, Mistral client factory, constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from mistralai.client import Mistral

MODEL = "voxtral-mini-tts-2603"
SAMPLE_RATE = 24000
MIN_CLIP_SECONDS = 3.0
MAX_CLIP_SECONDS = 10.0
CLIP_WARN_CEILING = 15.0
REGISTRY_PATH = Path(".voxclone/voices.json")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def get_api_key() -> str:
    """Return the Mistral API key from the environment or a local .env file."""
    load_dotenv()
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise ConfigError(
            "MISTRAL_API_KEY is not set. "
            "Copy .env.example to .env and add your key, "
            "or export MISTRAL_API_KEY in your shell."
        )
    return key


def get_client() -> Mistral:
    """Return an authenticated Mistral client."""
    return Mistral(api_key=get_api_key())
