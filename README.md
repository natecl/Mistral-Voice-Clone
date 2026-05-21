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
