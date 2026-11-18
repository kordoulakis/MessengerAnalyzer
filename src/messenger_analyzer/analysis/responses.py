"""How quickly people answer each other.

A *response* is any message whose sender differs from the previous message's
sender; its response time is the gap between the two. This cannot tell a reply
from someone restarting the conversation days later, so ``max_gap`` lets callers
ignore gaps longer than a threshold.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from messenger_analyzer.analysis.activity import period_expr, period_range, senders

UNITS: dict[str, float] = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0}


def response_times(messages: pl.DataFrame, *, max_gap: timedelta | None = None) -> pl.DataFrame:
    """Columns: timestamp (of the response), sender (who responded), seconds."""
    prev_sender = pl.col("sender").shift(1)
    gap = (pl.col("timestamp") - pl.col("timestamp").shift(1)).dt.total_milliseconds() / 1000
    result = messages.select(
        "timestamp", "sender", gap.alias("seconds"), prev_sender.alias("prev")
    ).filter(pl.col("prev").is_not_null() & (pl.col("sender") != pl.col("prev")))
    if max_gap is not None:
        result = result.filter(pl.col("seconds") <= max_gap.total_seconds())
    return result.drop("prev")


def mean_response_time(messages: pl.DataFrame, *, max_gap: timedelta | None = None) -> float | None:
    """Mean seconds per response across the whole conversation; None if nobody responded."""
    value = response_times(messages, max_gap=max_gap).get_column("seconds").mean()
    return None if value is None else float(value)  # type: ignore[arg-type]


def mean_response_time_per_sender(
    messages: pl.DataFrame, *, max_gap: timedelta | None = None
) -> pl.DataFrame:
    """Columns: sender, responses, mean_seconds (null for someone who never responded)."""
    stats = (
        response_times(messages, max_gap=max_gap)
        .group_by("sender")
        .agg(
            pl.len().cast(pl.Int64).alias("responses"),
            pl.col("seconds").mean().alias("mean_seconds"),
        )
    )
    return (
        senders(messages)
        .join(stats, on="sender", how="left")
        .with_columns(pl.col("responses").fill_null(0))
    )


def mean_response_time_per_month(
    messages: pl.DataFrame, *, max_gap: timedelta | None = None
) -> pl.DataFrame:
    """Columns: period (first of month), responses, mean_seconds (null for silent months)."""
    stats = (
        response_times(messages, max_gap=max_gap)
        .group_by(period_expr("month"))
        .agg(
            pl.len().cast(pl.Int64).alias("responses"),
            pl.col("seconds").mean().alias("mean_seconds"),
        )
    )
    return (
        period_range(messages, "month")
        .join(stats, on="period", how="left")
        .with_columns(pl.col("responses").fill_null(0))
        .sort("period")
    )
