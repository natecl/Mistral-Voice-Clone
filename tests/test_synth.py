# tests/test_synth.py
import base64
from types import SimpleNamespace

import pytest

from voxclone import synth


def _fake_client(capture, audio_bytes, fail_times=0, status_code=429):
    """Fake Mistral client; first `fail_times` calls raise a status error."""
    state = {"calls": 0}

    class ApiError(Exception):
        def __init__(self):
            self.status_code = status_code

    class FakeSpeech:
        def complete(self, **kwargs):
            state["calls"] += 1
            if state["calls"] <= fail_times:
                raise ApiError()
            capture.update(kwargs)
            capture["calls"] = state["calls"]
            return SimpleNamespace(
                audio_data=base64.b64encode(audio_bytes).decode()
            )

    return SimpleNamespace(audio=SimpleNamespace(speech=FakeSpeech()))


def test_synthesize_writes_decoded_audio(tmp_path):
    capture = {}
    client = _fake_client(capture, b"\x00\x01fake-mp3")
    out = tmp_path / "out.mp3"

    synth.synthesize(client, "voice-xyz", "Hello world", out)

    assert out.read_bytes() == b"\x00\x01fake-mp3"
    assert capture["model"] == "voxtral-mini-tts-2603"
    assert capture["voice_id"] == "voice-xyz"
    assert capture["input"] == "Hello world"
    assert capture["response_format"] == "mp3"


def test_synthesize_retries_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(synth.time, "sleep", lambda s: None)
    capture = {}
    client = _fake_client(capture, b"ok", fail_times=1, status_code=429)
    out = tmp_path / "out.mp3"

    synth.synthesize(client, "v", "hi", out)

    assert capture["calls"] == 2
    assert out.read_bytes() == b"ok"


def test_synthesize_gives_up_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(synth.time, "sleep", lambda s: None)
    client = _fake_client({}, b"never", fail_times=99, status_code=503)
    out = tmp_path / "out.mp3"

    with pytest.raises(Exception) as exc_info:
        synth.synthesize(client, "v", "hi", out, max_retries=2)
    assert exc_info.value.status_code == 503
    assert not out.exists()
