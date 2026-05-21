# tests/test_voices.py
import base64
from types import SimpleNamespace

from voxclone import voices


def _fake_client(capture):
    """A stand-in Mistral client whose audio.voices.create records kwargs."""

    class FakeVoices:
        def create(self, **kwargs):
            capture.update(kwargs)
            return SimpleNamespace(id="voice-xyz", name=kwargs["name"])

    return SimpleNamespace(audio=SimpleNamespace(voices=FakeVoices()))


def test_create_voice_returns_voice_id(tmp_path):
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"RIFFaudiodata")
    capture = {}
    client = _fake_client(capture)

    voice_id = voices.create_voice(client, "my-voice", clip, ["en"])

    assert voice_id == "voice-xyz"


def test_create_voice_sends_base64_audio_and_metadata(tmp_path):
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"RIFFaudiodata")
    capture = {}
    client = _fake_client(capture)

    voices.create_voice(client, "my-voice", clip, ["en", "fr"])

    assert capture["name"] == "my-voice"
    assert capture["sample_filename"] == "ref.wav"
    assert capture["languages"] == ["en", "fr"]
    assert base64.b64decode(capture["sample_audio"]) == b"RIFFaudiodata"
