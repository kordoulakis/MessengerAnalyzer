"""WhatsApp chat exports. Fixtures are hand-written, in the formats phones produce."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from nostos import loaders
from nostos.cli import main
from nostos.loaders.whatsapp import WhatsAppLoader, parse_chat
from nostos.schema import Conversation

LRM = chr(0x200E)  # left-to-right mark, which iPhone exports put before system text
NNBSP = chr(0x202F)  # narrow no-break space, used before AM/PM on newer phones

IPHONE = f"""\
[03/02/2024, 21:15:02] Ana: {LRM}Messages and calls are end-to-end encrypted..
[03/02/2024, 21:15:40] Ana: Hi Ben!
[03/02/2024, 21:16:05] Ben: Hello: how are you?
This line continues the message.

So does this one.
[04/02/2024, 08:00:00] Ben: {LRM}image omitted
[04/02/2024, 08:01:00] Ana: {LRM}<attached: 00000007-VIDEO-2024-02-04-08-01-00.mp4>
[04/02/2024, 08:02:00] Ana: {LRM}Missed voice call, {LRM}Tap to call back
[04/02/2024, 08:03:00] Ben: {LRM}This message was deleted.
[04/02/2024, 08:04:00] Ben: Fixed it {LRM}<This message was edited>
[04/02/2024, 08:05:00] Ben: {LRM}Ben changed their phone number to a new number.
[04/02/2024, 08:06:00] ~{NNBSP}Cam: location: https://maps.example.com/?q=1,2
[04/02/2024, 08:07:00] Ana: {LRM}notes.pdf • {LRM}2 pages {LRM}document omitted
"""

ANDROID = f"""\
1/30/23, 8:12{NNBSP}PM - Messages and calls are end-to-end encrypted. Tap to learn more.
1/30/23, 8:13{NNBSP}PM - Ana: Hi
1/30/23, 11:59{NNBSP}PM - Ben: <Media omitted>
1/31/23, 12:05{NNBSP}AM - Ben: IMG-20230131-WA0001.jpg (file attached)
a caption
1/31/23, 12:06 AM - Ana: You deleted this message
1/31/23, 12:07 AM - Ana created group "Plans"
"""


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def parse(text: str, tz: str = "UTC") -> Conversation:
    return parse_chat(text, timezone=tz)


def kinds(conv: Conversation) -> list[str]:
    return conv.messages["kind"].cast(str).to_list()


def test_iphone_export() -> None:
    conv = parse(IPHONE)
    m = conv.messages
    assert conv.platform == "whatsapp"
    assert conv.participants == ("Ana", "Ben", "Cam")
    assert m["timestamp"][0] == utc(2024, 2, 3, 21, 15, 40)
    assert m["text"][1] == (
        "Hello: how are you?\nThis line continues the message.\n\nSo does this one."
    )
    assert kinds(conv) == [
        "text",
        "text",
        "photo",
        "video",
        "call",
        "unsent",
        "text",
        "share",
        "file",
    ]
    assert m["text"][6] == "Fixed it"
    assert m["text"].null_count() == 5  # media, call and deleted messages have no text


def test_android_export_with_12_hour_clock_and_month_first() -> None:
    conv = parse(ANDROID)
    assert conv.participants == ("Ana", "Ben")
    assert conv.messages["timestamp"].to_list() == [
        utc(2023, 1, 30, 20, 13),
        utc(2023, 1, 30, 23, 59),
        utc(2023, 1, 31, 0, 5),
        utc(2023, 1, 31, 0, 6),
    ]
    assert kinds(conv) == ["text", "other", "photo", "unsent"]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("30.01.23, 20:12 - Ana: Hallo", utc(2023, 1, 30, 20, 12)),  # German
        ("30/01/2023 20:12 - Ana: Hola", utc(2023, 1, 30, 20, 12)),  # no comma
        ("2023-01-30, 20:12 - Ana: Hej", utc(2023, 1, 30, 20, 12)),  # year first
        ("[30.01.23, 20:12:09] Ana: Hallo", utc(2023, 1, 30, 20, 12, 9)),
        ("30/1/23, 8:12 μ.μ. - Ana: Γειά", utc(2023, 1, 30, 20, 12)),  # Greek
        ("1/30/23, 8:12 p. m. - Ana: Hola", utc(2023, 1, 30, 20, 12)),  # Spanish
        ("[1/30/23, 12:01:00 AM] Ana: Hi", utc(2023, 1, 30, 0, 1)),
    ],
)
def test_date_formats(line: str, expected: datetime) -> None:
    assert parse(line).messages["timestamp"][0] == expected


@pytest.mark.parametrize(
    ("dates", "expected_month"),
    [
        # Neither part is ever above 12: the order that keeps the chat chronological wins.
        (["12/1/23", "1/2/23"], 1),  # 12 Jan, 1 Feb (as month first: 1 Dec, then 2 Jan)
        (["1/12/23", "2/1/23"], 1),  # 12 Jan, 1 Feb (as day first: 1 Dec, then 2 Jan)
    ],
)
def test_ambiguous_date_order(dates: list[str], expected_month: int) -> None:
    text = "".join(f"{d}, 10:00 - Ana: hi\n" for d in dates)
    stamps = parse(text).messages["timestamp"]
    assert stamps.is_sorted()
    assert stamps.dt.month()[0] == expected_month


def test_times_are_read_in_the_given_timezone() -> None:
    conv = parse("[01/02/2024, 12:00:00] Ana: hi\n[31/03/2024, 02:30:00] Ana: hi", "Europe/Vienna")
    # 12:00 in Vienna in winter is 11:00 UTC. 02:30 on 31 March doesn't exist there
    # (clocks jump to 03:00), so it is read as 03:30 summer time.
    assert conv.messages["timestamp"].to_list() == [
        utc(2024, 2, 1, 11, 0),
        utc(2024, 3, 31, 1, 30),
    ]
    assert conv.in_timezone("Europe/Vienna").messages["timestamp"].dt.hour()[0] == 12


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("just some notes", "No WhatsApp messages"),
        ("30/01/23, 8:12 xyz - Ana: hi", "Unrecognised time"),
        ("31/02/23, 8:12 - Ana: hi", "Invalid date"),
    ],
)
def test_bad_chats_raise_loader_error(text: str, match: str) -> None:
    with pytest.raises(loaders.LoaderError, match=match):
        parse(text)


@pytest.mark.parametrize(
    ("relative_path", "title"),
    [
        ("WhatsApp Chat with Ana.txt", "Ana"),  # Android
        ("WhatsApp Chat - Ana/_chat.txt", "Ana"),  # iPhone, unzipped
        ("ana/_chat.txt", "ana"),
        ("ana/my chat.txt", "my chat"),
    ],
)
def test_file_and_folder_layouts(tmp_path: Path, relative_path: str, title: str) -> None:
    file = tmp_path / relative_path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(IPHONE, encoding="utf-8")
    loader = WhatsAppLoader()
    for path in (file, file.parent):
        assert loader.can_load(path)
        conv = loaders.load(path, timezone="UTC")
        assert (conv.platform, conv.title, len(conv)) == ("whatsapp", title, 9)


def test_byte_order_mark_and_windows_line_endings(tmp_path: Path) -> None:
    file = tmp_path / "chat.txt"
    file.write_bytes(b"\xef\xbb\xbf" + ANDROID.replace("\n", "\r\n").encode("utf-8"))
    conv = WhatsAppLoader().load(file, timezone="UTC")
    assert conv.messages["text"][0] == "Hi"


def test_what_is_not_a_whatsapp_chat(tmp_path: Path) -> None:
    loader = WhatsAppLoader()
    notes = tmp_path / "notes.txt"
    notes.write_text("shopping list\nmilk\n", encoding="utf-8")
    assert not loader.can_load(notes)
    assert not loader.can_load(tmp_path)
    assert not loader.can_load(tmp_path / "missing.txt")
    with pytest.raises(loaders.LoaderError, match="No WhatsApp chat"):
        loader.load(tmp_path)
    (tmp_path / "bad.txt").write_bytes(b"30/01/23, 20:12 - Ana: \xff\xfe")
    with pytest.raises(loaders.LoaderError, match="not UTF-8"):
        loader.load(tmp_path / "bad.txt")


def test_folder_with_several_chats_is_ambiguous(tmp_path: Path) -> None:
    for name in ("WhatsApp Chat with Ana.txt", "WhatsApp Chat with Ben.txt"):
        (tmp_path / name).write_text(ANDROID, encoding="utf-8")
    with pytest.raises(loaders.LoaderError, match="several WhatsApp chats"):
        WhatsAppLoader().load(tmp_path)


def test_cli_lists_and_reports_chat_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "WhatsApp Chat with Ana.txt").write_text(IPHONE, encoding="utf-8")
    assert main(["list", "--sources", str(tmp_path)]) == 0
    assert "WhatsApp Chat with Ana.txt\t(whatsapp)" in capsys.readouterr().out
    code = main(["report", "WhatsApp Chat with Ana.txt", "--sources", str(tmp_path), "--tz", "UTC"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Conversation: Ana (whatsapp)" in out
    assert "Total messages: 9" in out
