"""Nostos is local-only: nothing it runs or writes may reach the network."""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import Any

import pytest

from nostos.cli import main


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to open a network connection fail the test."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"Nostos tried to use the network: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize(
    "args",
    [
        ["list", "--sources", "."],
        ["report", "chat", "--sources", ".", "--format", "json", "-o", "out.json"],
        ["charts"],
        ["plot", "chat", "rhythm", "--sources", ".", "-o", "out.html"],
        ["dashboard", "chat", "--sources", ".", "-o", "out.html"],
    ],
    ids=lambda a: a[0],
)
def test_commands_work_without_network(
    args: list[str], export_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(export_dir.parent)
    assert main(args) == 0


# Any tag that would make a browser fetch something: <script src>, <link href>, <img src>, ...
_REMOTE_RESOURCE = re.compile(
    r"""<(?:script|link|img|iframe|source)\b[^>]*\b(?:src|href)\s*=\s*["']?(?:https?:)?//""", re.I
)


def test_pages_reference_no_remote_resources(export_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "d.html"
    assert main(["dashboard", str(export_dir), "-o", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert not _REMOTE_RESOURCE.search(page)
    assert "@import" not in page  # no remote stylesheets or fonts


def test_cdn_option_is_gone(export_dir: Path) -> None:
    with pytest.raises(SystemExit):
        main(["dashboard", str(export_dir), "--cdn"])
