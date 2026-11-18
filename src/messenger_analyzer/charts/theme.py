"""Colour and typography tokens for light and dark charts.

The categorical palette was validated for colour-vision deficiency, adjacent-pair
separation and contrast against each surface (8 slots, both modes). Slots are
assigned to participants in a fixed order and never cycled: past eight, extra
participants fold into "Other". Light slots 3-5 sit below 3:1 contrast on the
light surface, so every chart ships with a legend and a data table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ThemeName = Literal["light", "dark"]

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif'


@dataclass(frozen=True)
class Theme:
    name: ThemeName
    surface: str
    page: str
    text: str
    text_secondary: str
    muted: str
    grid: str
    axis: str
    border: str
    #: Categorical slots, in assignment order.
    series: tuple[str, ...]
    #: Colour for the folded "Other" series.
    other: str
    #: De-emphasised context marks (e.g. raw daily counts behind an average).
    context: str
    #: Sequential single-hue scale for magnitude (heatmaps), low -> high.
    sequential: tuple[str, ...]


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    page="#f9f9f7",
    text="#0b0b0b",
    text_secondary="#52514e",
    muted="#898781",
    grid="#e1e0d9",
    axis="#c3c2b7",
    border="rgba(11,11,11,0.10)",
    series=("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
    other="#a8a79f",
    context="#dcdbd4",
    sequential=(
        "#f1f6fd",
        "#cde2fb",
        "#9ec5f4",
        "#6da7ec",
        "#3987e5",
        "#256abf",
        "#184f95",
        "#0d366b",
    ),
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    page="#0d0d0d",
    text="#f0efec",
    text_secondary="#c3c2b7",
    muted="#898781",
    grid="#2c2c2a",
    axis="#383835",
    border="rgba(255,255,255,0.10)",
    series=("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"),
    other="#6b6a65",
    context="#3a3a37",
    sequential=(
        "#1e2733",
        "#0d366b",
        "#104281",
        "#184f95",
        "#256abf",
        "#3987e5",
        "#6da7ec",
        "#b7d3f6",
    ),
)

THEMES: dict[ThemeName, Theme] = {"light": LIGHT, "dark": DARK}


def colorscale(theme: Theme) -> list[list[Any]]:
    steps = theme.sequential
    return [[i / (len(steps) - 1), color] for i, color in enumerate(steps)]


def base_layout(theme: Theme) -> dict[str, Any]:
    """Plotly layout shared by every chart: quiet chrome, the data is the loud part."""
    axis = {
        "gridcolor": theme.grid,
        "gridwidth": 1,
        "linecolor": theme.axis,
        "zeroline": False,
        "tickfont": {"color": theme.muted, "size": 12},
        "title": {"font": {"color": theme.text_secondary, "size": 12}},
        "automargin": True,
        "showspikes": False,
    }
    return {
        "font": {"family": FONT, "color": theme.text_secondary, "size": 13},
        "paper_bgcolor": theme.surface,
        "plot_bgcolor": theme.surface,
        "colorway": list(theme.series),
        "margin": {"l": 8, "r": 16, "t": 16, "b": 8, "pad": 4},
        "xaxis": {
            **axis,
            "showgrid": False,
            "showline": True,
            "ticks": "outside",
            "tickcolor": theme.axis,
        },
        "yaxis": {**axis, "showgrid": True, "showline": False, "tickformat": ",~s"},
        "legend": {
            "orientation": "h",
            # Stacked bars otherwise list series bottom-up; keep conversation order everywhere.
            "traceorder": "normal",
            "x": 0,
            "xanchor": "left",
            "y": 1.02,
            "yanchor": "bottom",
            "font": {"color": theme.text_secondary},
            "bgcolor": "rgba(0,0,0,0)",
        },
        "hoverlabel": {
            "bgcolor": theme.surface,
            "bordercolor": theme.axis,
            "font": {"family": FONT, "color": theme.text, "size": 13},
        },
        "bargap": 0.3,
        "bargroupgap": 0.08,
    }
