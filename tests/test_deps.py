# tests/test_deps.py
import pytest

from voxclone import deps


def test_check_dependencies_passes_when_tools_present(monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    deps.check_dependencies()  # should not raise


def test_check_dependencies_raises_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda tool: None)
    with pytest.raises(deps.MissingDependencyError, match="ffmpeg"):
        deps.check_dependencies()


def test_check_dependencies_raises_for_missing_ffprobe_only(monkeypatch):
    monkeypatch.setattr(
        deps.shutil, "which",
        lambda tool: None if tool == "ffprobe" else f"/usr/bin/{tool}",
    )
    with pytest.raises(deps.MissingDependencyError, match="ffprobe"):
        deps.check_dependencies()
