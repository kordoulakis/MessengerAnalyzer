"""Interactive charts (Plotly): single-chart pages, a dashboard, and image export.

Image export additionally needs the ``export`` extra (kaleido) and a
Chrome/Chromium browser.
"""

from __future__ import annotations

from pathlib import Path

from nostos import analysis as an
from nostos.analysis.activity import period_range
from nostos.charts.figures import (
    CHARTS,
    Chart,
    ChartOptions,
    ChartUnavailable,
    build,
    kept_senders,
)
from nostos.charts.html import Kpi, Section, ThemeMode, render_page
from nostos.charts.theme import DARK, LIGHT, THEMES, ThemeName
from nostos.report import format_duration
from nostos.schema import Conversation

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf"}


class ExportError(RuntimeError):
    """Static image export failed (usually kaleido or Chrome is missing)."""


def _section(conv: Conversation, name: str, opts: ChartOptions) -> Section:
    return Section(
        id=f"chart-{name}",
        light=build(conv, name, opts, LIGHT),
        dark=build(conv, name, opts, DARK),
        wide=CHARTS[name].wide,
    )


def _date_range(conv: Conversation) -> str:
    ts = conv.messages["timestamp"]
    if ts.is_empty():
        return "no messages"
    first, last = ts.dt.date().min(), ts.dt.date().max()
    return f"{first:%d %b %Y} – {last:%d %b %Y}"  # type: ignore[str-format,str-bytes-safe]


def chart_page(
    conv: Conversation,
    name: str,
    opts: ChartOptions,
    *,
    theme: ThemeMode = "auto",
) -> str:
    section = _section(conv, name, opts)
    section.wide = True
    return render_page(
        title=conv.title,
        subtitle=f"{', '.join(conv.participants)} · {_date_range(conv)}",
        sections=[section],
        theme=theme,
    )


def _kpis(conv: Conversation, opts: ChartOptions) -> list[Kpi]:
    m = conv.messages
    span = period_range(m, "day").height
    responses = an.response_time_summary(m, max_gap=opts.max_gap)
    busiest = an.top_periods(m, "day", 1)
    words = an.average_words(m)
    kpis = [
        Kpi("Messages", f"{len(m):,}", f"{len(conv.participants)} participants"),
        Kpi("Days", f"{span:,}", f"{len(m) / max(span, 1):,.0f} messages a day"),
        Kpi(
            "Typical reply",
            format_duration(responses["median_seconds"]),  # type: ignore[arg-type]
            f"median of {responses['responses']:,} replies",
        ),
        Kpi("Words per message", "–" if words is None else f"{words:.1f}", "text messages only"),
    ]
    if busiest.height:
        day, count = busiest.row(0)
        kpis.append(Kpi("Busiest day", f"{day:%d %b %Y}", f"{count:,} messages"))
    return kpis


def dashboard_page(
    conv: Conversation,
    opts: ChartOptions,
    *,
    theme: ThemeMode = "auto",
) -> str:
    """Every chart on one page, with headline numbers on top."""
    group = len(conv.participants) > 1
    few = 1 < len(kept_senders(conv)) <= 4
    per_chart = {
        "activity": ChartOptions(**{**opts.__dict__, "by_sender": False}),
        "monthly": ChartOptions(**{**opts.__dict__, "by_sender": group}),
        "response-times": ChartOptions(**{**opts.__dict__, "by_sender": group}),
        "response-trend": ChartOptions(**{**opts.__dict__, "by_sender": few}),
        "words": ChartOptions(**{**opts.__dict__, "by_sender": few}),
    }
    sections = []
    for name in CHARTS:
        try:
            sections.append(_section(conv, name, per_chart.get(name, opts)))
        except ChartUnavailable:
            continue
    return render_page(
        title=conv.title,
        subtitle=f"{', '.join(conv.participants)} · {_date_range(conv)}",
        sections=sections,
        kpis=_kpis(conv, opts),
        theme=theme,
    )


def export_image(
    conv: Conversation,
    name: str,
    opts: ChartOptions,
    path: Path,
    *,
    theme: ThemeName = "light",
    width: int = 1200,
    scale: float = 2,
) -> None:
    """Write one chart as a static image; the format follows ``path``'s suffix."""
    selected = THEMES[theme]
    chart = build(conv, name, opts, selected)
    fig = chart.figure
    # Plotly draws a legend when two or more traces can appear in it; leave room for it.
    legend_traces = [t for t in fig.data if t.showlegend is not False and t.type != "heatmap"]
    top = 96 + (40 if len(legend_traces) >= 2 else 0)
    fig.update_layout(
        title={
            "text": chart.title,
            "subtitle": {
                "text": chart.subtitle,
                "font": {"color": selected.text_secondary, "size": 13},
            },
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
            "pad": {"l": 8},
            "font": {"color": selected.text, "size": 18},
        },
        margin={"t": top, "l": 16, "b": 16},
        width=width,
        height=chart.height + top,
    )
    try:
        import kaleido  # noqa: PLC0415 - optional dependency, only needed for export

        # Call kaleido directly: through plotly it would load MathJax from a CDN,
        # and export must not touch the network. plotly.js comes from the local
        # plotly package.
        image = kaleido.calc_fig_sync(
            fig.to_dict(),
            opts={
                "format": path.suffix.lower().lstrip("."),
                "width": width,
                "height": chart.height + top,
                "scale": scale,
            },
            kopts={"mathjax": False},
        )
        path.write_bytes(image)
    except Exception as exc:  # kaleido raises various errors when Chrome is missing
        raise ExportError(
            "Image export needs kaleido and Chrome: pip install -e '.[export]', "
            f"then run plotly_get_chrome. ({exc})"
        ) from exc


__all__ = [
    "CHARTS",
    "IMAGE_SUFFIXES",
    "Chart",
    "ChartOptions",
    "ChartUnavailable",
    "ExportError",
    "chart_page",
    "dashboard_page",
    "export_image",
]
