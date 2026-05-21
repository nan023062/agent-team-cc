"""Tests for remote tag enumeration + network probe."""
from __future__ import annotations

import subprocess

import pytest

from cbim_kernel.project.upgrade import remote
from cbim_kernel.project.upgrade.config import default_config


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ls_remote_tags_parses_refs(monkeypatch):
    out = "\n".join([
        "abc\trefs/tags/v1.0.0",
        "def\trefs/tags/v1.2.0",
        "ghi\trefs/tags/v1.2.0^{}",     # peeled tag, dedup
        "jkl\trefs/heads/main",          # ignored
        "mno\trefs/tags/v1.2.3",
    ]) + "\n"

    def fake_run(cmd, **kw):
        assert cmd[0] == "git"
        return _FakeCompleted(0, stdout=out)

    monkeypatch.setattr(remote.subprocess, "run", fake_run)
    tags = remote.ls_remote_tags("https://example/cbim.git")
    assert tags == ["v1.0.0", "v1.2.0", "v1.2.3"]


def test_ls_remote_tags_returns_empty_on_failure(monkeypatch):
    def fake_run(cmd, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(remote.subprocess, "run", fake_run)
    assert remote.ls_remote_tags("x") == []


def test_ls_remote_tags_returns_empty_on_nonzero_exit(monkeypatch):
    def fake_run(cmd, **kw):
        return _FakeCompleted(128, stderr="fatal: not a git repo")

    monkeypatch.setattr(remote.subprocess, "run", fake_run)
    assert remote.ls_remote_tags("x") == []


def test_latest_tag_filters_and_sorts(monkeypatch):
    monkeypatch.setattr(
        remote, "ls_remote_tags",
        lambda url: ["v1.0.0", "v1.2.3", "v0.9.0", "beta-x", "v1.10.0"],
    )
    assert remote.latest_tag("x", "v*") == "v1.10.0"


def test_latest_tag_pattern_filters(monkeypatch):
    monkeypatch.setattr(
        remote, "ls_remote_tags",
        lambda url: ["v1.0.0", "release-1.2.3", "release-2.0.0"],
    )
    assert remote.latest_tag("x", "release-*") == "release-2.0.0"


def test_latest_tag_returns_none_when_no_match(monkeypatch):
    monkeypatch.setattr(remote, "ls_remote_tags", lambda url: ["beta-1"])
    assert remote.latest_tag("x", "v*") is None


def test_get_remote_state_skip_network_short_circuits(monkeypatch):
    # Should NOT call network_available or ls_remote_tags.
    def boom(*a, **kw):
        raise AssertionError("must not be called when skip_network=True")

    monkeypatch.setattr(remote, "network_available", boom)
    monkeypatch.setattr(remote, "ls_remote_tags", boom)
    state = remote.get_remote_state(default_config(), skip_network=True)
    assert state.reachable is False
    assert state.latest is None


def test_get_remote_state_network_down(monkeypatch):
    monkeypatch.setattr(remote, "network_available", lambda: False)
    state = remote.get_remote_state(default_config(), skip_network=False)
    assert state.reachable is False
    assert state.latest is None


def test_get_remote_state_happy(monkeypatch):
    monkeypatch.setattr(remote, "network_available", lambda: True)
    monkeypatch.setattr(remote, "latest_tag", lambda url, pat: "v1.2.5")
    state = remote.get_remote_state(default_config(), skip_network=False)
    assert state.reachable is True
    assert state.latest == "v1.2.5"


def test_network_available_returns_bool(monkeypatch):
    # Just confirm it returns a bool without hanging — patch socket.
    import socket as _socket

    class _Sock:
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def fake_create_connection(addr, timeout):
        return _Sock()

    monkeypatch.setattr(_socket, "create_connection", fake_create_connection)
    assert remote.network_available() is True

    def fake_fail(addr, timeout):
        raise OSError("net down")

    monkeypatch.setattr(_socket, "create_connection", fake_fail)
    assert remote.network_available() is False
