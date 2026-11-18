"""Instagram JSON export (``message_1.json``, ...).

Instagram and Messenger share Meta's export format, including the mangled
encoding, so this reuses the Messenger parser. Two things differ:

* Telling them apart. The files look the same, so detection relies on the
  ``your_instagram_activity`` folder of the download, or on traces only Instagram
  leaves in the messages (see :data:`_CONTENT_HINTS`).
* Reaction notices. Instagram also logs a reaction as a message from the reacting
  person ("Reacted 😂 to your message", "Liked a message"). The reaction is already
  recorded on the message it belongs to, so these notices are dropped rather than
  counted as messages.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from nostos.loaders.messenger import find_message_files, messages_frame, read_documents
from nostos.schema import Conversation, MessageKind

_INSTAGRAM_FOLDER = "your_instagram_activity"
_FACEBOOK_FOLDER = "your_facebook_activity"

# Searched in the start of message_1.json, which holds the newest messages.
_HINT_BYTES = 256 * 1024
_CONTENT_HINTS = re.compile(
    rb"your_instagram_activity/"  # media paths
    rb'|"original_content_owner"'  # shared posts and reels
    rb'|"content":\s*"(?:Liked a message|Reacted [^"]{1,80} to your message)'
)

# English wording, which Instagram uses when the account language is English.
_REACTION_NOTICE = r"^(?:Liked a message|Reacted .{1,20} to your message)\s*$"


def looks_like_instagram(folder: Path) -> bool:
    """True if a Meta-style conversation folder came from Instagram, not Facebook."""
    parts = {part.lower() for part in folder.resolve().parts}
    if _INSTAGRAM_FOLDER in parts:
        return True
    if _FACEBOOK_FOLDER in parts:
        return False
    files = find_message_files(folder)
    if not files:
        return False
    with files[0].open("rb") as handle:
        return _CONTENT_HINTS.search(handle.read(_HINT_BYTES)) is not None


class InstagramLoader:
    name = "instagram"

    def can_load(self, path: Path) -> bool:
        return path.is_dir() and looks_like_instagram(path)

    def load(self, path: Path, *, timezone: str | None = None) -> Conversation:
        # Instagram stores absolute (UTC) timestamps, so ``timezone`` is not needed.
        frame, title = messages_frame(read_documents(path))
        notice = (pl.col("kind") == MessageKind.TEXT.value) & pl.col("text").str.contains(
            _REACTION_NOTICE
        )
        frame = frame.filter(~notice.fill_null(False))
        return Conversation.from_frame(frame, title=title or path.name, platform=self.name)
