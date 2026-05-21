# tests/test_cli.py
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
