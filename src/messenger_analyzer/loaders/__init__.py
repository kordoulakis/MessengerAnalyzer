"""Registry of platform loaders.

To add a platform, implement :class:`~messenger_analyzer.loaders.base.Loader`
and append an instance to :data:`LOADERS`.
"""

from __future__ import annotations

from pathlib import Path

from messenger_analyzer.loaders.base import Loader, LoaderError
from messenger_analyzer.loaders.messenger import MessengerLoader
from messenger_analyzer.schema import Conversation

LOADERS: tuple[Loader, ...] = (MessengerLoader(),)


def get_loader(name: str) -> Loader:
    for loader in LOADERS:
        if loader.name == name:
            return loader
    known = ", ".join(loader.name for loader in LOADERS)
    raise LoaderError(f"Unknown platform {name!r}. Known: {known}")


def load(path: Path, platform: str | None = None) -> Conversation:
    """Load ``path`` with the named loader, or the first one that recognises it."""
    if platform is not None:
        return get_loader(platform).load(path)
    for loader in LOADERS:
        if loader.can_load(path):
            return loader.load(path)
    raise LoaderError(f"No loader recognises {path}")


__all__ = ["LOADERS", "Loader", "LoaderError", "get_loader", "load"]
