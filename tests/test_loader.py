from __future__ import annotations

from pathlib import Path

import pytest

from nostos import loaders
from nostos.loaders.messenger import MessengerLoader, find_message_files, fix_mojibake
from nostos.schema import Conversation

from .conftest import MESSAGES, ms, write_export


def test_fix_mojibake_round_trips_and_leaves_clean_text_alone() -> None:
    assert fix_mojibake("Ã©") == "é"
    assert fix_mojibake("plain") == "plain"
    assert fix_mojibake("Γειά") == "Γειά"  # already correct, not Latin-1 encodable


def test_load_sorts_oldest_first_and_fixes_encoding(conversation: Conversation) -> None:
    m = conversation.messages
    assert len(conversation) == len(MESSAGES)
    assert m["timestamp"].is_sorted()
    assert m["sender"][1] == "Βασίλης"
    assert m["text"][1] == "Γειά!"
    assert conversation.title == "Ana & Βασίλης"
    assert conversation.participants == ("Ana", "Βασίλης", "Cam")


def test_message_kinds(conversation: Conversation) -> None:
    assert conversation.messages["kind"].cast(str).to_list() == [
        "text",
        "text",
        "text",
        "text",
        "text",
        "photo",
        "call",
        "photo",
    ]


def test_file_order_does_not_matter(tmp_path: Path) -> None:
    shuffled = [MESSAGES[3], MESSAGES[0], MESSAGES[7], MESSAGES[1]]
    folder = write_export(tmp_path / "c", [shuffled[:2], shuffled[2:]])
    conv = MessengerLoader().load(folder)
    assert conv.messages["timestamp"].is_sorted()


def test_files_sorted_numerically(tmp_path: Path) -> None:
    for n in (10, 2, 1):
        (tmp_path / f"message_{n}.json").write_text("{}")
    (tmp_path / "notes.txt").write_text("")
    assert [p.name for p in find_message_files(tmp_path)] == [
        "message_1.json",
        "message_2.json",
        "message_10.json",
    ]


def test_unsent_and_unknown_messages(tmp_path: Path) -> None:
    folder = write_export(
        tmp_path / "c",
        [
            [
                {"sender_name": "A", "timestamp_ms": ms(2021, 1, 1), "is_unsent": True},
                {"sender_name": "A", "timestamp_ms": ms(2021, 1, 2), "sticker": {"uri": "s"}},
                {"sender_name": "A", "timestamp_ms": ms(2021, 1, 3)},
            ]
        ],
    )
    kinds = MessengerLoader().load(folder).messages["kind"].cast(str).to_list()
    assert kinds == ["unsent", "sticker", "other"]


def test_timezone_conversion(conversation: Conversation) -> None:
    athens = conversation.in_timezone("Europe/Athens")
    assert athens.messages["timestamp"].dt.hour()[0] == 12  # 10:00 UTC in January


@pytest.mark.parametrize(
    ("content", "match"),
    [
        (None, "No message_N.json"),
        ("not json", "not valid JSON"),
        ('{"foo": 1}', "no 'messages' list"),
        ('{"messages": [{"content": "x"}]}', "missing field"),
    ],
)
def test_bad_exports_raise_loader_error(tmp_path: Path, content: str | None, match: str) -> None:
    if content is not None:
        (tmp_path / "message_1.json").write_text(content)
    with pytest.raises(loaders.LoaderError, match=match):
        MessengerLoader().load(tmp_path)


def test_registry(export_dir: Path, tmp_path: Path) -> None:
    assert loaders.load(export_dir).platform == "messenger"
    with pytest.raises(loaders.LoaderError, match="Unknown platform"):
        loaders.get_loader("carrier-pigeon")
    with pytest.raises(loaders.LoaderError, match="No chat export found"):
        loaders.load(tmp_path / "missing")


def test_unrecognised_folders_explain_the_mistake(export_dir: Path, tmp_path: Path) -> None:
    html_export = tmp_path / "html"
    html_export.mkdir()
    (html_export / "message_1.html").write_text("<html></html>")
    with pytest.raises(loaders.LoaderError, match="HTML export"):
        loaders.load(html_export)
    # export_dir's parent is like Facebook's inbox folder: conversations, not messages.
    with pytest.raises(loaders.LoaderError, match=r"holds 1 conversation \(chat\)"):
        loaders.load(export_dir.parent)
