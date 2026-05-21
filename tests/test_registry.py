# tests/test_registry.py
from voxclone import registry


def test_load_registry_missing_file_returns_empty(tmp_path):
    assert registry.load_registry(tmp_path / "nope.json") == {}


def test_save_and_load_voice(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.load_registry(path) == {"alice": "voice-1"}


def test_save_voice_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "voices.json"
    registry.save_voice("bob", "voice-2", path)
    assert path.exists()


def test_resolve_voice_returns_id_for_known_name(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.resolve_voice("alice", path) == "voice-1"


def test_resolve_voice_passes_through_unknown_value(tmp_path):
    path = tmp_path / "voices.json"
    assert registry.resolve_voice("raw-voice-id", path) == "raw-voice-id"


def test_remove_voice(tmp_path):
    path = tmp_path / "voices.json"
    registry.save_voice("alice", "voice-1", path)
    assert registry.remove_voice("alice", path) is True
    assert registry.load_registry(path) == {}
    assert registry.remove_voice("alice", path) is False
