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


def _probe(path, entry):
    """Return a single ffprobe value for the given stream/format entry."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entry,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


@pytest.fixture
def sine_audio(tmp_path):
    """A 20-second 440 Hz stereo test tone created with ffmpeg."""
    src = tmp_path / "sine.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=20:sample_rate=44100",
         "-ac", "2", str(src)],
        capture_output=True, check=True,
    )
    return src


def test_extract_clip_has_correct_duration(sine_audio, tmp_path):
    out = tmp_path / "clip.wav"
    clipper.extract_clip(sine_audio, "0:02", "0:09", out)
    assert out.exists()
    duration = float(_probe(out, "format=duration"))
    assert 6.5 < duration < 7.5  # ~7s clip


def test_extract_clip_is_mono_24khz(sine_audio, tmp_path):
    out = tmp_path / "clip.wav"
    clipper.extract_clip(sine_audio, "0:00", "0:05", out)
    assert _probe(out, "stream=channels") == "1"
    assert _probe(out, "stream=sample_rate") == "24000"


def test_extract_clip_rejects_non_positive_duration(sine_audio, tmp_path):
    with pytest.raises(ValueError, match="after start"):
        clipper.extract_clip(sine_audio, "0:09", "0:02", tmp_path / "x.wav")


def test_extract_clip_warns_when_too_short(sine_audio, tmp_path, capsys):
    clipper.extract_clip(sine_audio, "0:00", "0:01", tmp_path / "short.wav")
    assert "best with" in capsys.readouterr().out
