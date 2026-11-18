"""Chart definitions: each turns a conversation into a Plotly figure plus its data table.

Charts never pick colours by rank: participants get palette slots in the order
they first appear in the conversation, so a person keeps the same colour in
every chart. Beyond eight participants the quietest ones fold into "Other".
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
from typing import Any

import plotly.graph_objects as go
import polars as pl

from messenger_analyzer import analysis as an
from messenger_analyzer.charts.theme import Theme, base_layout, colorscale
from messenger_analyzer.report import format_duration
from messenger_analyzer.schema import Conversation

OTHER = "Other"
MAX_SERIES = 8
MAX_BARS = 15


class ChartUnavailable(ValueError):
    """The chart makes no sense for this conversation (e.g. a share chart with one person)."""


@dataclass(frozen=True)
class ChartOptions:
    by_sender: bool = False
    keywords: Sequence[str] = ()
    case_sensitive: bool = False
    unit: str = "minutes"
    max_gap: timedelta | None = None
    #: Days in the rolling average of the activity chart.
    window: int = 30
    #: Rows in the top-words chart.
    top: int = 20


@dataclass
class Chart:
    figure: go.Figure
    table: pl.DataFrame
    title: str
    subtitle: str
    height: int = 380


Builder = Callable[[Conversation, ChartOptions, Theme], Chart]


# --------------------------------------------------------------------------- helpers


def kept_senders(conv: Conversation) -> list[str]:
    """Participants that get their own colour, in conversation order."""
    if len(conv.participants) <= MAX_SERIES:
        return list(conv.participants)
    busiest = set(an.messages_per_sender(conv.messages)["sender"].head(MAX_SERIES - 1).to_list())
    return [s for s in conv.participants if s in busiest]


def sender_colors(conv: Conversation, theme: Theme) -> dict[str, str]:
    colors = {s: theme.series[i] for i, s in enumerate(kept_senders(conv))}
    colors[OTHER] = theme.other
    return colors


def _fold(
    frame: pl.DataFrame, conv: Conversation, keys: list[str], values: list[str]
) -> pl.DataFrame:
    """Sum the participants without their own colour into one "Other" row per key."""
    kept = kept_senders(conv)
    if frame.get_column("sender").is_in(kept).all():
        return frame
    sender = pl.when(pl.col("sender").is_in(kept)).then(pl.col("sender")).otherwise(pl.lit(OTHER))
    return (
        frame.with_columns(sender.alias("sender"))
        .group_by(keys, maintain_order=True)
        .agg(pl.col(values).sum())
    )


def _series_order(frame: pl.DataFrame, conv: Conversation) -> list[str]:
    present = set(frame.get_column("sender").to_list())
    return [s for s in [*kept_senders(conv), OTHER] if s in present]


def _layout(fig: go.Figure, theme: Theme, height: int, **overrides: Any) -> None:
    fig.update_layout(base_layout(theme))
    fig.update_layout(height=height, **overrides)


def _end_labels(
    fig: go.Figure, theme: Theme, series: list[tuple[str, Any, float]], y_span: float
) -> None:
    """Name 2-4 lines at their right end, unless two ends are too close to tell apart."""
    if not 2 <= len(series) <= 4:
        return
    ends = sorted(y for _, _, y in series)
    if any(b - a < 0.06 * (y_span or 1) for a, b in pairwise(ends)):
        return  # converging lines: the legend and tooltip carry identity instead
    for name, x, y in series:
        fig.add_annotation(
            x=x,
            y=y,
            text=name,
            xanchor="left",
            xshift=6,
            showarrow=False,
            font={"color": theme.text_secondary, "size": 12},
        )
    fig.update_layout(margin={"r": 96})


def _last_point(x: list[Any], y: list[float | None]) -> tuple[Any, float] | None:
    for xi, yi in zip(reversed(x), reversed(y), strict=True):
        if yi is not None:
            return xi, yi
    return None


def _lines(
    fig: go.Figure,
    frame: pl.DataFrame,
    conv: Conversation,
    theme: Theme,
    *,
    value: str,
    hover: str,
) -> None:
    """One 2px line per participant, coloured by identity, with end labels when they fit."""
    colors = sender_colors(conv, theme)
    ends: list[tuple[str, Any, float]] = []
    for name in _series_order(frame, conv):
        part = frame.filter(pl.col("sender") == name)
        x, y = part["period"].to_list(), part[value].to_list()
        fig.add_scatter(
            x=x,
            y=y,
            name=name,
            mode="lines",
            connectgaps=False,
            line={"color": colors[name], "width": 2},
            hovertemplate=f"{hover}<extra>{name}</extra>",
        )
        if point := _last_point(x, y):
            ends.append((name, *point))
    span = frame.select((pl.col(value).max() - pl.col(value).min()).cast(pl.Float64)).item()
    _end_labels(fig, theme, ends, span or 0.0)


def _month_axis(fig: go.Figure) -> None:
    fig.update_xaxes(type="date", tickformat="%b %Y", hoverformat="%B %Y")


def _rangeselector(theme: Theme) -> dict[str, Any]:
    return {
        "buttons": [
            {"count": 3, "label": "3m", "step": "month", "stepmode": "backward"},
            {"count": 1, "label": "1y", "step": "year", "stepmode": "backward"},
            {"step": "all", "label": "All"},
        ],
        "x": 1,
        "xanchor": "right",
        "y": 1.02,
        "yanchor": "bottom",
        "bgcolor": theme.surface,
        "activecolor": theme.grid,
        "bordercolor": theme.axis,
        "borderwidth": 1,
        "font": {"color": theme.text_secondary, "size": 12},
    }


def _ranked_bars(
    fig: go.Figure,
    theme: Theme,
    labels: list[str],
    values: list[float],
    *,
    hover: str,
    text: list[str],
) -> int:
    """Horizontal bars, largest on top, one hue, value at the tip. Returns a fitting height."""
    fig.add_bar(
        y=labels,
        x=values,
        orientation="h",
        marker={"color": theme.series[0]},
        text=text,
        textposition="outside",
        cliponaxis=False,
        textfont={"color": theme.text_secondary, "size": 12},
        hovertemplate=hover,
        showlegend=False,
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"color": theme.text_secondary})
    fig.update_xaxes(showgrid=True, showline=False, ticks="")
    return max(200, 30 * len(labels) + 60)


def _unit_label(unit: str) -> str:
    return {"seconds": "s", "minutes": "min", "hours": "h"}[unit]


# --------------------------------------------------------------------------- charts


def activity(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    messages, title = conv.messages, "Messages over time"
    if opts.keywords:
        messages = an.filter_keywords(messages, opts.keywords, case_sensitive=opts.case_sensitive)
        title = f"Messages mentioning {', '.join(opts.keywords)}"
    avg = pl.col("messages").rolling_mean(opts.window, min_samples=1)
    fig = go.Figure()

    if not opts.by_sender:
        data = an.messages_per_period(messages, "day", span=conv.messages)
        data = data.with_columns(avg.alias("average"))
        x = data["period"].to_list()
        fig.add_bar(
            x=x,
            y=data["messages"].to_list(),
            name="Each day",
            marker={"color": theme.context, "line": {"width": 0}},
            hovertemplate="%{y:,} messages<extra>that day</extra>",
        )
        fig.add_scatter(
            x=x,
            y=data["average"].to_list(),
            name=f"{opts.window}-day average",
            mode="lines",
            line={"color": theme.series[0], "width": 2},
            hovertemplate="%{y:,.1f} a day<extra>average</extra>",
        )
        table = data
        subtitle = f"Messages each day, with a {opts.window}-day rolling average."
    else:
        data = _fold(
            an.messages_per_period(messages, "day", by_sender=True, span=conv.messages),
            conv,
            ["period", "sender"],
            ["messages"],
        )
        data = data.sort("sender", "period").with_columns(avg.over("sender").alias("average"))
        _lines(fig, data, conv, theme, value="average", hover="%{y:,.1f} a day")
        table = data.pivot(on="sender", index="period", values="messages").sort("period")
        subtitle = f"{opts.window}-day rolling average of messages per day, per participant."

    _layout(fig, theme, 400, hovermode="x unified", bargap=0)
    fig.update_xaxes(type="date", hoverformat="%a %d %b %Y", rangeselector=_rangeselector(theme))
    return Chart(fig, table, title, subtitle, 400)


def monthly(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    fig = go.Figure()
    if not opts.by_sender:
        data = an.messages_per_period(conv.messages, "month")
        fig.add_bar(
            x=data["period"].to_list(),
            y=data["messages"].to_list(),
            name="Messages",
            marker={"color": theme.series[0]},
            xperiod="M1",
            xperiodalignment="middle",
            hovertemplate="%{y:,} messages<extra></extra>",
            showlegend=False,
        )
        table = data
        subtitle = "Total messages sent each month."
    else:
        data = _fold(
            an.messages_per_period(conv.messages, "month", by_sender=True),
            conv,
            ["period", "sender"],
            ["messages"],
        )
        colors = sender_colors(conv, theme)
        for name in _series_order(data, conv):
            part = data.filter(pl.col("sender") == name)
            fig.add_bar(
                x=part["period"].to_list(),
                y=part["messages"].to_list(),
                name=name,
                marker={"color": colors[name], "line": {"color": theme.surface, "width": 1}},
                xperiod="M1",
                xperiodalignment="middle",
                hovertemplate=f"%{{y:,}} messages<extra>{name}</extra>",
            )
        table = data.pivot(on="sender", index="period", values="messages").sort("period")
        subtitle = "Messages sent each month, stacked by participant."
    _layout(fig, theme, 380, barmode="stack", barcornerradius=4, hovermode="x unified")
    _month_axis(fig)
    return Chart(fig, table, "Messages per month", subtitle, 380)


def share(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    if len(conv.participants) < 2:
        raise ChartUnavailable("The share chart needs at least two participants")
    data = _fold(
        an.messages_per_period(conv.messages, "month", by_sender=True),
        conv,
        ["period", "sender"],
        ["messages"],
    )
    total = pl.col("messages").sum().over("period")
    data = data.with_columns(
        pl.when(total > 0).then(pl.col("messages") / total * 100).otherwise(None).alias("share")
    )
    fig = go.Figure()
    colors = sender_colors(conv, theme)
    for name in _series_order(data, conv):
        part = data.filter(pl.col("sender") == name)
        fig.add_bar(
            x=part["period"].to_list(),
            y=part["share"].to_list(),
            name=name,
            marker={"color": colors[name], "line": {"color": theme.surface, "width": 1}},
            xperiod="M1",
            xperiodalignment="middle",
            hovertemplate=f"%{{y:.1f}}%<extra>{name}</extra>",
        )
    _layout(fig, theme, 360, barmode="stack", hovermode="x unified", bargap=0.15)
    fig.update_yaxes(range=[0, 100], ticksuffix="%", tickformat="d")
    _month_axis(fig)
    table = data.pivot(on="sender", index="period", values="share").sort("period")
    return Chart(
        fig, table, "Who does the talking", "Each participant's share of the month's messages.", 360
    )


def rhythm(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = an.messages_per_weekday_hour(conv.messages)
    table = data.pivot(on="hour", index="weekday", values="messages")
    hours = [f"{h:02d}" for h in range(24)]
    z = [row[1:] for row in table.rows()]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=hours,
            y=list(an.WEEKDAYS),
            colorscale=colorscale(theme),
            xgap=2,
            ygap=2,
            hovertemplate="%{y} %{x}:00<br>%{z:,} messages<extra></extra>",
            colorbar={
                "thickness": 10,
                "outlinewidth": 0,
                "len": 0.9,
                "tickfont": {"color": theme.muted, "size": 11},
                "tickformat": ",~s",
            },
        )
    )
    _layout(fig, theme, 320)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"color": theme.text_secondary})
    fig.update_xaxes(title={"text": "Hour of day"}, showline=False, ticks="", type="category")
    table = table.rename({str(h): f"{h:02d}:00" for h in range(24)})
    return Chart(
        fig, table, "Weekly rhythm", "Messages by day of the week and hour of the day.", 320
    )


def participants(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = an.messages_per_sender(conv.messages)
    if data.height > MAX_BARS:
        rest = data.slice(MAX_BARS - 1)
        data = pl.concat(
            [
                data.head(MAX_BARS - 1),
                pl.DataFrame(
                    {
                        "sender": [f"{OTHER} ({rest.height})"],
                        "messages": [rest["messages"].sum()],
                        "share": [rest["share"].sum()],
                    },
                    schema=data.schema,
                ),
            ]
        )
    fig = go.Figure()
    height = _ranked_bars(
        fig,
        theme,
        data["sender"].to_list(),
        data["messages"].to_list(),
        hover="%{y}: %{x:,} messages<extra></extra>",
        text=[f"{m:,} · {s:.0%}" for m, s in data.select("messages", "share").rows()],
    )
    _layout(fig, theme, height, margin={"r": 96})
    return Chart(
        fig, data, "Messages per participant", "Total messages sent by each person.", height
    )


def response_times(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = an.response_time_distribution(
        conv.messages, by_sender=opts.by_sender, max_gap=opts.max_gap
    )
    if data["responses"].sum() == 0:
        raise ChartUnavailable("Nobody replied to anybody, so there are no response times")
    labels = [label for _, label in an.BUCKETS]
    fig = go.Figure()
    if not opts.by_sender:
        fig.add_bar(
            x=labels,
            y=(data["share"] * 100).to_list(),
            marker={"color": theme.series[0]},
            customdata=data["responses"].to_list(),
            showlegend=False,
            hovertemplate="%{y:.1f}% of replies (%{customdata:,})<extra>%{x}</extra>",
        )
        table = data.with_columns(pl.col("bucket").cast(pl.String))
    else:
        data = _fold(
            data.with_columns(pl.col("bucket").cast(pl.String)),
            conv,
            ["sender", "bucket"],
            ["responses"],
        )
        data = data.with_columns(
            (pl.col("responses") / pl.col("responses").sum().over("sender"))
            .fill_nan(0)
            .alias("share")
        )
        colors = sender_colors(conv, theme)
        for name in _series_order(data, conv):
            part = data.filter(pl.col("sender") == name)
            fig.add_bar(
                x=part["bucket"].to_list(),
                y=(part["share"] * 100).to_list(),
                name=name,
                marker={"color": colors[name]},
                customdata=part["responses"].to_list(),
                hovertemplate=f"%{{y:.1f}}% of {name}'s replies (%{{customdata:,}})<extra>%{{x}}</extra>",
            )
        table = data.pivot(on="sender", index="bucket", values="share")
    _layout(fig, theme, 360, barmode="group", barcornerradius=4)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=labels)
    fig.update_yaxes(ticksuffix="%", tickformat="d")
    gap = (
        f" Gaps over {format_duration(opts.max_gap.total_seconds())} ignored."
        if opts.max_gap
        else ""
    )
    return Chart(
        fig, table, "How fast people reply", f"Share of replies by time taken to reply.{gap}", 360
    )


def response_trend(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    divisor, unit = an.UNITS[opts.unit], _unit_label(opts.unit)
    data = an.response_time_per_month(conv.messages, by_sender=opts.by_sender, max_gap=opts.max_gap)
    data = data.with_columns((pl.col("median_seconds") / divisor).alias("median"))
    fig = go.Figure()
    subtitle = "Median time to reply, per month."
    if not opts.by_sender:
        fig.add_scatter(
            x=data["period"].to_list(),
            y=data["median"].to_list(),
            mode="lines",
            line={"color": theme.series[0], "width": 2},
            connectgaps=False,
            showlegend=False,
            hovertemplate=f"%{{y:,.1f}} {unit}<extra>median</extra>",
        )
        table = data.select("period", "responses", "median")
    else:
        kept = kept_senders(conv)
        data = data.filter(pl.col("sender").is_in(kept))
        _lines(fig, data, conv, theme, value="median", hover=f"%{{y:,.1f}} {unit}")
        table = data.pivot(on="sender", index="period", values="median").sort("period")
        if len(kept) < len(conv.participants):
            subtitle += f" The {len(kept)} most active participants."
    if opts.max_gap:
        subtitle += f" Gaps over {format_duration(opts.max_gap.total_seconds())} ignored."
    _layout(fig, theme, 360, hovermode="x unified")
    fig.update_yaxes(
        title={"text": f"Median reply ({opts.unit})"}, tickformat=",~r", rangemode="tozero"
    )
    _month_axis(fig)
    return Chart(fig, table, "Reply speed over time", subtitle, 360)


def words(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = an.average_words_per_month(conv.messages, by_sender=opts.by_sender)
    fig = go.Figure()
    if not opts.by_sender:
        fig.add_scatter(
            x=data["period"].to_list(),
            y=data["mean_words"].to_list(),
            mode="lines",
            line={"color": theme.series[0], "width": 2},
            connectgaps=False,
            showlegend=False,
            hovertemplate="%{y:.1f} words<extra>average</extra>",
        )
        table = data
    else:
        data = data.filter(pl.col("sender").is_in(kept_senders(conv)))
        _lines(fig, data, conv, theme, value="mean_words", hover="%{y:.1f} words")
        table = data.pivot(on="sender", index="period", values="mean_words").sort("period")
    _layout(fig, theme, 340, hovermode="x unified")
    fig.update_yaxes(title={"text": "Words per message"}, rangemode="tozero", tickformat=",~r")
    _month_axis(fig)
    return Chart(fig, table, "Message length", "Average words per text message, per month.", 340)


def kinds(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = (
        an.kind_counts(conv.messages)
        .filter(pl.col("messages") > 0)
        .with_columns(pl.col("kind").cast(pl.String))
        .sort("messages", descending=True)
    )
    total = max(int(data["messages"].sum()), 1)
    fig = go.Figure()
    height = _ranked_bars(
        fig,
        theme,
        data["kind"].to_list(),
        data["messages"].to_list(),
        hover="%{y}: %{x:,}<extra></extra>",
        text=[f"{m:,} · {m / total:.0%}" for m in data["messages"].to_list()],
    )
    _layout(fig, theme, height, margin={"r": 96})
    return Chart(fig, data, "Message types", "Text, photos, calls and everything else.", height)


def top_words(conv: Conversation, opts: ChartOptions, theme: Theme) -> Chart:
    data = an.top_words(conv.messages, opts.top, case_sensitive=opts.case_sensitive)
    fig = go.Figure()
    height = _ranked_bars(
        fig,
        theme,
        data["word"].to_list(),
        data["count"].to_list(),
        hover="%{y}: %{x:,} times<extra></extra>",
        text=[f"{c:,}" for c in data["count"].to_list()],
    )
    _layout(fig, theme, height, margin={"r": 64})
    return Chart(fig, data, f"Top {data.height} words", "Most used words in text messages.", height)


@dataclass(frozen=True)
class ChartSpec:
    name: str
    description: str
    build: Builder
    #: Spans the full width in the dashboard.
    wide: bool = False


CHARTS: dict[str, ChartSpec] = {
    spec.name: spec
    for spec in (
        ChartSpec(
            "activity",
            "Messages per day with a rolling average (--by-participant, --keywords, --window)",
            activity,
            wide=True,
        ),
        ChartSpec(
            "monthly", "Messages per month (--by-participant stacks them)", monthly, wide=True
        ),
        ChartSpec("share", "Each participant's share of messages, per month", share, wide=True),
        ChartSpec("rhythm", "Heatmap of messages by weekday and hour", rhythm, wide=True),
        ChartSpec("participants", "Total messages per participant", participants),
        ChartSpec(
            "response-times",
            "Distribution of reply times (--by-participant, --max-gap)",
            response_times,
        ),
        ChartSpec(
            "response-trend",
            "Median reply time per month (--by-participant, --unit, --max-gap)",
            response_trend,
        ),
        ChartSpec("words", "Average words per text message per month (--by-participant)", words),
        ChartSpec("kinds", "Messages by type: text, photo, call, ...", kinds),
        ChartSpec("top-words", "Most used words (--top)", top_words),
    )
}


def build(conv: Conversation, name: str, opts: ChartOptions, theme: Theme) -> Chart:
    return CHARTS[name].build(conv, opts, theme)
