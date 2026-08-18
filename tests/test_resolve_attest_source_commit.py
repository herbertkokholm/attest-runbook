"""Tests for resolve_attest_source_commit.py (fully mocked -- never touches the real venv)."""

from __future__ import annotations

import json
import subprocess
from importlib import metadata

import pytest

import resolve_attest_source_commit as rasc


class _FakeDistribution:
    def __init__(self, direct_url: dict | None):
        self._text = json.dumps(direct_url) if direct_url is not None else None

    def read_text(self, filename: str) -> str | None:
        assert filename == "direct_url.json"
        return self._text


def test_resolves_commit_from_a_pinned_vcs_install(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDistribution(
        {
            "url": "https://github.com/herbertkokholm/attest.git",
            "vcs_info": {"vcs": "git", "commit_id": "deadbeef" * 5},
        }
    )
    monkeypatch.setattr(metadata, "distribution", lambda name: fake)

    assert rasc.resolve_attest_source_commit() == "deadbeef" * 5


def test_falls_back_to_git_rev_parse_for_an_editable_local_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeDistribution({"url": "file:///Users/dev/attest", "dir_info": {"editable": True}})
    monkeypatch.setattr(metadata, "distribution", lambda name: fake)

    captured_args = {}

    def fake_run(args, **kwargs):
        captured_args["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert rasc.resolve_attest_source_commit() == "abc123"
    assert captured_args["args"] == ["git", "-C", "/Users/dev/attest", "rev-parse", "HEAD"]


def test_returns_none_when_attest_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(name: str):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "distribution", _raise)

    assert rasc.resolve_attest_source_commit() is None


def test_returns_none_when_direct_url_json_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata, "distribution", lambda name: _FakeDistribution(None))

    assert rasc.resolve_attest_source_commit() is None


def test_returns_none_for_a_non_editable_non_vcs_install(monkeypatch: pytest.MonkeyPatch) -> None:
    # e.g. a plain sdist/wheel install with no direct_url provenance at all.
    fake = _FakeDistribution({"url": "https://pypi.org/simple/attest/", "archive_info": {}})
    monkeypatch.setattr(metadata, "distribution", lambda name: fake)

    assert rasc.resolve_attest_source_commit() is None


def test_returns_none_when_git_rev_parse_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDistribution({"url": "file:///Users/dev/attest", "dir_info": {"editable": True}})
    monkeypatch.setattr(metadata, "distribution", lambda name: fake)

    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(128, args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert rasc.resolve_attest_source_commit() is None


def test_main_prints_the_commit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rasc, "resolve_attest_source_commit", lambda: "abc123")

    rc = rasc.main()

    assert rc == 0
    assert capsys.readouterr().out == "abc123\n"


def test_main_prints_nothing_when_unresolvable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rasc, "resolve_attest_source_commit", lambda: None)

    rc = rasc.main()

    assert rc == 0
    assert capsys.readouterr().out == ""
