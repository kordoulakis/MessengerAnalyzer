"""Facebook Messenger JSON export (``message_1.json``, ``message_2.json``, ...)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import orjson
import polars as pl

from messenger_analyzer.loaders.base import LoaderError
from messenger_analyzer.schema import KIND_DTYPE, Conversation, MessageKind

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


class MessengerLoader:
    name = "messenger"

    def can_load(self, path: Path) -> bool:
        return path.is_dir() and bool(find_message_files(path))

    def load(self, path: Path) -> Conversation:
        if not path.is_dir():
            raise LoaderError(f"Not a folder: {path}")
        files = find_message_files(path)
        if not files:
            raise LoaderError(f"No message_N.json files in {path}")
        documents = [self._read(f) for f in files]
        return self.from_documents(documents, default_title=path.name)

    @staticmethod
    def _read(file: Path) -> dict[str, Any]:
        try:
            document = orjson.loads(file.read_bytes())
        except orjson.JSONDecodeError as exc:
            raise LoaderError(f"{file} is not valid JSON: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("messages"), list):
            raise LoaderError(f"{file} has no 'messages' list; is it a Messenger export?")
        return document

    @staticmethod
    def from_documents(
        documents: Iterable[dict[str, Any]], *, default_title: str = "Conversation"
    ) -> Conversation:
        """Build a conversation from already-parsed JSON documents."""
        messages: list[dict[str, Any]] = []
        title = default_title
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
        return Conversation.from_frame(
            frame, title=fix_mojibake(title), platform=MessengerLoader.name
        )
