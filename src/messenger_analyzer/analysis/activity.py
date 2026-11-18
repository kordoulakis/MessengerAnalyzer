"""When and how much people talk."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

import polars as pl

Period = Literal["day", "month"]

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

_INTERVAL: dict[Period, str] = {"day": "1d", "month": "1mo"}


def period_expr(period: Period) -> pl.Expr:
    """Calendar date of the day or first day of the month, in the frame's timezone."""
    ts = pl.col("timestamp")
    expr = ts.dt.date() if period == "day" else ts.dt.truncate("1mo").dt.date()
    return expr.alias("period")


def period_range(messages: pl.DataFrame, period: Period) -> pl.DataFrame:
    """Every day or month from the first message to the last, so gaps show as zero."""
    bounds = messages.select(
        period_expr(period).min().alias("start"), period_expr(period).max().alias("end")
    ).row(0)
    if bounds[0] is None:
        return pl.DataFrame(schema={"period": pl.Date})
    dates = pl.date_range(bounds[0], bounds[1], _INTERVAL[period], eager=True)
    return pl.DataFrame({"period": dates})


def senders(messages: pl.DataFrame) -> pl.DataFrame:
    """Senders in order of their first message."""
    return messages.select(pl.col("sender").unique(maintain_order=True))


def messages_per_sender(messages: pl.DataFrame) -> pl.DataFrame:
    """Columns: sender, messages, share (fraction of all messages). Most active first."""
    total = max(messages.height, 1)
    return (
        messages.group_by("sender", maintain_order=True)
        .len("messages")
        .with_columns(
            pl.col("messages").cast(pl.Int64), (pl.col("messages") / total).alias("share")
        )
        .sort("messages", descending=True, maintain_order=True)
    )


def messages_per_period(
    messages: pl.DataFrame,
    period: Period = "day",
    *,
    by_sender: bool = False,
    span: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Message counts for every day or month, zero-filled.

    Columns: ``period, messages``, or ``period, sender, messages`` with ``by_sender``.
    ``span`` is the frame whose date range and senders to cover; defaults to
    ``messages``. Pass the full conversation when ``messages`` is a filtered subset.
    """
    span = messages if span is None else span
    full = period_range(span, period)
    keys = ["period", "sender"] if by_sender else ["period"]
    if by_sender:
        full = full.join(senders(span), how="cross")
    counts = messages.group_by(period_expr(period), *keys[1:]).len("messages")
    return (
        full.join(counts, on=keys, how="left")
        .with_columns(pl.col("messages").fill_null(0).cast(pl.Int64))
        .sort(keys, maintain_order=True)
    )


def messages_per_weekday(messages: pl.DataFrame) -> pl.DataFrame:
    """Columns: weekday (name), messages. Monday first."""
    counts = messages.group_by(pl.col("timestamp").dt.weekday().alias("n")).len("messages")
    full = pl.DataFrame({"n": pl.int_range(1, 8, dtype=pl.Int8, eager=True), "weekday": WEEKDAYS})
    return (
        full.join(counts.with_columns(pl.col("n").cast(pl.Int8)), on="n", how="left")
        .sort("n")
        .select("weekday", pl.col("messages").fill_null(0).cast(pl.Int64))
    )


def messages_per_hour(messages: pl.DataFrame) -> pl.DataFrame:
    """Columns: hour (0-23), messages."""
    counts = messages.group_by(pl.col("timestamp").dt.hour().cast(pl.Int8).alias("hour")).len(
        "messages"
    )
    full = pl.DataFrame({"hour": pl.int_range(0, 24, dtype=pl.Int8, eager=True)})
    return (
        full.join(counts, on="hour", how="left")
        .sort("hour")
        .with_columns(pl.col("messages").fill_null(0).cast(pl.Int64))
    )


def top_periods(messages: pl.DataFrame, period: Period = "day", n: int = 5) -> pl.DataFrame:
    """The ``n`` busiest days or months. Ties go to the earlier date."""
    return (
        messages_per_period(messages, period)
        .sort(["messages", "period"], descending=[True, False])
        .head(n)
    )


def keyword_pattern(keywords: Iterable[str], *, case_sensitive: bool = False) -> str:
    """Regex matching any of ``keywords`` as a whole word."""
    words = [re.escape(k.strip()) for k in keywords if k.strip()]
    if not words:
        raise ValueError("At least one non-empty keyword is required")
    flags = "" if case_sensitive else "(?i)"
    return rf"{flags}\b(?:{'|'.join(words)})\b"


def filter_keywords(
    messages: pl.DataFrame, keywords: Iterable[str], *, case_sensitive: bool = False
) -> pl.DataFrame:
    """Only the messages whose text contains at least one of ``keywords``."""
    pattern = keyword_pattern(keywords, case_sensitive=case_sensitive)
    return messages.filter(pl.col("text").str.contains(pattern).fill_null(False))
