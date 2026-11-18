from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from nostos.loaders.messenger import MessengerLoader
from nostos.schema import Conversation


def ms(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    """UTC timestamp in milliseconds."""
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def mangle(text: str) -> str:
    """Reproduce Messenger's encoding bug: one character per UTF-8 byte."""
    return text.encode("utf-8").decode("latin-1")


def write_export(folder: Path, files: list[list[dict[str, Any]]], title: str = "Chat") -> Path:
    """Write ``message_1.json``... the way Messenger does (newest first, mangled text)."""
    folder.mkdir(parents=True, exist_ok=True)
    for index, messages in enumerate(files, start=1):
        fixed = []
        for message in messages:
            m = dict(message)
            m["sender_name"] = mangle(m["sender_name"])
            if "content" in m:
                m["content"] = mangle(m["content"])
            fixed.append(m)
        document = {"participants": [], "messages": fixed, "title": mangle(title)}
        (folder / f"message_{index}.json").write_text(json.dumps(document), encoding="utf-8")
    return folder


# Two months of chat between Ana and Βασίλης (non-ASCII on purpose), plus Cam who
# only ever sends a photo. Listed oldest first here; write_export reverses nothing,
# so tests also cover arbitrary ordering by shuffling between files.
MESSAGES: list[dict[str, Any]] = [
    {"sender_name": "Ana", "timestamp_ms": ms(2020, 1, 1, 10, 0), "content": "one two three four"},
    {"sender_name": "Βασίλης", "timestamp_ms": ms(2020, 1, 1, 10, 1), "content": "Γειά!"},
    {"sender_name": "Βασίλης", "timestamp_ms": ms(2020, 1, 1, 10, 2), "content": "hello hello"},
    {"sender_name": "Ana", "timestamp_ms": ms(2020, 1, 3, 9, 0), "content": "Hello, world."},
    {"sender_name": "Ana", "timestamp_ms": ms(2020, 2, 1, 8, 0), "content": "a b"},
    {"sender_name": "Βασίλης", "timestamp_ms": ms(2020, 2, 1, 8, 5), "photos": [{"uri": "x"}]},
    {
        "sender_name": "Βασίλης",
        "timestamp_ms": ms(2020, 2, 1, 8, 6),
        "content": "The video chat ended.",
        "call_duration": 60,
    },
    {"sender_name": "Cam", "timestamp_ms": ms(2020, 2, 2, 8, 0), "photos": [{"uri": "y"}]},
]


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    # Messenger puts the newest messages in message_1.json, newest first.
    newest_first = list(reversed(MESSAGES))
    return write_export(
        tmp_path / "chat", [newest_first[:3], newest_first[3:]], title="Ana & Βασίλης"
    )


@pytest.fixture
def conversation(export_dir: Path) -> Conversation:
    return MessengerLoader().load(export_dir).in_timezone("UTC")
