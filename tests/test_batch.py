# tests/test_batch.py
from pathlib import Path

import pytest

from voxclone import batch, cli, registry


# ---------- parse_batch_file ----------

def _write(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "voices.env"
    f.write_text(body)
    return f


def test_parse_returns_entries_in_ascending_n_order(tmp_path):
    f = _write(tmp_path, """
VOICE2_NAME=bob
VOICE2_URL=https://youtu.be/xyz
VOICE2_START=1:00
VOICE2_END=1:10

VOICE1_NAME=alice
VOICE1_URL=https://youtu.be/abc
VOICE1_START=0:30
VOICE1_END=0:40
""")
    entries = batch.parse_batch_file(f)
    assert [e.name for e in entries] == ["alice", "bob"]
    assert entries[0].url == "https://youtu.be/abc"
    assert entries[0].start == "0:30"
    assert entries[0].end == "0:40"
    assert entries[1].url == "https://youtu.be/xyz"


def test_parse_allows_sparse_numbering(tmp_path):
    f = _write(tmp_path, """
VOICE5_NAME=alice
VOICE5_URL=u1
VOICE5_START=0:01
VOICE5_END=0:05

VOICE99_NAME=bob
VOICE99_URL=u2
VOICE99_START=0:01
VOICE99_END=0:05
""")
    entries = batch.parse_batch_file(f)
    assert [e.name for e in entries] == ["alice", "bob"]


def test_parse_errors_on_missing_required_key(tmp_path):
    f = _write(tmp_path, """
VOICE1_NAME=alice
VOICE1_URL=u1
VOICE1_START=0:01
""")
    with pytest.raises(ValueError, match="VOICE1.*END"):
        batch.parse_batch_file(f)


def test_parse_errors_on_unknown_key_under_voice_prefix(tmp_path):
    f = _write(tmp_path, """
VOICE1_NAME=alice
VOICE1_URL=u1
VOICE1_START=0:01
VOICE1_END=0:05
VOICE1_URLS=oops
""")
    with pytest.raises(ValueError, match="URLS"):
        batch.parse_batch_file(f)


def test_parse_errors_on_duplicate_name(tmp_path):
    f = _write(tmp_path, """
VOICE1_NAME=alice
VOICE1_URL=u1
VOICE1_START=0:01
VOICE1_END=0:05

VOICE2_NAME=alice
VOICE2_URL=u2
VOICE2_START=0:01
VOICE2_END=0:05
""")
    with pytest.raises(ValueError, match="duplicate"):
        batch.parse_batch_file(f)


def test_parse_errors_on_empty_file(tmp_path):
    f = _write(tmp_path, "# only a comment\n")
    with pytest.raises(ValueError, match="no voice entries"):
        batch.parse_batch_file(f)


def test_parse_ignores_blank_or_malformed_lines(tmp_path):
    # `=value` is exposed by python-dotenv as a blank key; should be ignored,
    # not raised as "Unrecognized key: ''".
    f = _write(tmp_path, """
=stray
VOICE1_NAME=alice
VOICE1_URL=u1
VOICE1_START=0:01
VOICE1_END=0:05
""")
    entries = batch.parse_batch_file(f)
    assert [e.name for e in entries] == ["alice"]


def test_parse_errors_on_zero_or_negative_index(tmp_path):
    f = _write(tmp_path, """
VOICE0_NAME=alice
VOICE0_URL=u1
VOICE0_START=0:01
VOICE0_END=0:05
""")
    with pytest.raises(ValueError, match="VOICE0"):
        batch.parse_batch_file(f)


# ---------- clone-batch CLI ----------

def _stub_pipeline(monkeypatch):
    """Stub deps + downloader + clipper + config so clone-batch runs in-process."""
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


_BATCH_FILE = """
VOICE1_NAME=alice
VOICE1_URL=https://youtu.be/abc
VOICE1_START=0:30
VOICE1_END=0:40

VOICE2_NAME=bob
VOICE2_URL=https://youtu.be/xyz
VOICE2_START=1:00
VOICE2_END=1:10
"""


def test_clone_batch_creates_all_voices(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _stub_pipeline(monkeypatch)

    calls = []

    def fake_create(client, name, clip, langs):
        calls.append(name)
        return f"voice-{name}"

    monkeypatch.setattr(cli.voices, "create_voice", fake_create)
    (tmp_path / "voices.env").write_text(_BATCH_FILE)

    rc = cli.main(["clone-batch", "voices.env", "--i-have-consent"])
    assert rc == 0
    assert calls == ["alice", "bob"]
    assert registry.resolve_voice("alice") == "voice-alice"
    assert registry.resolve_voice("bob") == "voice-bob"
    out = capsys.readouterr().out
    assert "[1/2]" in out and "[2/2]" in out


def test_clone_batch_aborts_on_name_collision_before_any_api_call(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    _stub_pipeline(monkeypatch)
    registry.save_voice("alice", "preexisting")

    def boom(*a, **k):
        raise AssertionError("create_voice must not be called on collision")

    monkeypatch.setattr(cli.voices, "create_voice", boom)
    (tmp_path / "voices.env").write_text(_BATCH_FILE)

    rc = cli.main(["clone-batch", "voices.env", "--i-have-consent"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "alice" in err
    # The preexisting entry must be untouched.
    assert registry.resolve_voice("alice") == "preexisting"


def test_clone_batch_aborts_on_first_failure_and_keeps_prior(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    _stub_pipeline(monkeypatch)

    def fake_create(client, name, clip, langs):
        if name == "bob":
            raise RuntimeError("simulated API failure")
        return f"voice-{name}"

    monkeypatch.setattr(cli.voices, "create_voice", fake_create)
    (tmp_path / "voices.env").write_text(_BATCH_FILE)

    rc = cli.main(["clone-batch", "voices.env", "--i-have-consent"])
    assert rc == 1
    saved = registry.load_registry()
    # alice was created before bob failed and is persisted.
    assert saved.get("alice") == "voice-alice"
    # bob was never saved (resolve_voice is a passthrough for unknowns, so
    # check the registry contents directly).
    assert "bob" not in saved
    assert "simulated API failure" in capsys.readouterr().err


def test_clone_batch_requires_consent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    monkeypatch.setattr(cli.voices, "create_voice",
                        lambda *a, **k: pytest.fail("must not run without consent"))
    (tmp_path / "voices.env").write_text(_BATCH_FILE)

    rc = cli.main(["clone-batch", "voices.env"])
    assert rc == 1
    assert "Aborted" in capsys.readouterr().err


def test_clone_batch_reports_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(
        cli.voices, "create_voice",
        lambda *a, **k: pytest.fail("create_voice called for missing file"),
    )
    rc = cli.main(["clone-batch", "nope.env", "--i-have-consent"])
    assert rc == 1
    assert "nope.env" in capsys.readouterr().err
