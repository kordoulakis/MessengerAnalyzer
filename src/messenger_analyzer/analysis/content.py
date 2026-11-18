"""What people send: message kinds and words.

Word statistics only use text messages; the automatic text attached to calls and
shares ("The video chat ended.") would otherwise skew them.
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from messenger_analyzer.analysis.activity import period_expr, period_range, senders
from messenger_analyzer.schema import MessageKind

#: A word is a run of letters/digits, optionally joined by apostrophes ("don't").
WORD_PATTERN = r"\w+(?:['’]\w+)*"

_WORD_COUNT = pl.col("text").str.count_matches(r"\S+").alias("words")


def text_messages(messages: pl.DataFrame) -> pl.DataFrame:
    return messages.filter(
        (pl.col("kind") == MessageKind.TEXT.value) & pl.col("text").is_not_null()
    )


def kind_counts(messages: pl.DataFrame, *, by_sender: bool = False) -> pl.DataFrame:
    """Columns: kind, messages (or sender, kind, messages). Every kind is listed, zero-filled."""
    kinds = pl.DataFrame(
        {"kind": [k.value for k in MessageKind]}, schema={"kind": messages.schema["kind"]}
    )
    keys = ["sender", "kind"] if by_sender else ["kind"]
    full = senders(messages).join(kinds, how="cross") if by_sender else kinds
    counts = messages.group_by(keys).len("messages")
    return full.join(counts, on=keys, how="left").with_columns(
        pl.col("messages").fill_null(0).cast(pl.Int64)
    )


def _collect(query: pl.LazyFrame) -> pl.DataFrame:
    # Regex work on text is the costliest thing we do; the streaming engine
    # splits it across all CPU cores (about 3-4x faster on a 4-core machine).
    return query.collect(engine="streaming")


def _text_stats(messages: pl.DataFrame, *keys: str | pl.Expr) -> pl.DataFrame:
    """Text-message count and mean words, grouped by ``keys`` (or overall)."""
    aggs = [pl.len().cast(pl.Int64).alias("text_messages"), _WORD_COUNT.mean().alias("mean_words")]
    query = text_messages(messages).lazy()
    return _collect(query.group_by(*keys).agg(aggs) if keys else query.select(aggs))


def average_words(messages: pl.DataFrame) -> float | None:
    """Mean words per text message; None if there are no text messages."""
    value = _text_stats(messages)["mean_words"].item()
    return None if value is None else float(value)


def average_words_per_sender(messages: pl.DataFrame) -> pl.DataFrame:
    """Columns: sender, text_messages, mean_words (null for someone with no text)."""
    return (
        senders(messages)
        .join(_text_stats(messages, "sender"), on="sender", how="left")
        .with_columns(pl.col("text_messages").fill_null(0))
    )


def average_words_per_month(messages: pl.DataFrame, *, by_sender: bool = False) -> pl.DataFrame:
    """Columns: period (first of month), [sender], text_messages, mean_words.

    Every month is listed; months without text messages have a null mean.
    """
    keys = ["period", "sender"] if by_sender else ["period"]
    full = period_range(messages, "month")
    if by_sender:
        full = full.join(senders(messages), how="cross")
    return (
        full.join(_text_stats(messages, period_expr("month"), *keys[1:]), on=keys, how="left")
        .with_columns(pl.col("text_messages").fill_null(0))
        .sort(keys, maintain_order=True)
    )


def word_frequencies(messages: pl.DataFrame, *, case_sensitive: bool = False) -> pl.DataFrame:
    """Columns: word, count. Every distinct word, most frequent first, ties alphabetical.

    Tokenising is the expensive part of word statistics; when you need several of
    them, compute this once and derive the rest (see :func:`word_occurrences`).
    """
    text = pl.col("text") if case_sensitive else pl.col("text").str.to_lowercase()
    query = (
        text_messages(messages)
        .lazy()
        .select(text.str.extract_all(WORD_PATTERN).explode().alias("word"))
        .drop_nulls()
        .group_by("word")
        .agg(pl.len().cast(pl.Int64).alias("count"))
    )
    return _collect(query).sort(["count", "word"], descending=[True, False])


def top_words(messages: pl.DataFrame, n: int = 10, *, case_sensitive: bool = False) -> pl.DataFrame:
    """Columns: word, count. The ``n`` most frequent words."""
    return word_frequencies(messages, case_sensitive=case_sensitive).head(n)


def unique_word_count(messages: pl.DataFrame, *, case_sensitive: bool = False) -> int:
    return word_frequencies(messages, case_sensitive=case_sensitive).height


def word_occurrences(
    messages: pl.DataFrame,
    words: Iterable[str],
    *,
    case_sensitive: bool = False,
    frequencies: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Columns: word, count. How many times each word appears in total.

    Pass ``frequencies`` from :func:`word_frequencies` to avoid re-tokenising.
    """
    if frequencies is None:
        frequencies = word_frequencies(messages, case_sensitive=case_sensitive)
    wanted = [w if case_sensitive else w.lower() for w in words]
    return (
        pl.DataFrame({"word": wanted}, schema={"word": pl.String})
        .join(frequencies, on="word", how="left", maintain_order="left")
        .with_columns(pl.col("count").fill_null(0))
    )
