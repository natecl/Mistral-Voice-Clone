# Voxtral Voice Cloning from YouTube — Design Spec

**Date:** 2026-05-21
**Status:** Approved

## Goal

A reusable Python CLI that clones a voice from a YouTube video using Mistral's
Voxtral TTS API, then generates speech in that voice from arbitrary text.

## Background

Voxtral TTS (`voxtral-mini-tts-2603`) supports zero-shot voice cloning, but
**only through the Mistral cloud API**. The open-weights release
(`mistralai/Voxtral-4B-TTS-2603`) ships without the audio autoencoder's encoder
weights, so self-hosted cloning is impossible — local use is limited to the ~20
preset voices. Therefore this project targets the **cloud API exclusively**.

Cloning requires a short reference clip (Mistral recommends 3–10 s of clean
speech). The API exposes a "saved voice" flow: upload reference audio once,
receive a reusable `voice_id`.

## Scope

In scope:
- Download audio from a YouTube URL.
- Trim a user-specified time range into a clean reference clip.
- Register a saved Voxtral voice and persist its `voice_id` locally.
- Generate speech audio from text using a saved voice.

Out of scope:
- Local / self-hosted inference (cloning unsupported there).
- Automatic or interactive clip selection (manual timestamps only).
- A GUI or web interface.

## Architecture

Modular Python package with a thin CLI orchestration layer.

```
Mistral-Voice-Clone/
├── pyproject.toml          # deps: mistralai, yt-dlp, python-dotenv
├── .env.example            # MISTRAL_API_KEY=
├── README.md               # setup + usage
├── voxclone/
│   ├── __init__.py
│   ├── config.py           # API key loading, Mistral client factory, constants
│   ├── downloader.py       # YouTube URL → raw audio file (yt-dlp)
│   ├── clipper.py          # trim + normalize → clean reference WAV (ffmpeg)
│   ├── voices.py           # create/list/delete voices; name→id registry
│   ├── synth.py            # text + voice_id → speech audio file
│   └── cli.py              # argparse subcommands
└── tests/
    ├── test_clipper.py
    ├── test_voices.py
    ├── test_synth.py
    └── fixtures/           # short fixture audio for clipper tests
```

`ffmpeg` is a system dependency (not pip-installable). `yt-dlp` is a pip
dependency but also requires `ffmpeg` for audio extraction.

## Module responsibilities

### `config.py`
- Loads `MISTRAL_API_KEY` from environment or a `.env` file.
- Exposes a factory that returns an authenticated `Mistral` client.
- Holds constants: `MODEL = "voxtral-mini-tts-2603"`, target sample rate
  `24000`, recommended clip bounds (3–10 s), and the registry path
  (`.voxclone/voices.json`, project-local).
- Raises a clear error if the key is missing, pointing to `.env.example`.

### `downloader.py`
- `download_audio(url, out_dir) -> Path`: invokes `yt-dlp` to fetch best audio
  and returns the path to the downloaded file.
- Surfaces `yt-dlp` failures (age-restricted, region-locked, removed video)
  with the underlying error message.

### `clipper.py`
- `extract_clip(src, start, end, out_path) -> Path`: uses `ffmpeg` to seek to
  `start`, take duration `end - start`, convert to mono 24 kHz WAV, and apply
  loudness normalization.
- Accepts timestamps as `MM:SS` or seconds.
- Warns (does not fail) when the resulting clip falls outside 3–15 s.

### `voices.py`
- `create_voice(client, name, clip_path, languages) -> voice_id`:
  base64-encodes the clip and calls `client.audio.voices.create(name=...,
  sample_audio=<b64>, sample_filename=..., languages=[...])`.
- `list_voices()` / `delete_voice(name)`.
- Maintains a project-local `.voxclone/voices.json` mapping friendly names to
  `voice_id`, so later commands can reference a voice by name.

### `synth.py`
- `synthesize(client, voice_id, text, response_format, out_path) -> Path`:
  calls the Voxtral speech endpoint and writes the audio file.
- Default `response_format` is `mp3`; `wav`, `pcm`, `flac`, `aac`, `opus`
  also accepted.
- The exact `mistralai` SDK method for speech generation is verified against
  the installed SDK version during implementation; if the SDK lacks a speech
  method, fall back to a direct `POST /v1/audio/speech` HTTP call.

### `cli.py`
`argparse` with subcommands:
- `clone <youtube_url> --start 0:30 --end 0:42 --name my-voice [--languages en]
  --i-have-consent` — full pipeline: download → trim → normalize → register →
  store `voice_id`.
- `speak --voice my-voice --text "..." [--text-file f.txt] [--format mp3]
  [--out speech.mp3]` — generate speech.
- `voices` — list saved voices.

## Data flow

```
YouTube URL
  → yt-dlp (bestaudio)            [downloader]
  → ffmpeg trim + mono 24kHz WAV + loudness-normalize   [clipper]
  → base64 encode
  → voices.create() → voice_id    [voices]
  → .voxclone/voices.json (name → voice_id)
  → speech endpoint with text     [synth]
  → output audio file (mp3/wav/...)
```

## Error handling

- Missing `MISTRAL_API_KEY` — clear message referencing `.env.example`.
- Missing `ffmpeg` or `yt-dlp` — detected on startup, with install instructions.
- YouTube download failure — surface `yt-dlp`'s error verbatim.
- Reference clip outside 3–15 s — warn but proceed.
- API errors — friendly messages per status; exponential-backoff retry on
  HTTP 429 and 5xx.

## Consent guard

The `clone` command requires an explicit `--i-have-consent` flag (or an
interactive y/n confirmation when absent) affirming the user has the right to
clone the voice. One concise line — not a lecture.

## Testing strategy

Test-driven, red-to-green, with each phase a testable vertical slice.

- `clipper` — tested against a real short fixture audio file; assert output
  duration, sample rate, and channel count.
- `voices` — mocked Mistral client; assert the request carries correctly
  base64-encoded audio, the right model id, and expected parameters. Registry
  read/write tested against a temp directory.
- `synth` — mocked Mistral client / HTTP layer; assert endpoint, payload, and
  that the response bytes are written to the output path.
- `downloader` — `yt-dlp` invocation mocked; one optional integration test
  gated behind a network/env flag.
- `config` — key-loading and missing-key error paths.

## Open questions

None. Implementation-time verification item: the exact `mistralai` SDK speech
method (see `synth.py` above).
