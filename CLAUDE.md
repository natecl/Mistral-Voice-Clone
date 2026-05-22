# CLAUDE.md

Guidance for a Claude agent working in this repo.

## Project

`voxclone` clones a voice with Mistral's Voxtral TTS cloud API, then generates
speech in that voice from text. Source lives in `voxclone/`; tests in `tests/`.

## How to make a voice clone

A voice can be cloned from a **local audio file** or a **YouTube URL**.

### Prerequisites — check these first

- `MISTRAL_API_KEY` must be set in `.env` (see `.env.example`).
- **Cloning custom voices requires an active paid Mistral plan.** On the free
  tier the API returns `403 — "Custom voices require an active paid plan."`
  If you hit this, stop and tell the user; it is an account/billing issue,
  not a code or input problem.
- `ffmpeg` and `ffprobe` must be on `PATH` (macOS: `brew install ffmpeg`).
- The `voxclone` console script may not be installed on `PATH`. If
  `voxclone ...` fails, run the module instead: `python3 -m voxclone.cli ...`.

### Consent — required before every clone

Only clone a voice the user has the right to clone (their own voice, or a
speaker's explicit consent). Confirm this with the user before running a
clone. The CLI also gates on it: pass `--i-have-consent`, or it prompts.

### Clone from a local audio file

```bash
voxclone clone --clip reference.wav --name my-voice --i-have-consent
```

Best results come from 3-10 s of clean speech; voxclone warns (does not fail)
outside that range. The file is sent to the API as-is — it is not re-encoded.

### Clone from a YouTube URL

```bash
voxclone clone "<youtube-url>" --start 0:30 --end 0:40 \
    --name my-voice --i-have-consent
```

`--clip` and the URL trio (`url` + `--start` + `--end`) are mutually
exclusive — supply exactly one.

Both forms accept `--languages` (default `en`, e.g. `--languages en fr`).
Cloned voices are retained by Mistral for ~30 days. The voice name is saved
to a local registry (`.voxclone/voices.json`).

### Generate speech with a cloned voice

```bash
voxclone speak --voice my-voice --text "Hello from a cloned voice." --out hello.mp3
voxclone voices   # list saved voices
```

## Development

- Run tests with `pytest -v` (or `python3 -m pytest`).
- `tests/test_config.py::test_get_api_key_missing_raises` fails locally when a
  populated `.env` exists, because `get_api_key()` calls `load_dotenv()`. This
  is a known environment artifact, unrelated to feature work.
- This project uses TDD: write a failing test before implementation code.
