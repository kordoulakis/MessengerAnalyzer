"""Facebook Messenger JSON export (``message_1.json``, ``message_2.json``, ...)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import orjson
import polars as pl

from nostos.loaders.base import LoaderError
from nostos.schema import KIND_DTYPE, Conversation, MessageKind

_FILE_PATTERN = re.compile(r"^message_(\d+)\.json$", re.IGNORECASE)

# First matching key decides the kind. A share or call usually also has
# ``content`` (e.g. "The video chat ended."), so these are checked before text.
_KIND_KEYS: tuple[tuple[str, MessageKind], ...] = (
    ("photos", MessageKind.PHOTO),
    ("videos", MessageKind.VIDEO),
    ("audio_files", MessageKind.AUDIO),
    ("call_duration", MessageKind.CALL),
    ("share", MessageKind.SHARE),
    ("gifs", MessageKind.GIF),
    ("sticker", MessageKind.STICKER),
    ("files", MessageKind.FILE),
)


def fix_mojibake(value: str) -> str:
    """Undo Messenger's encoding bug.

    The export writes each UTF-8 byte as its own ``\\u00XX`` escape, so after
    JSON decoding "é" reads as "Ã©". Re-encoding as Latin-1 recovers the bytes.
    Strings that were not mangled are returned unchanged.
    """
    if value.isascii():
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


_SPECIAL_KEYS = frozenset(key for key, _ in _KIND_KEYS) | {"is_unsent"}
_TEXT, _OTHER = MessageKind.TEXT.value, MessageKind.OTHER.value


def _kind_of(message: dict[str, Any]) -> str:
    # Fast path: the vast majority of messages are plain text.
    if _SPECIAL_KEYS.isdisjoint(message):
        return _TEXT if "content" in message else _OTHER
    if message.get("is_unsent"):
        return MessageKind.UNSENT.value
    for key, kind in _KIND_KEYS:
        if key in message:
            return kind.value
    return _TEXT if "content" in message else _OTHER


def find_message_files(folder: Path) -> list[Path]:
    """Return the ``message_N.json`` files in ``folder``, ordered by N."""
    matches = [(m, p) for p in folder.iterdir() if (m := _FILE_PATTERN.match(p.name))]
    return [p for m, p in sorted(matches, key=lambda mp: int(mp[0].group(1)))]


def read_documents(folder: Path) -> list[dict[str, Any]]:
    """Parse every ``message_N.json`` in ``folder``."""
    if not folder.is_dir():
        raise LoaderError(f"Not a folder: {folder}")
    files = find_message_files(folder)
    if not files:
        raise LoaderError(f"No message_N.json files in {folder}")
    return [_read(f) for f in files]


def _read(file: Path) -> dict[str, Any]:
    try:
        document = orjson.loads(file.read_bytes())
    except orjson.JSONDecodeError as exc:
        raise LoaderError(f"{file} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("messages"), list):
        raise LoaderError(f"{file} has no 'messages' list; is it a Messenger export?")
    return document


def messages_frame(documents: Iterable[dict[str, Any]]) -> tuple[pl.DataFrame, str | None]:
    """The messages of already-parsed documents as a schema frame, plus the thread title.

    Shared by Messenger and Instagram, whose exports have the same structure.
    """
    messages: list[dict[str, Any]] = []
    title: str | None = None
    for document in documents:
        title = document.get("title") or title
        messages.extend(document["messages"])

    # Column-wise comprehensions are much faster than appending per message.
    try:
        timestamps = [m["timestamp_ms"] for m in messages]
        senders = [m["sender_name"] for m in messages]
    except KeyError as exc:
        bad = next(m for m in messages if exc.args[0] not in m)
        raise LoaderError(f"Message missing field {exc}: {bad!r:.200}") from exc
    texts = [m.get("content") for m in messages]
    texts = [t if t is None or t.isascii() else fix_mojibake(t) for t in texts]
    kinds = [_kind_of(m) for m in messages]

    frame = pl.DataFrame(
        {
            "timestamp": pl.Series(timestamps, dtype=pl.Int64).cast(pl.Datetime("ms", "UTC")),
            # Few distinct senders: fix their names once, not once per message.
            "sender": pl.Series(senders, dtype=pl.String).replace_strict(
                {name: fix_mojibake(name) for name in set(senders)}
            ),
            "text": pl.Series(texts, dtype=pl.String),
            "kind": pl.Series(kinds, dtype=KIND_DTYPE),
        }
    )
    return frame, fix_mojibake(title) if title else None


class MessengerLoader:
    name = "messenger"

    def can_load(self, path: Path) -> bool:
        return path.is_dir() and bool(find_message_files(path))

    def load(self, path: Path, *, timezone: str | None = None) -> Conversation:
        # Messenger stores absolute (UTC) timestamps, so ``timezone`` is not needed.
        frame, title = messages_frame(read_documents(path))
        return Conversation.from_frame(frame, title=title or path.name, platform=self.name)
