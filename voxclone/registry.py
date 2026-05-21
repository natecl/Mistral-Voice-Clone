"""Local name -> voice_id store backed by a JSON file."""
from __future__ import annotations

import json
from pathlib import Path

from .config import REGISTRY_PATH


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, str]:
    """Return the name -> voice_id mapping, or {} if no registry file exists."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Registry file is corrupt ({path}): {exc}. "
            "Delete it or restore it manually."
        ) from exc


def _write(registry: dict[str, str], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=True))


def save_voice(name: str, voice_id: str, path: Path = REGISTRY_PATH) -> None:
    """Add or update a name -> voice_id entry."""
    registry = load_registry(path)
    registry[name] = voice_id
    _write(registry, path)


def resolve_voice(name_or_id: str, path: Path = REGISTRY_PATH) -> str:
    """Return the voice_id for a registered name, or the input unchanged."""
    return load_registry(path).get(name_or_id, name_or_id)


def remove_voice(name: str, path: Path = REGISTRY_PATH) -> bool:
    """Delete a registry entry. Return True if it existed, False otherwise."""
    registry = load_registry(path)
    if name not in registry:
        return False
    del registry[name]
    _write(registry, path)
    return True
