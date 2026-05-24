"""Parse a `.env`-style batch file into a list of clone entries.

File format — numbered key=value, one block per voice:

    VOICE1_NAME=alice
    VOICE1_URL=https://youtu.be/abc
    VOICE1_START=0:30
    VOICE1_END=0:40

`<N>` is any positive integer; numbering may be sparse and out of order.
Entries are returned sorted by `<N>`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

_PREFIX_RE = re.compile(r"^VOICE(\d+)_(.+)$")
_REQUIRED = ("NAME", "URL", "START", "END")


@dataclass(frozen=True)
class BatchEntry:
    name: str
    url: str
    start: str
    end: str


def parse_batch_file(path: Path) -> list[BatchEntry]:
    path = Path(path)
    raw = dotenv_values(path)
    # dotenv_values returns dict[str, str | None]; treat None as missing.
    groups: dict[int, dict[str, str]] = {}
    for key, value in raw.items():
        if not key:
            # python-dotenv exposes malformed lines (e.g. "=value") as a
            # blank key — skip rather than emitting a confusing error.
            continue
        match = _PREFIX_RE.match(key)
        if not match:
            raise ValueError(
                f"Unrecognized key in batch file: {key!r}. "
                f"Expected VOICE<N>_NAME / _URL / _START / _END."
            )
        index = int(match.group(1))
        if index < 1:
            raise ValueError(
                f"Invalid voice index in {key!r}: VOICE<N> must be >= 1."
            )
        field = match.group(2)
        if field not in _REQUIRED:
            raise ValueError(
                f"Unknown field {field!r} in {key!r}. "
                f"Allowed fields: {', '.join(_REQUIRED)}."
            )
        if value is None or value == "":
            raise ValueError(f"{key} is empty.")
        groups.setdefault(index, {})[field] = value

    if not groups:
        raise ValueError(f"{path}: no voice entries found.")

    entries: list[BatchEntry] = []
    seen_names: set[str] = set()
    for index in sorted(groups):
        fields = groups[index]
        missing = [f for f in _REQUIRED if f not in fields]
        if missing:
            raise ValueError(
                f"VOICE{index} is missing required keys: "
                f"{', '.join(f'VOICE{index}_{m}' for m in missing)}."
            )
        name = fields["NAME"]
        if name in seen_names:
            raise ValueError(
                f"VOICE{index}_NAME={name!r} is a duplicate within the batch file."
            )
        seen_names.add(name)
        entries.append(BatchEntry(
            name=name,
            url=fields["URL"],
            start=fields["START"],
            end=fields["END"],
        ))
    return entries
