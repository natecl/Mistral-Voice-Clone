# tests/test_downloader.py
import pytest

from voxclone import downloader


def test_download_audio_returns_extracted_wav_path(tmp_path, monkeypatch):
    fake_id = "abc123"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            # Simulate yt-dlp writing the post-processed wav file.
            (tmp_path / f"{fake_id}.wav").write_bytes(b"RIFFfakeaudio")
            return {"id": fake_id}

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    result = downloader.download_audio("https://youtu.be/x", tmp_path)
    assert result == tmp_path / f"{fake_id}.wav"
    assert result.read_bytes() == b"RIFFfakeaudio"


def test_download_audio_raises_when_file_missing(tmp_path, monkeypatch):
    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            return {"id": "missing"}  # never writes a file

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(RuntimeError, match="did not produce"):
        downloader.download_audio("https://youtu.be/x", tmp_path)
