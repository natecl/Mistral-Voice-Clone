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


def test_clone_command_creates_and_saves_voice(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.deps, "check_dependencies", lambda: None)
    monkeypatch.setattr(cli.config, "get_client", lambda: object())

    def fake_download(url, out_dir):
        path = Path(out_dir) / "audio.wav"
        path.write_bytes(b"RIFFaudio")
        return path

    def fake_extract(src, start, end, out):
        Path(out).write_bytes(b"clip")
        return Path(out)

    monkeypatch.setattr(cli.downloader, "download_audio", fake_download)
    monkeypatch.setattr(cli.clipper, "extract_clip", fake_extract)
    monkeypatch.setattr(
        cli.voices, "create_voice",
        lambda client, name, clip, langs: "voice-123",
    )

    rc = cli.main(["clone", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08",
                   "--name", "bob", "--i-have-consent"])
    assert rc == 0
    assert registry.resolve_voice("bob") == "voice-123"
    assert "voice-123" in capsys.readouterr().out


def test_clone_command_aborts_without_consent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.deps, "check_dependencies", lambda: None)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")

    rc = cli.main(["clone", "https://youtu.be/x",
                   "--start", "0:01", "--end", "0:08", "--name", "bob"])
    assert rc == 1
    assert "Aborted" in capsys.readouterr().err


def test_speak_command_writes_output_for_saved_voice(tmp_path, monkeypatch,
                                                     capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    capture = {}

    def fake_synth(client, voice_id, text, out, response_format="mp3"):
        capture.update(voice_id=voice_id, text=text, fmt=response_format)
        Path(out).write_bytes(b"audio-bytes")
        return Path(out)

    monkeypatch.setattr(cli.synth, "synthesize", fake_synth)

    rc = cli.main(["speak", "--voice", "bob", "--text", "Hello there",
                   "--out", "result.mp3"])
    assert rc == 0
    assert capture["voice_id"] == "voice-123"  # name resolved to id
    assert capture["text"] == "Hello there"
    assert Path("result.mp3").read_bytes() == b"audio-bytes"


def test_speak_command_reads_text_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    (tmp_path / "script.txt").write_text("from a file")
    capture = {}

    def fake_synth(client, voice_id, text, out, response_format="mp3"):
        capture["text"] = text
        Path(out).write_bytes(b"x")
        return Path(out)

    monkeypatch.setattr(cli.synth, "synthesize", fake_synth)

    rc = cli.main(["speak", "--voice", "bob", "--text-file", "script.txt",
                   "--out", "out.mp3"])
    assert rc == 0
    assert capture["text"] == "from a file"


def test_speak_command_requires_text(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    rc = cli.main(["speak", "--voice", "bob"])
    assert rc == 1
    assert "text" in capsys.readouterr().err.lower()


def test_speak_command_reports_missing_text_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())
    rc = cli.main(["speak", "--voice", "bob", "--text-file", "nope.txt",
                   "--out", "out.mp3"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err


def test_speak_command_reports_api_error(tmp_path, monkeypatch, capsys):
    from mistralai.client.errors import MistralError

    class _FakeApiError(MistralError):
        """A MistralError subclass that avoids the SDK's __init__ args."""

        def __init__(self, message):
            self._message = message

        def __str__(self):
            return self._message

    monkeypatch.chdir(tmp_path)
    registry.save_voice("bob", "voice-123")
    monkeypatch.setattr(cli.config, "get_client", lambda: object())

    def boom(*args, **kwargs):
        raise _FakeApiError("api rejected the request")

    monkeypatch.setattr(cli.synth, "synthesize", boom)
    rc = cli.main(["speak", "--voice", "bob", "--text", "hi", "--out", "o.mp3"])
    assert rc == 1
    assert "api rejected the request" in capsys.readouterr().err
