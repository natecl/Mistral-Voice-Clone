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

### Clone multiple voices at once (batch)

When the user asks to "run the batch", "clone the batch file", or otherwise
clone several voices from a list, use `voxclone clone-batch <file>`.

The batch file is `.env`-style — one block per voice, numbered:

```
# voices.env
VOICE1_NAME=alice
VOICE1_URL=https://youtu.be/abc
VOICE1_START=0:30
VOICE1_END=0:40

VOICE2_NAME=bob
VOICE2_URL=https://youtu.be/xyz
VOICE2_START=1:00
VOICE2_END=1:10
```

`example_voices.env` in the repo root is a starter template. The default
filename to look for is `voices.env` (project root); if it is not there,
ask the user where the batch file lives — do not guess.

Run it with:

```bash
voxclone clone-batch voices.env --i-have-consent
# or, if the console script isn't on PATH:
python3 -m voxclone.cli clone-batch voices.env --i-have-consent
```

Behavior to be aware of when reporting to the user:

- **Pre-flight collision check**: if any `VOICEn_NAME` already exists in the
  local registry, the command aborts before any download or API call with
  exit 1. Tell the user which names collided and ask whether to rename in
  the batch file or remove them from `.voxclone/voices.json`.
- **Abort on first failure**: a single failure (download error, 403 paid-plan
  error, etc.) aborts the rest of the batch. Voices created before the
  failure stay saved. Report which voices made it and which did not.
- Confirm consent applies to **every** voice in the file before passing
  `--i-have-consent`. Same rule as single-clone — if you aren't sure, ask.
- `--languages` on `clone-batch` applies to every entry in the file
  (default `en`).

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
