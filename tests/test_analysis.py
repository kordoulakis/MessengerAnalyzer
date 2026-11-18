from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from messenger_analyzer import analysis as an
from messenger_analyzer.schema import Conversation


@pytest.fixture
def m(conversation: Conversation) -> pl.DataFrame:
    return conversation.messages


def test_messages_per_sender(m: pl.DataFrame) -> None:
    result = an.messages_per_sender(m)
    assert result.select("sender", "messages").rows() == [("Βασίλης", 4), ("Ana", 3), ("Cam", 1)]
    assert result["share"].sum() == pytest.approx(1.0)


def test_messages_per_day_is_zero_filled(m: pl.DataFrame) -> None:
    result = an.messages_per_period(m, "day")
    assert result["period"][0] == date(2020, 1, 1)
    assert result["period"][-1] == date(2020, 2, 2)
    assert result.height == 33
    assert result["messages"].sum() == 8
    assert result.filter(pl.col("period") == date(2020, 1, 2))["messages"].item() == 0


def test_messages_per_month_by_sender(m: pl.DataFrame) -> None:
    result = an.messages_per_period(m, "month", by_sender=True)
    assert result.height == 6  # 2 months x 3 senders, zero-filled
    feb_cam = result.filter((pl.col("period") == date(2020, 2, 1)) & (pl.col("sender") == "Cam"))
    assert feb_cam["messages"].item() == 1


def test_weekday_and_hour(m: pl.DataFrame) -> None:
    weekdays = an.messages_per_weekday(m)
    assert weekdays["weekday"].to_list() == list(an.WEEKDAYS)
    assert weekdays["messages"].sum() == 8
    # 2020-01-01 was a Wednesday: three messages
    assert weekdays.filter(pl.col("weekday") == "Wednesday")["messages"].item() == 3
    hours = an.messages_per_hour(m)
    assert hours.height == 24
    assert hours.filter(pl.col("hour") == 8)["messages"].item() == 4


def test_top_days(m: pl.DataFrame) -> None:
    assert an.top_periods(m, "day", 2).rows() == [(date(2020, 1, 1), 3), (date(2020, 2, 1), 3)]
    assert an.top_periods(m, "day", 100).height == 33  # never None when n > days


def test_keywords_are_whole_word_and_case_insensitive(m: pl.DataFrame) -> None:
    assert an.filter_keywords(m, ["HELLO"]).height == 2  # "hello hello", "Hello, world."
    assert an.filter_keywords(m, ["hello"], case_sensitive=True).height == 1
    assert an.filter_keywords(m, ["hell"]).height == 0
    with pytest.raises(ValueError, match="keyword"):
        an.filter_keywords(m, [" "])


def test_keyword_counts_cover_full_range(m: pl.DataFrame) -> None:
    hits = an.filter_keywords(m, ["photo-never-mentioned"])
    assert an.messages_per_period(hits, "day", span=m).height == 33


def test_response_times(m: pl.DataFrame) -> None:
    rt = an.response_times(m)
    # Senders in order: Ana, Β, Β, Ana, Ana, Β, Β, Cam -> responses at indices 1, 3, 5, 7
    assert rt.height == 4
    assert rt["seconds"][0] == 60
    assert rt["seconds"][2] == 300
    per_sender = dict(an.mean_response_time_per_sender(m).select("sender", "responses").rows())
    assert per_sender == {"Ana": 1, "Βασίλης": 2, "Cam": 1}


def test_max_gap_drops_conversation_restarts(m: pl.DataFrame) -> None:
    rt = an.response_times(m, max_gap=timedelta(hours=1))
    assert rt["seconds"].to_list() == [60.0, 300.0]
    assert an.mean_response_time(m, max_gap=timedelta(hours=1)) == 180.0


def test_no_division_by_zero_with_single_sender(m: pl.DataFrame) -> None:
    solo = m.filter(pl.col("sender") == "Cam")
    assert an.mean_response_time(solo) is None
    assert an.mean_response_time_per_sender(solo)["mean_seconds"].to_list() == [None]
    assert an.average_words(solo) is None
    assert an.average_words_per_sender(solo)["mean_words"].to_list() == [None]


def test_average_words_per_month_is_per_month(m: pl.DataFrame) -> None:
    # Jan: 4 + 1 + 2 + 2 words over 4 text messages; Feb: one text message of 2 words.
    result = an.average_words_per_month(m)
    assert result["mean_words"].to_list() == [2.25, 2.0]
    assert result["text_messages"].to_list() == [4, 1]


def test_average_words(m: pl.DataFrame) -> None:
    assert an.average_words(m) == pytest.approx(11 / 5)
    per_sender = dict(an.average_words_per_sender(m).select("sender", "mean_words").rows())
    assert per_sender == {"Ana": pytest.approx(8 / 3), "Βασίλης": 1.5, "Cam": None}


def test_kind_counts(m: pl.DataFrame) -> None:
    counts = dict(an.kind_counts(m).with_columns(pl.col("kind").cast(str)).rows())
    assert counts["text"] == 5
    assert counts["photo"] == 2
    assert counts["call"] == 1
    assert counts["gif"] == 0
    per_sender = an.kind_counts(m, by_sender=True)
    assert per_sender.filter(pl.col("sender") == "Cam")["messages"].sum() == 1


def test_words(m: pl.DataFrame) -> None:
    top = an.top_words(m, 2)
    assert top.rows() == [("hello", 3), ("a", 1)]
    assert an.unique_word_count(m) == 9
    occurrences = dict(an.word_occurrences(m, ["Hello", "missing"]).rows())
    assert occurrences == {"hello": 3, "missing": 0}


def test_empty_frame_is_handled(m: pl.DataFrame) -> None:
    empty = m.clear()
    assert an.messages_per_period(empty, "day").height == 0
    assert an.top_words(empty).height == 0
    assert an.mean_response_time(empty) is None
