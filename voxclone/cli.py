"""voxclone command-line interface."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import clipper, config, deps, downloader, registry


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
