"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import clipper, config, deps, downloader, registry, synth, voices
from mistralai.client.errors import MistralError, NoResponseError


def _cmd_voices(args: argparse.Namespace) -> int:
    saved = registry.load_registry()
    if not saved:
        print("No saved voices yet. Run 'voxclone clone' to create one.")
        return 0
    print("Saved voices:")
    for name, voice_id in sorted(saved.items()):
        print(f"  {name}\t{voice_id}")
    return 0


def _prepare_reference(url: str, start: str, end: str, out_path: Path) -> Path:
    """Download `url`, extract [start, end] into a clean reference clip.

    Callers are responsible for running deps.check_dependencies() first.
    """
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Downloading audio from {url} ...")
        audio = downloader.download_audio(url, Path(tmp))
        print(f"Extracting clip {start}-{end} ...")
        clipper.extract_clip(audio, start, end, out_path)
    return out_path


def _cmd_prepare(args: argparse.Namespace) -> int:
    deps.check_dependencies()
    out = Path(args.out)
    _prepare_reference(args.url, args.start, args.end, out)
    print(f"Reference clip saved to {out}")
    return 0


def _confirm_consent(args: argparse.Namespace) -> bool:
    """Return True if consent is confirmed via --i-have-consent or an
    interactive [y/N] prompt; False if the prompt is declined."""
    if args.i_have_consent:
        return True
    print(
        "Voice cloning requires the right to clone this voice — "
        "your own voice, or the speaker's explicit consent."
    )
    answer = input("Do you have that right? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _cmd_clone(args: argparse.Namespace) -> int:
    deps.check_dependencies()
    if not _confirm_consent(args):
        print("Aborted: consent not confirmed.", file=sys.stderr)
        return 1
    client = config.get_client()
    # `tmp` keeps the reference clip alive while voices.create_voice reads it.
    with tempfile.TemporaryDirectory() as tmp:
        clip = Path(tmp) / "reference.wav"
        _prepare_reference(args.url, args.start, args.end, clip)
        print("Creating Voxtral voice ...")
        voice_id = voices.create_voice(client, args.name, clip, args.languages)
    registry.save_voice(args.name, voice_id)
    print(f"Voice '{args.name}' created and saved: {voice_id}")
    print("Note: Mistral retains cloned voices for ~30 days by default.")
    return 0


def _cmd_speak(args: argparse.Namespace) -> int:
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        print("Error: provide --text or --text-file", file=sys.stderr)
        return 1
    client = config.get_client()
    voice_id = registry.resolve_voice(args.voice)
    out = Path(args.out) if args.out else Path(f"speech.{args.format}")
    print(f"Generating speech with voice '{args.voice}' "
          f"({len(text)} characters) ...")
    synth.synthesize(client, voice_id, text, out, response_format=args.format)
    print(f"Wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxclone",
        description="Clone a voice from a YouTube video with Mistral Voxtral TTS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_voices = sub.add_parser("voices", help="List saved voices")
    p_voices.set_defaults(func=_cmd_voices)

    p_prepare = sub.add_parser(
        "prepare", help="Download a YouTube clip and save a reference WAV"
    )
    p_prepare.add_argument("url", help="YouTube video URL")
    p_prepare.add_argument("--start", required=True, help="Clip start (MM:SS)")
    p_prepare.add_argument("--end", required=True, help="Clip end (MM:SS)")
    p_prepare.add_argument("--out", required=True, help="Output WAV path")
    p_prepare.set_defaults(func=_cmd_prepare)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (config.ConfigError, deps.MissingDependencyError,
            RuntimeError, ValueError, OSError,
            MistralError, NoResponseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Aborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
