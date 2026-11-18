"""Loader interface shared by every chat platform."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from tzlocal import get_localzone_name

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

    def load(self, path: Path, *, timezone: str | None = None) -> Conversation:
        """Parse the export at ``path``. Raises :class:`LoaderError` on failure.

        ``timezone`` (an IANA name) is how to read times that the export writes
        without one, as WhatsApp does; ``None`` means this computer's timezone.
        Exports that store absolute times ignore it.
        """
        ...


def local_timezone() -> str:
    """This computer's IANA timezone name, or ``"UTC"`` if it cannot be determined."""
    try:
        name = get_localzone_name()
    except Exception:  # tzlocal can fail on unusual systems; UTC is a safe default
        return "UTC"
    return name or "UTC"
