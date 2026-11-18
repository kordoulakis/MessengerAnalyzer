"""Matplotlib charts.

Each chart draws onto a caller-supplied :class:`~matplotlib.figure.Figure`, so it
works headless (save to file) or interactively (pyplot window) without global
pyplot state. matplotlib is an optional dependency: ``pip install .[plot]``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, cast

import numpy as np
import polars as pl

from messenger_analyzer import analysis as an
from messenger_analyzer.schema import Conversation

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.projections.polar import PolarAxes

FIGSIZE = (12, 7)
ACCENT = "#e4572e"
MONTH_BAR = np.timedelta64(25, "D")


@dataclass(frozen=True)
class ChartOptions:
    by_sender: bool = False
    separate: bool = False
    keywords: Sequence[str] = field(default_factory=tuple)
    case_sensitive: bool = False
    unit: str = "minutes"
    max_gap: timedelta | None = None


ChartFn = Callable[[Conversation, "Figure", ChartOptions], None]


def _style(ax: Axes) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)


def _dates(series: pl.Series) -> np.ndarray:
    return series.to_numpy()


def _wide(frame: pl.DataFrame, senders: Sequence[str]) -> pl.DataFrame:
    """Long ``period, sender, messages`` -> one column per sender, in conversation order."""
    wide = frame.pivot(on="sender", index="period", values="messages")
    return wide.select("period", *[s for s in senders if s in wide.columns])


def daily(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    messages = conv.messages
    title = "Messages per day"
    if opts.keywords:
        messages = an.filter_keywords(messages, opts.keywords, case_sensitive=opts.case_sensitive)
        title += f" containing: {', '.join(opts.keywords)}"

    if not opts.by_sender:
        data = an.messages_per_period(messages, "day", span=conv.messages)
        ax = fig.add_subplot()
        x, y = _dates(data["period"]), data["messages"].to_numpy()
        ax.fill_between(x, 0, y, alpha=0.2, color=ACCENT, step="mid")
        ax.plot(x, y, lw=1, color=ACCENT, drawstyle="steps-mid")
        ax.set(title=title, ylabel="Messages")
        _style(ax)
        return

    wide = _wide(
        an.messages_per_period(messages, "day", by_sender=True, span=conv.messages),
        conv.participants,
    )
    x = _dates(wide["period"])
    names = wide.columns[1:]
    if opts.separate:
        axes = fig.subplots(len(names), 1, sharex=True, squeeze=False)[:, 0]
        for i, (ax, name) in enumerate(zip(axes, names, strict=True)):
            ax.plot(x, wide[name].to_numpy(), lw=1, color=f"C{i}")
            ax.set_ylabel(name)
            _style(ax)
        axes[0].set_title(title + " per participant")
    else:
        ax = fig.add_subplot()
        for i, name in enumerate(names):
            ax.plot(x, wide[name].to_numpy(), lw=1, alpha=0.8, label=name, color=f"C{i}")
        ax.set(title=title + " per participant", ylabel="Messages")
        ax.legend()
        _style(ax)


def monthly(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    ax = fig.add_subplot()
    if not opts.by_sender:
        data = an.messages_per_period(conv.messages, "month")
        ax.bar(
            _dates(data["period"]),
            data["messages"].to_numpy(),
            width=MONTH_BAR,
            align="edge",
            color=ACCENT,
        )
        ax.set(title="Messages per month", ylabel="Messages")
    else:
        wide = _wide(
            an.messages_per_period(conv.messages, "month", by_sender=True), conv.participants
        )
        x = _dates(wide["period"])
        names = wide.columns[1:]
        width = np.timedelta64(26 * 24 // len(names), "h")
        for i, name in enumerate(names):
            ax.bar(
                x + i * width,
                wide[name].to_numpy(),
                width=width,
                align="edge",
                label=name,
                color=f"C{i}",
            )
        ax.set(title="Messages per month per participant", ylabel="Messages")
        ax.legend()
    _style(ax)


def participants(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.messages_per_sender(conv.messages)
    ax = fig.add_subplot()
    ax.bar(data["sender"].to_list(), data["messages"].to_numpy(), color=ACCENT)
    ax.set(title="Messages per participant", ylabel="Messages")
    ax.tick_params(axis="x", rotation=20)
    _style(ax)


def _radar(fig: Figure, labels: Sequence[str], values: np.ndarray, title: str) -> None:
    ax = cast("PolarAxes", fig.add_subplot(projection="polar"))
    theta = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    closed_theta, closed_values = np.append(theta, theta[0]), np.append(values, values[0])
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.plot(closed_theta, closed_values, color=ACCENT)
    ax.fill(closed_theta, closed_values, color=ACCENT, alpha=0.35)
    ax.set_xticks(theta, labels)
    ax.set_title(title, pad=20)


def weekday(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.messages_per_weekday(conv.messages)
    _radar(
        fig, data["weekday"].to_list(), data["messages"].to_numpy(), "Messages per day of the week"
    )


def hourly(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.messages_per_hour(conv.messages)
    labels = [f"{h:02d}:00" for h in data["hour"].to_list()]
    _radar(fig, labels, data["messages"].to_numpy(), "Messages per hour of the day")


def responses(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.response_times(conv.messages, max_gap=opts.max_gap)
    ax = fig.add_subplot()
    x = data["timestamp"].dt.replace_time_zone(None).to_numpy()
    ax.scatter(x, data["seconds"].to_numpy() / an.UNITS[opts.unit], s=2, alpha=0.4, color=ACCENT)
    ax.set_yscale("log")
    ax.set(title="Response time of each response", ylabel=f"Response time ({opts.unit}, log scale)")
    _style(ax)


def responses_monthly(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.mean_response_time_per_month(conv.messages, max_gap=opts.max_gap)
    ax = fig.add_subplot()
    values = (data["mean_seconds"] / an.UNITS[opts.unit]).fill_null(0).to_numpy()
    ax.bar(_dates(data["period"]), values, width=MONTH_BAR, align="edge", color=ACCENT)
    ax.set(title="Average response time per month", ylabel=f"Response time ({opts.unit})")
    _style(ax)


def words_monthly(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.average_words_per_month(conv.messages)
    ax = fig.add_subplot()
    ax.bar(
        _dates(data["period"]),
        data["mean_words"].fill_null(0).to_numpy(),
        width=MONTH_BAR,
        align="edge",
        color=ACCENT,
    )
    ax.set(title="Average words per text message per month", ylabel="Words")
    _style(ax)


def kinds(conv: Conversation, fig: Figure, opts: ChartOptions) -> None:
    data = an.kind_counts(conv.messages).filter(pl.col("messages") > 0)
    ax = fig.add_subplot()
    ax.bar(data["kind"].cast(pl.String).to_list(), data["messages"].to_numpy(), color=ACCENT)
    ax.set(title="Messages by type", ylabel="Messages")
    _style(ax)


#: CLI chart name -> (description, drawing function).
CHARTS: dict[str, tuple[str, ChartFn]] = {
    "daily": ("Messages per day (supports --by-participant, --separate, --keywords)", daily),
    "monthly": ("Messages per month (supports --by-participant)", monthly),
    "participants": ("Total messages per participant", participants),
    "weekday": ("Messages per day of the week (radar)", weekday),
    "hourly": ("Messages per hour of the day (radar)", hourly),
    "responses": ("Every response time over time (supports --unit)", responses),
    "responses-monthly": ("Average response time per month (supports --unit)", responses_monthly),
    "words-monthly": ("Average words per text message per month", words_monthly),
    "kinds": ("Messages by type (text, photo, video, ...)", kinds),
}


_DATE_AXIS = {"daily", "monthly", "responses", "responses-monthly", "words-monthly"}


def render(conv: Conversation, chart: str, opts: ChartOptions, fig: Figure) -> Figure:
    _, draw = CHARTS[chart]
    draw(conv, fig, opts)
    if chart in _DATE_AXIS:
        fig.autofmt_xdate()
    fig.tight_layout()
    return fig
