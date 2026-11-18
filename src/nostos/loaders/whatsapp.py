"""WhatsApp "Export chat" text file, from Android or iPhone, in any date format.

Every message starts with a line like one of these (iPhone, then Android)::

    [30/01/2023, 20:12:10] Alex: Hello
    30/01/2023, 20:12 - Alex: Hello
    1/30/23, 8:12 PM - Alex: Hello

and any line that doesn't continues the previous message. The phone's region
decides the date format: day/month or month/day order is worked out from the
whole file. Times are the phone's local time with no timezone, so they are read
in the timezone the loader is given.

Media placeholders, calls, deleted messages and system notices are recognised in
WhatsApp's English wording. In other languages they are counted as text.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import polars as pl

from nostos.loaders.base import LoaderError, local_timezone
from nostos.schema import KIND_DTYPE, Conversation, MessageKind

_DATE = r"(?P<date>\d{1,4}[./-]\d{1,2}[./-]\d{1,4})\.?"
_TIME = r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
_IPHONE_HEADER = re.compile(rf"\[{_DATE},?\s{_TIME}(?P<ampm>[^\]]{{0,12}})\]\s(?P<body>.*)")
_ANDROID_HEADER = re.compile(rf"{_DATE},?\s{_TIME}(?P<ampm>[^-–]{{0,12}}?)\s[-–]\s(?P<body>.*)")

# Lower-cased, without dots or spaces. Covers the languages WhatsApp most often
# writes 12-hour times in; an unknown marker is reported rather than guessed.
_AM = frozenset({"am", "a", "πμ", "vorm", "vm", "午前", "上午", "오전", "ص"})
_PM = frozenset({"pm", "p", "μμ", "nachm", "nm", "午後", "下午", "오후", "م"})

# Direction marks WhatsApp puts around names, numbers and system text.
_INVISIBLE = str.maketrans(
    dict.fromkeys(
        map(chr, (0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A), 0xFEFF))
    )
)
# On iPhone, system notices and media placeholders start with a left-to-right mark.
_MARK = "\u200e"

_TEXT, _OTHER = MessageKind.TEXT.value, MessageKind.OTHER.value
_EDITED = re.compile(r"\s*<this message was edited>\s*$", re.IGNORECASE)
_SYSTEM = re.compile(
    r"^(?:messages (?:and calls |to this (?:chat|group) (?:and calls )?)are (?:now )?"
    r"(?:end-to-end encrypted|secured)|your security code with )"
)
_DELETED = frozenset({"this message was deleted", "you deleted this message"})
_ATTACHED = re.compile(r"^<attached: (?P<a>[^>]+)>|^(?P<b>\S[^\n]*?) \(file attached\)")
_OMITTED = re.compile(r"(?:^|\s)(image|video|audio|sticker|gif|document|contact card) omitted$")
_OMITTED_KINDS = {
    "image": MessageKind.PHOTO,
    "video": MessageKind.VIDEO,
    "audio": MessageKind.AUDIO,
    "sticker": MessageKind.STICKER,
    "gif": MessageKind.GIF,
    "document": MessageKind.FILE,
    "contact card": MessageKind.SHARE,
}
# Attachment file names: iPhone "00000012-PHOTO-2023-02-01-12-19-50.jpg",
# Android "IMG-20230201-WA0001.jpg".
_FILE_KINDS = (
    (re.compile(r"-sticker-|^stk-|\.webp$"), MessageKind.STICKER),
    (re.compile(r"-gif-|\.gif$"), MessageKind.GIF),
    (re.compile(r"-photo-|^img-|\.(?:jpe?g|png|heic)$"), MessageKind.PHOTO),
    (re.compile(r"-video-|^vid-|\.(?:mp4|mov|3gp)$"), MessageKind.VIDEO),
    (re.compile(r"-audio-|^ptt-|^aud-|\.(?:opus|m4a|mp3|aac|ogg)$"), MessageKind.AUDIO),
)
_CALL = re.compile(
    r"^(?:missed )?(?:group )?(?:voice|video) call"
    r"(?:, .*(?:sec|min|hr|call back|join|answer|device).*)?$"
)
_SHARE = re.compile(r"^(?:location: https?://|live location shared)")

_TITLE = re.compile(r"^WhatsApp Chat (?:with|-) (?P<name>.+)$", re.IGNORECASE)
_SNIFF_BYTES = 4096


def _header(line: str) -> re.Match[str] | None:
    line = line.lstrip(_MARK + "\ufeff")
    pattern = _IPHONE_HEADER if line.startswith("[") else _ANDROID_HEADER
    return pattern.fullmatch(line)


def _is_chat_file(file: Path) -> bool:
    if file.suffix.lower() != ".txt" or not file.is_file():
        return False
    with file.open("rb") as handle:
        head = handle.read(_SNIFF_BYTES).decode("utf-8", errors="replace")
    lines = [line for line in head.splitlines()[:20] if line.strip()]
    return any(_header(line) for line in lines)


def chat_files(path: Path) -> list[Path]:
    """WhatsApp chat files at ``path``: the file itself, or the ones in a folder."""
    if path.is_file():
        return [path] if _is_chat_file(path) else []
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.txt") if _is_chat_file(p))


def _title(file: Path) -> str:
    for name in (file.stem, file.parent.name):
        if match := _TITLE.match(name):
            return match["name"].strip()
    return file.parent.name if file.stem == "_chat" else file.stem


def _date_order(parts: Sequence[tuple[str, str, str]]) -> str:
    """``"ymd"``, ``"dmy"`` or ``"mdy"`` for the date strings of one file."""
    if len(parts[0][0]) == 4:
        return "ymd"
    numbers = [(int(a), int(b), int(c)) for a, b, c in parts]
    if any(a > 12 for a, _, _ in numbers):
        return "dmy"
    if any(b > 12 for _, b, _ in numbers):
        return "mdy"
    # Every day so far is 12 or less: pick the order that keeps the chat in
    # chronological order, as WhatsApp writes it. Ties go to day first, the
    # more common order worldwide.
    dmy = [(c, b, a) for a, b, c in numbers]
    mdy = [(c, a, b) for a, b, c in numbers]
    backwards = {
        order: sum(later < earlier for earlier, later in pairwise(keys))
        for order, keys in (("dmy", dmy), ("mdy", mdy))
    }
    return "mdy" if backwards["mdy"] < backwards["dmy"] else "dmy"


def _hour(hour: int, marker: str, line: str) -> int:
    marker = re.sub(r"[\s.]", "", marker).lower()
    if not marker:
        return hour
    if marker in _AM:
        return hour % 12
    if marker in _PM:
        return hour % 12 + 12
    raise LoaderError(f"Unrecognised time format in line: {line!r:.120}")


def _file_kind(name: str) -> MessageKind:
    name = name.strip().lower()
    for pattern, kind in _FILE_KINDS:
        if pattern.search(name):
            return kind
    return MessageKind.FILE


def _classify(body: str) -> tuple[str, str | None] | None:  # noqa: PLR0911
    """The kind and text of a message body, or None for a system notice."""
    marked = body.startswith(_MARK)
    text = _EDITED.sub("", body.translate(_INVISIBLE)).strip()
    low = text.lower()
    if not text:
        return _OTHER, None
    if _SYSTEM.match(low):
        return None
    if low.rstrip(".") in _DELETED:
        return MessageKind.UNSENT.value, None
    if low == "<media omitted>":
        return _OTHER, None
    if match := _ATTACHED.match(text):
        return _file_kind(match["a"] or match["b"]).value, None
    if "\n" not in low and (match := _OMITTED.search(low)):
        return _OMITTED_KINDS[match[1]].value, None
    if _CALL.match(low):
        return MessageKind.CALL.value, None
    if _SHARE.match(low):
        return MessageKind.SHARE.value, text
    if marked:  # group changes, security notices and the like
        return None
    return _TEXT, text


def parse_chat(text: str, *, timezone: str, title: str = "WhatsApp chat") -> Conversation:
    """Parse the contents of an exported chat file."""
    headers: list[re.Match[str]] = []
    bodies: list[list[str]] = []
    for raw_line in text.split("\n"):
        line = raw_line.removesuffix("\r")
        if match := _header(line):
            headers.append(match)
            bodies.append([match["body"]])
        elif bodies:
            bodies[-1].append(line)
    if not headers:
        raise LoaderError(
            "No WhatsApp messages found: expected lines like '30/01/2023, 20:12 - Alex: Hi'"
        )

    dates: list[tuple[str, str, str]] = []
    for match in headers:
        a, b, c = re.split(r"[./-]", match["date"])
        dates.append((a, b, c))
    order = _date_order(dates)
    stamps: list[datetime] = []
    senders: list[str] = []
    texts: list[str | None] = []
    kinds: list[str] = []
    for match, (a, b, c), body_lines in zip(headers, dates, bodies, strict=True):
        sender, separator, body = "\n".join(body_lines).partition(": ")
        if not separator:
            continue  # Android system notice: no sender
        classified = _classify(body)
        if classified is None:
            continue
        year, month, day = {
            "ymd": (a, b, c),
            "dmy": (c, b, a),
            "mdy": (c, a, b),
        }[order]
        hour, minute, *second = (int(x) for x in re.split(r"[:.]", match["time"]))
        try:
            stamp = datetime(
                int(year) + (2000 if len(year) <= 2 else 0),
                int(month),
                int(day),
                _hour(hour, match["ampm"], match.string),
                minute,
                second[0] if second else 0,
            )
        except ValueError as exc:
            raise LoaderError(f"Invalid date in line {match.string!r:.120}: {exc}") from exc
        stamps.append(stamp)
        senders.append(sender.translate(_INVISIBLE).strip().lstrip("~").strip())
        texts.append(classified[1])
        kinds.append(classified[0])

    naive = pl.Series(stamps, dtype=pl.Datetime("ms"))
    local = naive.dt.replace_time_zone(timezone, ambiguous="earliest", non_existent="null")
    # A time skipped by a daylight-saving change can only come from a phone set to
    # another timezone; read it an hour later rather than lose the message.
    later = (naive + timedelta(hours=1)).dt.replace_time_zone(
        timezone, ambiguous="earliest", non_existent="null"
    )
    frame = pl.DataFrame(
        {
            "timestamp": local.fill_null(later).dt.convert_time_zone("UTC"),
            "sender": pl.Series(senders, dtype=pl.String),
            "text": pl.Series(texts, dtype=pl.String),
            "kind": pl.Series(kinds, dtype=KIND_DTYPE),
        }
    )
    return Conversation.from_frame(frame, title=title, platform=WhatsAppLoader.name)


class WhatsAppLoader:
    name = "whatsapp"

    def can_load(self, path: Path) -> bool:
        return bool(chat_files(path))

    def load(self, path: Path, *, timezone: str | None = None) -> Conversation:
        files = chat_files(path)
        if not files:
            raise LoaderError(f"No WhatsApp chat (.txt) found at {path}")
        if len(files) > 1:
            names = ", ".join(f.name for f in files)
            raise LoaderError(f"{path} holds several WhatsApp chats ({names}): point at one file.")
        file = files[0]
        try:
            text = file.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise LoaderError(f"{file} is not UTF-8 text: {exc}") from exc
        return parse_chat(text, timezone=timezone or local_timezone(), title=_title(file))
