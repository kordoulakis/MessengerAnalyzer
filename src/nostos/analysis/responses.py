"""How quickly people answer each other.

A *response* is any message whose sender differs from the previous message's
sender; its response time is the gap between the two. This cannot tell a reply
from someone restarting the conversation days later, so ``max_gap`` lets callers
ignore gaps longer than a threshold. Medians are reported next to means because
a few overnight gaps can dominate a mean.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from nostos.analysis.activity import period_expr, period_range, senders

UNITS: dict[str, float] = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0}

#: Upper bounds (inclusive, seconds) and labels for :func:`response_time_distribution`.
BUCKETS: tuple[tuple[float, str], ...] = (
    (60, "≤ 1 min"),
    (5 * 60, "1–5 min"),
    (15 * 60, "5–15 min"),
    (60 * 60, "15–60 min"),
    (6 * 3600, "1–6 h"),
    (24 * 3600, "6–24 h"),
    (float("inf"), "> 1 day"),
)
BUCKET_DTYPE = pl.Enum([label for _, label in BUCKETS])

_STATS = (
    pl.len().cast(pl.Int64).alias("responses"),
    pl.col("seconds").mean().alias("mean_seconds"),
    pl.col("seconds").median().alias("median_seconds"),
)


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


def response_time_summary(
    messages: pl.DataFrame, *, max_gap: timedelta | None = None
) -> dict[str, float | int | None]:
    """``responses``, ``mean_seconds`` and ``median_seconds`` for the whole conversation."""
    row = response_times(messages, max_gap=max_gap).select(_STATS).row(0, named=True)
    return {k: (float(v) if isinstance(v, float) else v) for k, v in row.items()}


def mean_response_time(messages: pl.DataFrame, *, max_gap: timedelta | None = None) -> float | None:
    """Mean seconds per response; None if nobody responded."""
    value = response_time_summary(messages, max_gap=max_gap)["mean_seconds"]
    return None if value is None else float(value)


def response_time_per_sender(
    messages: pl.DataFrame, *, max_gap: timedelta | None = None
) -> pl.DataFrame:
    """Columns: sender, responses, mean_seconds, median_seconds (null if they never responded)."""
    stats = response_times(messages, max_gap=max_gap).group_by("sender").agg(_STATS)
    return (
        senders(messages)
        .join(stats, on="sender", how="left")
        .with_columns(pl.col("responses").fill_null(0))
    )


def response_time_per_month(
    messages: pl.DataFrame, *, by_sender: bool = False, max_gap: timedelta | None = None
) -> pl.DataFrame:
    """Columns: period, [sender], responses, mean_seconds, median_seconds.

    Every month is listed; months without responses have null times.
    """
    keys = ["period", "sender"] if by_sender else ["period"]
    full = period_range(messages, "month")
    if by_sender:
        full = full.join(senders(messages), how="cross")
    stats = (
        response_times(messages, max_gap=max_gap)
        .group_by(period_expr("month"), *keys[1:])
        .agg(_STATS)
    )
    return (
        full.join(stats, on=keys, how="left")
        .with_columns(pl.col("responses").fill_null(0))
        .sort(keys, maintain_order=True)
    )


def response_time_distribution(
    messages: pl.DataFrame, *, by_sender: bool = False, max_gap: timedelta | None = None
) -> pl.DataFrame:
    """Columns: bucket, [sender], responses, share.

    ``share`` is the fraction of all responses (or of that sender's responses)
    falling in the bucket. Every bucket is listed, zero-filled, fastest first.
    """
    keys = ["sender", "bucket"] if by_sender else ["bucket"]
    labels = [label for _, label in BUCKETS]
    bucket: pl.Expr = pl.lit(labels[-1])
    for upper, label in reversed(BUCKETS[:-1]):
        bucket = pl.when(pl.col("seconds") <= upper).then(pl.lit(label)).otherwise(bucket)
    bucket = bucket.cast(BUCKET_DTYPE)
    counts = (
        response_times(messages, max_gap=max_gap)
        .group_by(*keys[:-1], bucket.alias("bucket"))
        .len("responses")
    )
    full = pl.DataFrame({"bucket": labels}, schema={"bucket": BUCKET_DTYPE})
    if by_sender:
        full = senders(messages).join(full, how="cross")
    result = full.join(counts, on=keys, how="left").with_columns(
        pl.col("responses").fill_null(0).cast(pl.Int64)
    )
    total = pl.col("responses").sum()
    if by_sender:
        total = total.over("sender")
    return result.with_columns(
        pl.when(total > 0).then(pl.col("responses") / total).otherwise(0.0).alias("share")
    )
