"""Canonical, platform-independent representation of a conversation.

Every loader (Messenger, Instagram, WhatsApp) converts its native
export format into a :class:`Conversation` whose ``messages`` frame follows
:data:`MESSAGE_SCHEMA`. Everything downstream (analysis, reporting, plotting)
only ever sees this schema, so adding a platform never touches analysis code.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import polars as pl


class MessageKind(str, Enum):
    """What a message carries. Text is the default when nothing else matches."""

    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    CALL = "call"
    SHARE = "share"
    GIF = "gif"
    STICKER = "sticker"
    FILE = "file"
    UNSENT = "unsent"
    OTHER = "other"


KIND_DTYPE = pl.Enum([k.value for k in MessageKind])

#: Column name -> dtype. ``timestamp`` is timezone-aware; loaders emit UTC and
#: :meth:`Conversation.in_timezone` converts it once for all analyses.
MESSAGE_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime("ms", "UTC"),
    "sender": pl.String(),
    "text": pl.String(),
    "kind": KIND_DTYPE,
}


@dataclass(frozen=True, slots=True)
class Conversation:
    """A single chat thread, messages sorted oldest first."""

    title: str
    platform: str
    participants: tuple[str, ...]
    messages: pl.DataFrame

    @classmethod
    def from_frame(cls, frame: pl.DataFrame, *, title: str, platform: str) -> Conversation:
        """Validate, sort and wrap a frame that follows :data:`MESSAGE_SCHEMA`."""
        frame = frame.select(
            [pl.col(name).cast(dtype) for name, dtype in MESSAGE_SCHEMA.items()]
        ).sort("timestamp", maintain_order=True)
        # Participants are everyone who ever sent a message, in order of their
        # first message: the export's own participant list omits people who left.
        participants = tuple(frame.get_column("sender").unique(maintain_order=True).to_list())
        return cls(title=title, platform=platform, participants=participants, messages=frame)

    def in_timezone(self, tz: str) -> Conversation:
        """Return a copy whose timestamps are expressed in ``tz`` (an IANA name)."""
        messages = self.messages.with_columns(pl.col("timestamp").dt.convert_time_zone(tz))
        return replace(self, messages=messages)

    def __len__(self) -> int:
        return self.messages.height
