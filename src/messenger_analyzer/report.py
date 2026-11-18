"""Full statistics report: built once as plain data, then rendered as text or JSON.

:func:`build_report` returns only JSON-serialisable values, so the same output can
feed the CLI today and a web front end later.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import polars as pl

from messenger_analyzer import analysis as an
from messenger_analyzer.schema import Conversation


def _records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    return [
        {k: v.isoformat() if isinstance(v, date | datetime) else v for k, v in row.items()}
        for row in frame.iter_rows(named=True)
    ]


def build_report(
    conversation: Conversation,
    *,
    top: int = 5,
    keywords: Sequence[str] = (),
    max_gap: timedelta | None = None,
) -> dict[str, Any]:
    m = conversation.messages
    first, last = (
        (m.get_column("timestamp").min(), m.get_column("timestamp").max())
        if len(m)
        else (None, None)
    )
    span_days = (last.date() - first.date()).days + 1 if first and last else 0  # type: ignore[union-attr]
    busiest_month = an.top_periods(m, "month", 1)
    frequencies = an.word_frequencies(m)

    report: dict[str, Any] = {
        "title": conversation.title,
        "platform": conversation.platform,
        "participants": list(conversation.participants),
        "total_messages": len(m),
        "first_message": first.isoformat() if first else None,  # type: ignore[union-attr]
        "last_message": last.isoformat() if last else None,  # type: ignore[union-attr]
        "span_days": span_days,
        "messages_per_sender": _records(an.messages_per_sender(m)),
        "top_days": _records(an.top_periods(m, "day", top)),
        "busiest_month": _records(busiest_month)[0] if len(busiest_month) else None,
        "response_time": {
            "max_gap_seconds": max_gap.total_seconds() if max_gap else None,
            "mean_seconds": an.mean_response_time(m, max_gap=max_gap),
            "per_sender": _records(an.mean_response_time_per_sender(m, max_gap=max_gap)),
        },
        "messages_per_weekday": _records(an.messages_per_weekday(m)),
        "words": {
            "mean_per_message": an.average_words(m),
            "per_sender": _records(an.average_words_per_sender(m)),
            "top": _records(frequencies.head(top)),
            "unique": frequencies.height,
        },
        "kinds": _records(an.kind_counts(m)),
        "kinds_per_sender": _records(an.kind_counts(m, by_sender=True)),
    }
    if keywords:
        report["keywords"] = _records(an.word_occurrences(m, keywords, frequencies=frequencies))
    return report


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = round(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _section(title: str, rows: list[str]) -> list[str]:
    return ["", title, *(f"  {row}" for row in rows)]


def _overview(report: dict[str, Any]) -> list[str]:
    first, last = report["first_message"], report["last_message"]
    days = report["span_days"]
    lines = [
        f"Conversation: {report['title']} ({report['platform']})",
        f"Participants: {', '.join(report['participants'])}",
        f"Span: {days} days ({days / 365:.2f} years), "
        f"{first[:10] if first else '?'} to {last[:10] if last else '?'}",
        f"Total messages: {report['total_messages']:,}",
    ]
    lines += _section(
        "Messages per participant:",
        [
            f"{r['sender']}: {r['messages']:,} ({r['share']:.1%})"
            for r in report["messages_per_sender"]
        ],
    )
    lines += _section(
        f"Top {len(report['top_days'])} days:",
        [f"{r['period']}: {r['messages']:,}" for r in report["top_days"]],
    )
    if bm := report["busiest_month"]:
        lines += ["", f"Busiest month: {bm['period'][:7]} with {bm['messages']:,} messages"]
    lines += _section(
        "Messages per weekday:",
        [f"{r['weekday']}: {r['messages']:,}" for r in report["messages_per_weekday"]],
    )
    return lines


def _responses(report: dict[str, Any]) -> list[str]:
    rt = report["response_time"]
    gap = rt["max_gap_seconds"]
    ignored = f" (gaps over {format_duration(gap)} ignored)" if gap else ""
    return _section(
        f"Average response time{ignored}: {format_duration(rt['mean_seconds'])}",
        [
            f"{r['sender']}: {format_duration(r['mean_seconds'])} over {r['responses']:,} responses"
            for r in rt["per_sender"]
        ],
    )


def _content(report: dict[str, Any]) -> list[str]:
    words = report["words"]
    by_sender: dict[str, list[str]] = {}
    for r in report["kinds_per_sender"]:
        if r["messages"]:
            by_sender.setdefault(r["sender"], []).append(f"{r['kind']} {r['messages']:,}")

    lines = _section(
        f"Average words per text message: {_num(words['mean_per_message'])}",
        [f"{r['sender']}: {_num(r['mean_words'])}" for r in words["per_sender"]],
    )
    lines += _section(
        "Message types:",
        [f"{r['kind']}: {r['messages']:,}" for r in report["kinds"] if r["messages"]],
    )
    lines += _section(
        "Message types per participant:", [f"{s}: {', '.join(p)}" for s, p in by_sender.items()]
    )
    lines += _section(
        f"Top {len(words['top'])} words:", [f"{r['word']}: {r['count']:,}" for r in words["top"]]
    )
    lines.append(f"Unique words: {words['unique']:,}")
    if "keywords" in report:
        lines += _section(
            "Keyword occurrences:", [f"{r['word']}: {r['count']:,}" for r in report["keywords"]]
        )
    return lines


def to_text(report: dict[str, Any]) -> str:
    """Human-readable rendering of :func:`build_report` output."""
    return "\n".join([*_overview(report), *_responses(report), *_content(report)]) + "\n"
