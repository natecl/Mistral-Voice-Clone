# Design: `--clip <path>` for `voxclone clone`

**Date:** 2026-05-22
**Status:** Approved

## Problem

`voxclone clone` can only clone a voice from a YouTube URL: it requires a
positional `url` plus `--start`/`--end`, then downloads and trims the audio.
There is no way to clone a voice from an audio file the user already has on
disk (e.g. a `reference.wav` produced elsewhere). The underlying
`voices.create_voice()` already accepts a local clip path — only the CLI lacks
a way to reach it.

## Goal

Add a `--clip <path>` option to the `clone` command that clones a voice
directly from a local audio file, skipping the download/extract pipeline.

## Approach

Three options were considered:

- **A. `--clip` flag on the existing `clone` command** *(chosen)* — one
  command, one mental model ("clone a voice"). The user explicitly asked for a
  `--clip` *option*, which implies a flag.
- B. A separate `clone-clip` subcommand — cleaner per-command args, but adds a
  second clone command to the help/README surface.
- C. Auto-detect URL vs. local path on the positional `url` arg — implicit and
  magical; rejected.

## CLI changes — `voxclone/cli.py`

On the `clone` subparser:

- The positional `url` becomes optional (`nargs="?"`).
- `--start` and `--end` lose `required=True`.
- A new `--clip PATH` argument is added.

`_cmd_clone` validates the input mode before doing any work, mirroring how
`_cmd_speak` validates `--text` / `--text-file`:

- Exactly one input mode must be supplied: `--clip`, **or** the trio
  (`url` + `--start` + `--end`). Supplying both, or neither, prints an error to
  stderr and returns exit code 1.
- When `--clip` is supplied but the file does not exist, print an error to
  stderr and return exit code 1.

When `--clip` is used:

- Skip the download/extract/temp-directory path entirely.
- Probe the clip's duration and warn if it is outside Voxtral's usual range.
- Pass the file path directly to `voices.create_voice`.

The YouTube path (positional `url` + `--start`/`--end`) is unchanged.

## Shared duration logic — `voxclone/clipper.py`

- New `probe_duration(src) -> float`: runs
  `ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 <src>`
  and parses the result into seconds. Raises `RuntimeError` if ffprobe fails.
- The length-warning currently inline in `extract_clip` is extracted into
  `warn_if_unusual_length(duration) -> None`. Both `extract_clip` and the new
  `--clip` path call it, so both print the identical `3-10s` warning. The
  YouTube path's behavior is unchanged (the warning text and threshold —
  warn below `MIN_CLIP_SECONDS` or above `CLIP_WARN_CEILING` — are preserved).

## Dependencies

`_cmd_clone` already calls `deps.check_dependencies()` at the top, which checks
for both `ffmpeg` and `ffprobe`. `probe_duration` needs `ffprobe`, so the
`--clip` path is already covered — no change to dependency checks.

## Error handling

- Missing `--clip` file → stderr message, exit 1.
- Both/neither input mode → stderr message, exit 1.
- `ffprobe` failure during `probe_duration` → `RuntimeError`, caught by the
  existing top-level handler in `main`, which prints `Error: ...` and exits 1.
- Mistral API errors → already caught by the existing `main` handler.

## Testing (TDD — tests written first)

`tests/test_cli.py`:

- Clone from a local clip succeeds and saves the voice to the registry.
- Missing `--clip` file → exit 1 with an error.
- `--clip` combined with a `url` → exit 1 with an error.
- Neither input mode supplied → exit 1 with an error.
- A short clip (probe returns a below-range duration) prints a warning.
- The existing YouTube-path clone test continues to pass.

`tests/test_clipper.py`:

- `probe_duration` returns the correct length for a generated WAV file.
- `warn_if_unusual_length` warns below `MIN_CLIP_SECONDS` and above
  `CLIP_WARN_CEILING`, and stays silent for an in-range duration.

## Documentation

Add a short `--clip` note to the README Usage section.

## Out of scope (YAGNI)

- No re-encoding, resampling, or loudness-normalizing of the local file — it is
  sent to the API as-is.
- No `--clip` support on the `prepare` command (`prepare` is about downloading).
