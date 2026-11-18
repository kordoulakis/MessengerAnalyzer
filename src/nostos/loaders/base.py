"""Loader interface shared by every chat platform."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from nostos.schema import Conversation


class LoaderError(Exception):
    """Raised when an export cannot be found or parsed."""


class Loader(Protocol):
    """Turns a platform's export into a :class:`Conversation`."""

    #: Short identifier used on the command line, e.g. ``"messenger"``.
    name: str

    def can_load(self, path: Path) -> bool:
        """Return True if ``path`` looks like an export this loader understands."""
        ...

    def load(self, path: Path) -> Conversation:
        """Parse the export at ``path``. Raises :class:`LoaderError` on failure."""
        ...
