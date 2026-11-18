"""Instagram exports: Messenger's format, told apart by folder or content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nostos import loaders
from nostos.loaders.instagram import InstagramLoader, looks_like_instagram

from .conftest import ms, write_export

# Hand-written, newest first like the real export.
MESSAGES: list[dict[str, Any]] = [
    {"sender_name": "Βασίλης", "timestamp_ms": ms(2026, 3, 1, 9, 5), "content": "Liked a message"},
    {"sender_name": "Ana", "timestamp_ms": ms(2026, 3, 1, 9, 4), "content": "ναι 😂"},
    {
        "sender_name": "Βασίλης",
        "timestamp_ms": ms(2026, 3, 1, 9, 3),
        "content": "Reacted 😂 to your message ",
    },
    {
        "sender_name": "Βασίλης",
        "timestamp_ms": ms(2026, 3, 1, 9, 2),
        "content": "Βασίλης sent an attachment.",
        "share": {"link": "https://example.com/reel/1", "original_content_owner": "someone"},
    },
    {
        "sender_name": "Ana",
        "timestamp_ms": ms(2026, 3, 1, 9, 1),
        "content": "Reacted to your message, I mean it",
        "reactions": [{"reaction": "❤", "actor": "Βασίλης"}],
    },
    {"sender_name": "Ana", "timestamp_ms": ms(2026, 3, 1, 9, 0), "photos": [{"uri": "p.jpg"}]},
]

PLAIN = [{"sender_name": "Ana", "timestamp_ms": ms(2026, 3, 1), "content": "hi"}]


def test_instagram_export(tmp_path: Path) -> None:
    folder = write_export(tmp_path / "ana_123", [MESSAGES], title="Ana")
    conv = loaders.load(folder)
    assert conv.platform == "instagram"
    assert conv.title == "Ana"
    assert conv.participants == ("Ana", "Βασίλης")
    # Reaction notices are dropped; real text that merely mentions one is kept.
    assert conv.messages["text"].to_list() == [
        None,
        "Reacted to your message, I mean it",
        "Βασίλης sent an attachment.",
        "ναι 😂",
    ]
    assert conv.messages["kind"].cast(str).to_list() == ["photo", "text", "share", "text"]


def test_detected_by_download_folder(tmp_path: Path) -> None:
    inbox = tmp_path / "your_instagram_activity" / "messages" / "inbox"
    assert looks_like_instagram(write_export(inbox / "ana_123", [PLAIN]))
    assert loaders.load(inbox / "ana_123").platform == "instagram"


def test_facebook_download_folder_wins_over_content(tmp_path: Path) -> None:
    inbox = tmp_path / "your_facebook_activity" / "messages" / "inbox"
    folder = write_export(inbox / "ana_123", [MESSAGES])
    assert not looks_like_instagram(folder)
    assert loaders.load(folder).platform == "messenger"


def test_messenger_export_is_not_instagram(export_dir: Path, tmp_path: Path) -> None:
    assert not looks_like_instagram(export_dir)
    assert not looks_like_instagram(tmp_path)  # no message files at all
    assert not InstagramLoader().can_load(tmp_path / "missing")


def test_platform_can_be_forced(export_dir: Path) -> None:
    assert loaders.load(export_dir, "instagram").platform == "instagram"
