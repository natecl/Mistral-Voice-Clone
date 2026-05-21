# tests/test_cli.py
from pathlib import Path

import pytest

from voxclone import cli, registry


def test_voices_command_reports_empty_registry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["voices"])
    assert rc == 0
    assert "No saved voices" in capsys.readouterr().out


def test_voices_command_lists_saved_voices(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("alice", "voice-1")
    rc = cli.main(["voices"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "voice-1" in out


def test_no_subcommand_exits_with_error(monkeypatch):
    with pytest.raises(SystemExit):
        cli.main([])


def test_prepare_command_writes_reference_clip(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.deps, "check_dependencies", lambda: None)

    def fake_download(url, out_dir):
        path = Path(out_dir) / "audio.wav"
        path.write_bytes(b"RIFFaudio")
        return path

    def fake_extract(src, start, end, out_path):
        Path(out_path).write_bytes(b"RIFFclip")
        return Path(out_path)

    monkeypatch.setattr(cli.downloader, "download_audio", fake_download)
    monkeypatch.setattr(cli.clipper, "extract_clip", fake_extract)

    rc = cli.main(["prepare", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08",
                   "--out", "reference.wav"])
    assert rc == 0
    assert Path("reference.wav").read_bytes() == b"RIFFclip"
    assert "reference.wav" in capsys.readouterr().out
