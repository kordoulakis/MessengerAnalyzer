"""Messenger writes each UTF-8 byte as its own character; the loader must undo that
for every language, not just Greek."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from messenger_analyzer import analysis as an
from messenger_analyzer.loaders.messenger import MessengerLoader, fix_mojibake

from .conftest import mangle, ms, write_export

SAMPLES = {
    "english": "plain english, nothing to fix",
    "french": "café crème à la française",
    "german": "Grüße aus Köln, Straße",
    "greek": "Γειά σου, τι κάνεις;",
    "russian": "Привет, как дела?",
    "chinese": "你好世界",
    "japanese": "こんにちは、元気ですか",
    "korean": "안녕하세요",
    "arabic": "مرحبا بالعالم",
    "hebrew": "שלום עולם",
    "hindi": "नमस्ते दुनिया",
    "thai": "สวัสดีชาวโลก",
    "emoji": "😂❤️👍🏽 👨‍👩‍👧",
    "mixed": "naïve 😂 Ελλάδα Москва 東京",
}


@pytest.mark.parametrize("text", SAMPLES.values(), ids=SAMPLES.keys())
def test_mangled_text_is_restored(text: str) -> None:
    assert fix_mojibake(mangle(text)) == text


@pytest.mark.parametrize("text", SAMPLES.values(), ids=SAMPLES.keys())
def test_correct_text_is_left_alone(text: str) -> None:
    assert fix_mojibake(text) == text


def test_ascii_is_unchanged_by_the_bug() -> None:
    assert mangle(SAMPLES["english"]) == SAMPLES["english"]


def test_mojibake_that_is_not_valid_utf8_is_left_alone() -> None:
    # Latin-1 encodable but not a valid UTF-8 byte sequence once re-encoded.
    assert fix_mojibake("Ã") == "Ã"


@pytest.fixture
def multilingual(tmp_path: Path) -> pl.DataFrame:
    senders = ["Βασίλης", "Дмитрий", "李雷", "José"]
    messages = [
        {
            "sender_name": senders[i % len(senders)],
            "timestamp_ms": ms(2022, 3, 1, 9, i),
            "content": text,
        }
        for i, text in enumerate(SAMPLES.values())
    ]
    folder = write_export(tmp_path / "intl", [list(reversed(messages))], title="Διεθνές 🌍")
    conversation = MessengerLoader().load(folder)
    assert conversation.title == "Διεθνές 🌍"
    assert conversation.participants == tuple(senders)
    return conversation.messages


def test_loader_restores_every_language(multilingual: pl.DataFrame) -> None:
    assert multilingual["text"].to_list() == list(SAMPLES.values())


def test_keywords_match_in_any_script(multilingual: pl.DataFrame) -> None:
    for word in ["Привет", "привет", "ΓΕΙΆ", "café", "Straße", "안녕하세요"]:
        assert an.filter_keywords(multilingual, [word]).height == 1, word


def test_word_statistics_handle_non_latin_scripts(multilingual: pl.DataFrame) -> None:
    words = set(an.word_frequencies(multilingual)["word"].to_list())
    # Lower-casing works beyond ASCII, and accented letters stay inside their word.
    assert {"γειά", "привет", "москва", "café", "grüße", "straße", "naïve"} <= words
    # Scripts without spaces count as a single run of letters.
    assert "你好世界" in words
    # Emoji are not words, but still count towards message length.
    assert not any("😂" in w for w in words)
    emoji_row = multilingual.filter(pl.col("text") == SAMPLES["emoji"])
    assert an.average_words(emoji_row) == 2.0


def test_report_json_keeps_unicode(multilingual: pl.DataFrame, tmp_path: Path) -> None:
    from messenger_analyzer.cli import main

    out = tmp_path / "r.json"
    assert main(["report", str(tmp_path / "intl"), "--format", "json", "-o", str(out)]) == 0
    raw = out.read_text(encoding="utf-8")
    assert "Βασίλης" in raw
    assert "\\u" not in raw  # written as real characters, not escapes
