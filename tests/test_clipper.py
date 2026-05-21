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
