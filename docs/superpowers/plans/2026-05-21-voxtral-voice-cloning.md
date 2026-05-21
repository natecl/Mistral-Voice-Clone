# Voxtral Voice Cloning from YouTube — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that clones a voice from a YouTube video via Mistral's Voxtral TTS API and generates speech from text in that voice.

**Architecture:** A modular `voxclone/` package — focused single-responsibility modules (`config`, `deps`, `registry`, `downloader`, `clipper`, `voices`, `synth`) wired by a thin `cli.py`. Voice cloning runs against the Mistral cloud API (`voxtral-mini-tts-2603`); self-hosting cannot clone voices because the open weights ship without the audio encoder. Each phase ends with a runnable CLI command and passing tests.

**Tech Stack:** Python 3.10+, `mistralai` SDK, `yt-dlp` (library), `ffmpeg`/`ffprobe` (system tools), `python-dotenv`, `pytest`.

---

## Phases (each a testable vertical slice)

- **Phase 1** — Scaffold, config, dependency checks, voice registry, CLI skeleton. Slice: `voxclone voices` runs and reports an empty registry.
- **Phase 2** — YouTube download + clip extraction + `prepare` command. Slice: `voxclone prepare <url> --start --end --out ref.wav` produces a clean reference clip.
- **Phase 3** — Voice creation API + `clone` command. Slice: `voxclone clone <url> ...` clones a voice end-to-end and saves it.
- **Phase 4** — Speech synthesis API + `speak` command. Slice: `voxclone speak --voice <name> --text "..."` produces speech audio.

## Reference: confirmed Mistral API surface

```python
from mistralai import Mistral
client = Mistral(api_key="...")

# Create a saved voice
voice = client.audio.voices.create(
    name="my-voice",
    sample_audio="<base64-encoded audio bytes>",
    sample_filename="reference.wav",
    languages=["en"],
)
voice.id  # -> the voice_id string

# Generate speech with a saved voice
response = client.audio.speech.complete(
    model="voxtral-mini-tts-2603",
    input="Text to speak",
    voice_id="<voice_id>",
    response_format="mp3",   # mp3 | wav | pcm | flac | opus
)
# response.audio_data is base64-encoded audio bytes
```

---

# Phase 1 — Scaffold, Config, Registry, CLI Skeleton

## Task 1.1: Project scaffold and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `voxclone/__init__.py`
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "voxclone"
version = "0.1.0"
description = "Clone a voice from a YouTube video with Mistral Voxtral TTS"
requires-python = ">=3.10"
dependencies = [
    "mistralai>=1.0",
    "yt-dlp>=2024.1.1",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
voxclone = "voxclone.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["voxclone*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `voxclone/__init__.py`**

```python
"""voxclone — clone a voice from YouTube with Mistral Voxtral TTS."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.env
.voxclone/
*.egg-info/
build/
dist/
.pytest_cache/
# generated audio output
*.mp3
*.wav
*.flac
*.opus
# but keep example/fixture assets if added later
!docs/**
```

- [ ] **Step 4: Create `.env.example`**

```dotenv
# Get your key at https://console.mistral.ai/
MISTRAL_API_KEY=
```

- [ ] **Step 5: Install the package in editable mode with dev extras**

Run: `pip install -e ".[dev]"`
Expected: installs `mistralai`, `yt-dlp`, `python-dotenv`, `pytest`; ends with "Successfully installed ... voxclone-0.1.0".

- [ ] **Step 6: Verify ffmpeg is available (system dependency)**

Run: `ffmpeg -version && ffprobe -version`
Expected: both print version banners. If not, install ffmpeg (macOS: `brew install ffmpeg`) before continuing — the test suite needs it.

- [ ] **Step 7: Verify the package imports**

Run: `python -c "import voxclone; print(voxclone.__version__)"`
Expected: prints `0.1.0`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml voxclone/__init__.py .gitignore .env.example
git commit -m "chore: scaffold voxclone package"
```

---

## Task 1.2: Configuration module

**Files:**
- Create: `voxclone/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest

from voxclone import config


def test_get_api_key_returns_env_value(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-123")
    assert config.get_api_key() == "test-key-123"


def test_get_api_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env file here
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(config.ConfigError, match="MISTRAL_API_KEY"):
        config.get_api_key()


def test_constants_have_expected_values():
    assert config.MODEL == "voxtral-mini-tts-2603"
    assert config.SAMPLE_RATE == 24000
    assert config.MIN_CLIP_SECONDS == 3.0
    assert config.MAX_CLIP_SECONDS == 10.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError` (`voxclone.config` does not exist).

- [ ] **Step 3: Write `voxclone/config.py`**

```python
"""Configuration: API key loading, Mistral client factory, constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from mistralai import Mistral

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/config.py tests/test_config.py
git commit -m "feat: add config module for API key and constants"
```

---

## Task 1.3: External dependency checks

**Files:**
- Create: `voxclone/deps.py`
- Test: `tests/test_deps.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_deps.py
import pytest

from voxclone import deps


def test_check_dependencies_passes_when_tools_present(monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    deps.check_dependencies()  # should not raise


def test_check_dependencies_raises_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda tool: None)
    with pytest.raises(deps.MissingDependencyError, match="ffmpeg"):
        deps.check_dependencies()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_deps.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.deps'`.

- [ ] **Step 3: Write `voxclone/deps.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_deps.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/deps.py tests/test_deps.py
git commit -m "feat: add external dependency checks"
```

---

## Task 1.4: Voice registry (name → voice_id store)

**Files:**
- Create: `voxclone/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registry.py
from voxclone import registry


def test_load_registry_missing_file_returns_empty(tmp_path):
    assert registry.load_registry(tmp_path / "nope.json") == {}


def test_save_and_load_voice(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.load_registry(path) == {"alice": "voice-1"}


def test_save_voice_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "voices.json"
    registry.save_voice("bob", "voice-2", path)
    assert path.exists()


def test_resolve_voice_returns_id_for_known_name(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.resolve_voice("alice", path) == "voice-1"


def test_resolve_voice_passes_through_unknown_value(tmp_path):
    path = tmp_path / "voices.json"
    assert registry.resolve_voice("raw-voice-id", path) == "raw-voice-id"


def test_remove_voice(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.remove_voice("alice", path) is True
    assert registry.load_registry(path) == {}
    assert registry.remove_voice("alice", path) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.registry'`.

- [ ] **Step 3: Write `voxclone/registry.py`**

```python
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
    return json.loads(path.read_text())


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_registry.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/registry.py tests/test_registry.py
git commit -m "feat: add local voice registry"
```

---

## Task 1.5: CLI skeleton with `voices` subcommand

**Files:**
- Create: `voxclone/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
import pytest

from voxclone import cli, registry


def test_voices_command_reports_empty_registry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["voices"])
    assert rc == 0
    assert "No saved voices" in capsys.readouterr().out


def test_voices_command_lists_saved_voices(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("alice", "voice-1")
    rc = cli.main(["voices"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "voice-1" in out


def test_no_subcommand_exits_with_error(monkeypatch):
    with pytest.raises(SystemExit):
        cli.main([])
```

Note: `registry.save_voice("alice", ...)` writes to the default relative path
`.voxclone/voices.json`; `monkeypatch.chdir(tmp_path)` keeps it inside the temp
directory, so tests never touch a real registry.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.cli'`.

- [ ] **Step 3: Write `voxclone/cli.py`**

```python
"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys

from . import config, deps, registry


def _cmd_voices(args: argparse.Namespace) -> int:
    saved = registry.load_registry()
    if not saved:
        print("No saved voices yet. Run 'voxclone clone' to create one.")
        return 0
    print("Saved voices:")
    for name, voice_id in sorted(saved.items()):
        print(f"  {name}\t{voice_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxclone",
        description="Clone a voice from a YouTube video with Mistral Voxtral TTS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_voices = sub.add_parser("voices", help="List saved voices")
    p_voices.set_defaults(func=_cmd_voices)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (config.ConfigError, deps.MissingDependencyError,
            RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 3 passed.

- [ ] **Step 5: Verify the slice end-to-end**

Run: `voxclone voices`
Expected: prints `No saved voices yet. Run 'voxclone clone' to create one.`
Run: `voxclone --help`
Expected: prints usage with the `voices` subcommand listed.

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: all tests pass (config, deps, registry, cli).

- [ ] **Step 7: Commit**

```bash
git add voxclone/cli.py tests/test_cli.py
git commit -m "feat: add CLI skeleton with voices subcommand"
```

---

# Phase 2 — Download, Clip Extraction, `prepare` Command

## Task 2.1: Timestamp parsing

**Files:**
- Create: `voxclone/clipper.py`
- Test: `tests/test_clipper.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clipper.py
import subprocess

import pytest

from voxclone import clipper


def test_parse_timestamp_plain_seconds():
    assert clipper.parse_timestamp("45") == 45.0


def test_parse_timestamp_mm_ss():
    assert clipper.parse_timestamp("1:30") == 90.0


def test_parse_timestamp_hh_mm_ss():
    assert clipper.parse_timestamp("1:00:05") == 3605.0


def test_parse_timestamp_invalid_raises():
    with pytest.raises(ValueError):
        clipper.parse_timestamp("ab:cd")


def test_parse_timestamp_too_many_parts_raises():
    with pytest.raises(ValueError):
        clipper.parse_timestamp("1:2:3:4")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_clipper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.clipper'`.

- [ ] **Step 3: Write `voxclone/clipper.py` (timestamp parsing only)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_clipper.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/clipper.py tests/test_clipper.py
git commit -m "feat: add timestamp parsing for clip extraction"
```

---

## Task 2.2: Clip extraction with ffmpeg

**Files:**
- Modify: `voxclone/clipper.py` (add `extract_clip`)
- Test: `tests/test_clipper.py` (add extraction tests)

- [ ] **Step 1: Write the failing tests (append to `tests/test_clipper.py`)**

```python
def _probe(path, entry):
    """Return a single ffprobe value for the given stream/format entry."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entry,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


@pytest.fixture
def sine_audio(tmp_path):
    """A 20-second 440 Hz stereo test tone created with ffmpeg."""
    src = tmp_path / "sine.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=20:sample_rate=44100",
         "-ac", "2", str(src)],
        capture_output=True, check=True,
    )
    return src


def test_extract_clip_has_correct_duration(sine_audio, tmp_path):
    out = tmp_path / "clip.wav"
    clipper.extract_clip(sine_audio, "0:02", "0:09", out)
    assert out.exists()
    duration = float(_probe(out, "format=duration"))
    assert 6.5 < duration < 7.5  # ~7s clip


def test_extract_clip_is_mono_24khz(sine_audio, tmp_path):
    out = tmp_path / "clip.wav"
    clipper.extract_clip(sine_audio, "0:00", "0:05", out)
    assert _probe(out, "stream=channels") == "1"
    assert _probe(out, "stream=sample_rate") == "24000"


def test_extract_clip_rejects_non_positive_duration(sine_audio, tmp_path):
    with pytest.raises(ValueError, match="after start"):
        clipper.extract_clip(sine_audio, "0:09", "0:02", tmp_path / "x.wav")


def test_extract_clip_warns_when_too_short(sine_audio, tmp_path, capsys):
    clipper.extract_clip(sine_audio, "0:00", "0:01", tmp_path / "short.wav")
    assert "best with" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_clipper.py -v`
Expected: FAIL — `AttributeError: module 'voxclone.clipper' has no attribute 'extract_clip'`.

- [ ] **Step 3: Add `extract_clip` to `voxclone/clipper.py`**

Append this function to `voxclone/clipper.py`:

```python
def extract_clip(src, start, end, out_path):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_clipper.py -v`
Expected: 9 passed (5 timestamp + 4 extraction).

- [ ] **Step 5: Commit**

```bash
git add voxclone/clipper.py tests/test_clipper.py
git commit -m "feat: add ffmpeg clip extraction with normalization"
```

---

## Task 2.3: YouTube audio download

**Files:**
- Create: `voxclone/downloader.py`
- Test: `tests/test_downloader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_downloader.py
import pytest

from voxclone import downloader


def test_download_audio_returns_extracted_wav_path(tmp_path, monkeypatch):
    fake_id = "abc123"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            # Simulate yt-dlp writing the post-processed wav file.
            (tmp_path / f"{fake_id}.wav").write_bytes(b"RIFFfakeaudio")
            return {"id": fake_id}

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    result = downloader.download_audio("https://youtu.be/x", tmp_path)
    assert result == tmp_path / f"{fake_id}.wav"
    assert result.read_bytes() == b"RIFFfakeaudio"


def test_download_audio_raises_when_file_missing(tmp_path, monkeypatch):
    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            return {"id": "missing"}  # never writes a file

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(RuntimeError, match="did not produce"):
        downloader.download_audio("https://youtu.be/x", tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_downloader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.downloader'`.

- [ ] **Step 3: Write `voxclone/downloader.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_downloader.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/downloader.py tests/test_downloader.py
git commit -m "feat: add YouTube audio downloader"
```

---

## Task 2.4: `prepare` command (download + clip, no API)

**Files:**
- Modify: `voxclone/cli.py` (add `_prepare_reference`, `_cmd_prepare`, parser entry)
- Test: `tests/test_cli.py` (add `prepare` tests)

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
from pathlib import Path


def test_prepare_command_writes_reference_clip(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.deps, "check_dependencies", lambda: None)

    def fake_download(url, out_dir):
        path = Path(out_dir) / "audio.wav"
        path.write_bytes(b"RIFFaudio")
        return path

    def fake_extract(src, start, end, out_path):
        Path(out_path).write_bytes(b"RIFFclip")
        return Path(out_path)

    monkeypatch.setattr(cli.downloader, "download_audio", fake_download)
    monkeypatch.setattr(cli.clipper, "extract_clip", fake_extract)

    rc = cli.main(["prepare", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08",
                   "--out", "reference.wav"])
    assert rc == 0
    assert Path("reference.wav").read_bytes() == b"RIFFclip"
    assert "reference.wav" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_prepare_command_writes_reference_clip -v`
Expected: FAIL — `argparse` error: invalid choice `'prepare'`.

- [ ] **Step 3: Update `voxclone/cli.py`**

Add `clipper`, `downloader`, `tempfile`, and `Path` imports — replace the
import block at the top with:

```python
"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import clipper, config, deps, downloader, registry
```

Add these two functions above `build_parser`:

```python
def _prepare_reference(url: str, start: str, end: str, out_path: Path) -> Path:
    """Download `url`, extract [start, end] into a clean reference clip."""
    deps.check_dependencies()
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Downloading audio from {url} ...")
        audio = downloader.download_audio(url, Path(tmp))
        print(f"Extracting clip {start}-{end} ...")
        clipper.extract_clip(audio, start, end, out_path)
    return out_path


def _cmd_prepare(args: argparse.Namespace) -> int:
    out = Path(args.out)
    _prepare_reference(args.url, args.start, args.end, out)
    print(f"Reference clip saved to {out}")
    return 0
```

In `build_parser`, add the `prepare` subparser before `return parser`:

```python
    p_prepare = sub.add_parser(
        "prepare", help="Download a YouTube clip and save a reference WAV"
    )
    p_prepare.add_argument("url", help="YouTube video URL")
    p_prepare.add_argument("--start", required=True, help="Clip start (MM:SS)")
    p_prepare.add_argument("--end", required=True, help="Clip end (MM:SS)")
    p_prepare.add_argument("--out", required=True, help="Output WAV path")
    p_prepare.set_defaults(func=_cmd_prepare)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all CLI tests pass (4 total: 2 voices, 1 no-subcommand, 1 prepare).

- [ ] **Step 5: Verify the slice with a real video (optional, needs network)**

Run: `voxclone prepare "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --start 0:30 --end 0:40 --out reference.wav`
Expected: downloads, extracts, prints `Reference clip saved to reference.wav`; `reference.wav` is a ~10 s mono 24 kHz file. (Use a video you have rights to.)

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add voxclone/cli.py tests/test_cli.py
git commit -m "feat: add prepare command for reference clip extraction"
```

---

# Phase 3 — Voice Creation API, `clone` Command

## Task 3.1: Voice creation against the Mistral API

**Files:**
- Create: `voxclone/voices.py`
- Test: `tests/test_voices.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_voices.py
import base64
from types import SimpleNamespace

from voxclone import voices


def _fake_client(capture):
    """A stand-in Mistral client whose audio.voices.create records kwargs."""

    class FakeVoices:
        def create(self, **kwargs):
            capture.update(kwargs)
            return SimpleNamespace(id="voice-xyz", name=kwargs["name"])

    return SimpleNamespace(audio=SimpleNamespace(voices=FakeVoices()))


def test_create_voice_returns_voice_id(tmp_path):
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"RIFFaudiodata")
    capture = {}
    client = _fake_client(capture)

    voice_id = voices.create_voice(client, "my-voice", clip, ["en"])

    assert voice_id == "voice-xyz"


def test_create_voice_sends_base64_audio_and_metadata(tmp_path):
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"RIFFaudiodata")
    capture = {}
    client = _fake_client(capture)

    voices.create_voice(client, "my-voice", clip, ["en", "fr"])

    assert capture["name"] == "my-voice"
    assert capture["sample_filename"] == "ref.wav"
    assert capture["languages"] == ["en", "fr"]
    assert base64.b64decode(capture["sample_audio"]) == b"RIFFaudiodata"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voices.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.voices'`.

- [ ] **Step 3: Write `voxclone/voices.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_voices.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/voices.py tests/test_voices.py
git commit -m "feat: add Voxtral voice creation"
```

---

## Task 3.2: `clone` command with consent guard

**Files:**
- Modify: `voxclone/cli.py` (add `voices` import, `_confirm_consent`, `_cmd_clone`, parser entry)
- Test: `tests/test_cli.py` (add `clone` tests)

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
def test_clone_command_creates_and_saves_voice(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.deps, "check_dependencies", lambda: None)
    monkeypatch.setattr(cli.config, "get_client", lambda: object())

    def fake_download(url, out_dir):
        path = Path(out_dir) / "audio.wav"
        path.write_bytes(b"RIFFaudio")
        return path

    def fake_extract(src, start, end, out):
        Path(out).write_bytes(b"clip")
        return Path(out)

    monkeypatch.setattr(cli.downloader, "download_audio", fake_download)
    monkeypatch.setattr(cli.clipper, "extract_clip", fake_extract)
    monkeypatch.setattr(
        cli.voices, "create_voice",
        lambda client, name, clip, langs: "voice-123",
    )

    rc = cli.main(["clone", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08",
                   "--name", "bob", "--i-have-consent"])
    assert rc == 0
    assert registry.resolve_voice("bob") == "voice-123"
    assert "voice-123" in capsys.readouterr().out


def test_clone_command_aborts_without_consent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")

    rc = cli.main(["clone", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08", "--name", "bob"])
    assert rc == 1
    assert "Aborted" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k clone -v`
Expected: FAIL — `argparse` error: invalid choice `'clone'`.

- [ ] **Step 3: Update `voxclone/cli.py`**

Replace the import block with (adds `voices`):

```python
"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import clipper, config, deps, downloader, registry, voices
```

Add these functions above `build_parser`:

```python
def _confirm_consent(args: argparse.Namespace) -> bool:
    """Confirm the user has the right to clone this voice."""
    if args.i_have_consent:
        return True
    print(
        "Voice cloning requires the right to clone this voice — "
        "your own voice, or the speaker's explicit consent."
    )
    answer = input("Do you have that right? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _cmd_clone(args: argparse.Namespace) -> int:
    if not _confirm_consent(args):
        print("Aborted: consent not confirmed.")
        return 1
    client = config.get_client()
    with tempfile.TemporaryDirectory() as tmp:
        clip = Path(tmp) / "reference.wav"
        _prepare_reference(args.url, args.start, args.end, clip)
        print("Creating Voxtral voice ...")
        voice_id = voices.create_voice(client, args.name, clip, args.languages)
    registry.save_voice(args.name, voice_id)
    print(f"Voice '{args.name}' created and saved: {voice_id}")
    return 0
```

In `build_parser`, add the `clone` subparser before `return parser`:

```python
    p_clone = sub.add_parser(
        "clone", help="Clone a voice from a YouTube video"
    )
    p_clone.add_argument("url", help="YouTube video URL")
    p_clone.add_argument("--start", required=True, help="Clip start (MM:SS)")
    p_clone.add_argument("--end", required=True, help="Clip end (MM:SS)")
    p_clone.add_argument("--name", required=True,
                         help="Name to save the cloned voice under")
    p_clone.add_argument("--languages", nargs="+", default=["en"],
                         help="Language codes for the voice (default: en)")
    p_clone.add_argument("--i-have-consent", action="store_true",
                         help="Confirm you have the right to clone this voice")
    p_clone.set_defaults(func=_cmd_clone)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all CLI tests pass (6 total).

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Verify the slice with a real video (optional, needs network + API key)**

Run: `voxclone clone "https://www.youtube.com/watch?v=<id>" --start 0:30 --end 0:40 --name testvoice --i-have-consent`
Then: `voxclone voices`
Expected: `clone` prints a created voice id; `voices` lists `testvoice`.

- [ ] **Step 7: Commit**

```bash
git add voxclone/cli.py tests/test_cli.py
git commit -m "feat: add clone command with consent guard"
```

---

# Phase 4 — Speech Synthesis, `speak` Command

## Task 4.1: Speech synthesis with retry

**Files:**
- Create: `voxclone/synth.py`
- Test: `tests/test_synth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synth.py
import base64
from types import SimpleNamespace

import pytest

from voxclone import synth


def _fake_client(capture, audio_bytes, fail_times=0, status_code=429):
    """Fake Mistral client; first `fail_times` calls raise a status error."""
    state = {"calls": 0}

    class ApiError(Exception):
        def __init__(self):
            self.status_code = status_code

    class FakeSpeech:
        def complete(self, **kwargs):
            state["calls"] += 1
            if state["calls"] <= fail_times:
                raise ApiError()
            capture.update(kwargs)
            capture["calls"] = state["calls"]
            return SimpleNamespace(
                audio_data=base64.b64encode(audio_bytes).decode()
            )

    return SimpleNamespace(audio=SimpleNamespace(speech=FakeSpeech()))


def test_synthesize_writes_decoded_audio(tmp_path):
    capture = {}
    client = _fake_client(capture, b"\x00\x01fake-mp3")
    out = tmp_path / "out.mp3"

    synth.synthesize(client, "voice-xyz", "Hello world", out)

    assert out.read_bytes() == b"\x00\x01fake-mp3"
    assert capture["model"] == "voxtral-mini-tts-2603"
    assert capture["voice_id"] == "voice-xyz"
    assert capture["input"] == "Hello world"
    assert capture["response_format"] == "mp3"


def test_synthesize_retries_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(synth.time, "sleep", lambda s: None)
    capture = {}
    client = _fake_client(capture, b"ok", fail_times=1, status_code=429)
    out = tmp_path / "out.mp3"

    synth.synthesize(client, "v", "hi", out)

    assert capture["calls"] == 2
    assert out.read_bytes() == b"ok"


def test_synthesize_gives_up_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(synth.time, "sleep", lambda s: None)
    client = _fake_client({}, b"never", fail_times=99, status_code=503)
    out = tmp_path / "out.mp3"

    with pytest.raises(Exception):
        synth.synthesize(client, "v", "hi", out, max_retries=2)
    assert not out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voxclone.synth'`.

- [ ] **Step 3: Write `voxclone/synth.py`**

```python
"""Mistral Voxtral speech generation."""
from __future__ import annotations

import base64
import time
from pathlib import Path

from .config import MODEL

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def synthesize(client, voice_id: str, text: str, out_path,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synth.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add voxclone/synth.py tests/test_synth.py
git commit -m "feat: add speech synthesis with retry"
```

---

## Task 4.2: `speak` command

**Files:**
- Modify: `voxclone/cli.py` (add `synth` import, `_cmd_speak`, parser entry)
- Test: `tests/test_cli.py` (add `speak` tests)

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
def test_speak_command_writes_output_for_saved_voice(tmp_path, monkeypatch,
                                                     capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    capture = {}

    def fake_synth(client, voice_id, text, out, response_format="mp3"):
        capture.update(voice_id=voice_id, text=text, fmt=response_format)
        Path(out).write_bytes(b"audio-bytes")
        return Path(out)

    monkeypatch.setattr(cli.synth, "synthesize", fake_synth)

    rc = cli.main(["speak", "--voice", "bob", "--text", "Hello there",
                   "--out", "result.mp3"])
    assert rc == 0
    assert capture["voice_id"] == "voice-123"  # name resolved to id
    assert capture["text"] == "Hello there"
    assert Path("result.mp3").read_bytes() == b"audio-bytes"


def test_speak_command_reads_text_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    (tmp_path / "script.txt").write_text("from a file")
    capture = {}

    def fake_synth(client, voice_id, text, out, response_format="mp3"):
        capture["text"] = text
        Path(out).write_bytes(b"x")
        return Path(out)

    monkeypatch.setattr(cli.synth, "synthesize", fake_synth)

    rc = cli.main(["speak", "--voice", "bob", "--text-file", "script.txt",
                   "--out", "out.mp3"])
    assert rc == 0
    assert capture["text"] == "from a file"


def test_speak_command_requires_text(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    rc = cli.main(["speak", "--voice", "bob"])
    assert rc == 1
    assert "text" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k speak -v`
Expected: FAIL — `argparse` error: invalid choice `'speak'`.

- [ ] **Step 3: Update `voxclone/cli.py`**

Replace the import block with (adds `synth`):

```python
"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import clipper, config, deps, downloader, registry, synth, voices
```

Add this function above `build_parser`:

```python
def _cmd_speak(args: argparse.Namespace) -> int:
    if args.text_file:
        text = Path(args.text_file).read_text()
    elif args.text:
        text = args.text
    else:
        print("Error: provide --text or --text-file", file=sys.stderr)
        return 1
    client = config.get_client()
    voice_id = registry.resolve_voice(args.voice)
    out = Path(args.out) if args.out else Path(f"speech.{args.format}")
    print(f"Generating speech with voice '{args.voice}' ...")
    synth.synthesize(client, voice_id, text, out, response_format=args.format)
    print(f"Wrote {out}")
    return 0
```

In `build_parser`, add the `speak` subparser before `return parser`:

```python
    p_speak = sub.add_parser(
        "speak", help="Generate speech with a saved voice"
    )
    p_speak.add_argument("--voice", required=True,
                         help="Saved voice name (or raw voice id)")
    p_speak.add_argument("--text", help="Text to speak")
    p_speak.add_argument("--text-file", help="Path to a file with text to speak")
    p_speak.add_argument("--format", default="mp3",
                         choices=["mp3", "wav", "pcm", "flac", "opus"],
                         help="Output audio format (default: mp3)")
    p_speak.add_argument("--out", help="Output path (default: speech.<format>)")
    p_speak.set_defaults(func=_cmd_speak)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all CLI tests pass (9 total).

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass across every module.

- [ ] **Step 6: Verify the slice (optional, needs API key + a saved voice)**

Run: `voxclone speak --voice testvoice --text "This is my cloned voice." --out hello.mp3`
Expected: prints `Wrote hello.mp3`; `hello.mp3` plays back the text in the cloned voice.

- [ ] **Step 7: Commit**

```bash
git add voxclone/cli.py tests/test_cli.py
git commit -m "feat: add speak command for speech generation"
```

---

## Task 4.3: README and documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md`**

```markdown
# Mistral Voice Clone

Clone a voice from a YouTube video with Mistral's Voxtral TTS API, then
generate speech in that voice from any text.

> Voice cloning runs against the **Mistral cloud API**. The open-weight
> Voxtral release ships without the audio encoder, so self-hosting can only
> use Mistral's ~20 preset voices — it cannot clone an arbitrary voice.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` on your PATH (macOS: `brew install ffmpeg`)
- A Mistral API key — https://console.mistral.ai/

## Install

```bash
pip install -e ".[dev]"
cp .env.example .env   # then add your MISTRAL_API_KEY
```

## Usage

Preview a reference clip before cloning:

```bash
voxclone prepare "<youtube-url>" --start 0:30 --end 0:40 --out reference.wav
```

Clone a voice (you must have the right to clone it):

```bash
voxclone clone "<youtube-url>" --start 0:30 --end 0:40 \
    --name my-voice --i-have-consent
```

Generate speech with a saved voice:

```bash
voxclone speak --voice my-voice --text "Hello from a cloned voice." \
    --out hello.mp3
```

List saved voices:

```bash
voxclone voices
```

## Consent

Only clone voices you have the right to use — your own voice, or a speaker
who has given explicit consent. The `clone` command requires confirmation.

## Development

```bash
pytest -v
```
```

- [ ] **Step 2: Verify the full suite still passes**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add usage documentation"
```

---

## Done

After Phase 4, the CLI supports `prepare`, `clone`, `speak`, and `voices`,
with every module unit-tested. Final verification:

- [ ] Run `pytest -v` — all tests pass.
- [ ] Run `voxclone --help` — all four subcommands listed.
- [ ] Optional live check: `clone` a short clip from a video you own, then
      `speak` with the resulting voice and listen to the output.
