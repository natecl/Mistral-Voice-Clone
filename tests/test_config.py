# tests/test_config.py
import pytest

from voxclone import config


def test_get_api_key_returns_env_value(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-123")
    assert config.get_api_key() == "test-key-123"


def test_get_api_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env file here
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(config.ConfigError, match="MISTRAL_API_KEY"):
        config.get_api_key()


def test_constants_have_expected_values():
    assert config.MODEL == "voxtral-mini-tts-2603"
    assert config.SAMPLE_RATE == 24000
    assert config.MIN_CLIP_SECONDS == 3.0
    assert config.MAX_CLIP_SECONDS == 10.0
