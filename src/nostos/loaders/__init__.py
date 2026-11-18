"""Registry of platform loaders.

To add a platform, implement :class:`~nostos.loaders.base.Loader`
and add an instance to :data:`LOADERS`.
"""

from __future__ import annotations

from pathlib import Path

from nostos.loaders.base import Loader, LoaderError
from nostos.loaders.instagram import InstagramLoader
from nostos.loaders.messenger import MessengerLoader
from nostos.loaders.whatsapp import WhatsAppLoader
from nostos.schema import Conversation

#: Tried in order when detecting a format. Instagram comes before Messenger: their
#: folders look alike, and Messenger is the fallback for any Meta-style export.
LOADERS: tuple[Loader, ...] = (InstagramLoader(), MessengerLoader(), WhatsAppLoader())


def get_loader(name: str) -> Loader:
    for loader in LOADERS:
        if loader.name == name:
            return loader
    known = ", ".join(loader.name for loader in LOADERS)
    raise LoaderError(f"Unknown platform {name!r}. Known: {known}")


def detect(path: Path) -> Loader | None:
    """The first loader that recognises ``path``."""
    return next((loader for loader in LOADERS if loader.can_load(path)), None)


def load(path: Path, platform: str | None = None, *, timezone: str | None = None) -> Conversation:
    """Load ``path`` with the named loader, or the first one that recognises it.

    ``timezone`` is how to read exports that store local times without a zone
    (WhatsApp); ``None`` means this computer's timezone.
    """
    loader = get_loader(platform) if platform is not None else detect(path)
    if loader is None:
        raise LoaderError(_explain_unrecognised(path))
    return loader.load(path, timezone=timezone)


def _explain_unrecognised(path: Path) -> str:
    """Say what is wrong with ``path`` in terms of the usual mistakes."""
    message = (
        f"No chat export found in {path}. Expected a conversation folder containing "
        "message_1.json (Messenger, Instagram) or a WhatsApp chat .txt file."
    )
    if path.suffix.lower() == ".zip":
        return message + " This is a zip file: unzip it first."
    if not path.is_dir():
        return message
    if any(path.glob("message_*.html")):
        return message + " This looks like an HTML export: download your data again in JSON format."
    conversations = sorted(p.name for p in path.iterdir() if p.is_dir() and detect(p))
    if conversations:
        examples = ", ".join(conversations[:3]) + (", ..." if len(conversations) > 3 else "")
        return (
            message + f" This folder holds {len(conversations)} "
            f"conversation{'s' if len(conversations) != 1 else ''} ({examples}): "
            "point at one of them instead."
        )
    return message


__all__ = ["LOADERS", "Loader", "LoaderError", "detect", "get_loader", "load"]
