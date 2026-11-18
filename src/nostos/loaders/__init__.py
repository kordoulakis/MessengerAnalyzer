"""Registry of platform loaders.

To add a platform, implement :class:`~nostos.loaders.base.Loader`
and append an instance to :data:`LOADERS`.
"""

from __future__ import annotations

from pathlib import Path

from nostos.loaders.base import Loader, LoaderError
from nostos.loaders.messenger import MessengerLoader
from nostos.schema import Conversation

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
    raise LoaderError(_explain_unrecognised(path))


def _explain_unrecognised(path: Path) -> str:
    """Say what is wrong with ``path`` in terms of the usual mistakes."""
    message = (
        f"No chat export found in {path}. Expected a conversation folder containing message_1.json."
    )
    if not path.is_dir():
        return message
    if any(path.glob("message_*.html")):
        return message + " This looks like an HTML export: download your data again in JSON format."
    conversations = sorted(
        p.name for p in path.iterdir() if p.is_dir() and any(ld.can_load(p) for ld in LOADERS)
    )
    if conversations:
        examples = ", ".join(conversations[:3]) + (", ..." if len(conversations) > 3 else "")
        return (
            message + f" This folder holds {len(conversations)} "
            f"conversation{'s' if len(conversations) != 1 else ''} ({examples}): "
            "point at one of them instead."
        )
    return message


__all__ = ["LOADERS", "Loader", "LoaderError", "get_loader", "load"]
