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
