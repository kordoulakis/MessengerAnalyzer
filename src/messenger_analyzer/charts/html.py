"""Self-contained HTML pages for one chart or a whole dashboard.

Every chart is embedded twice, once per theme. The page shows the one matching
the viewer's system setting (or the toggle in the corner) and swaps live, so a
chart is never an automatic colour inversion of the other mode. By default
plotly.js is inlined, so the page works offline and loads nothing from the web.
"""

from __future__ import annotations

import html
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import plotly.io as pio
import polars as pl

from messenger_analyzer.charts.figures import Chart

ThemeMode = Literal["auto", "light", "dark"]
PlotlyJS = Literal["inline", "cdn"]


@dataclass
class Section:
    id: str
    light: Chart
    dark: Chart
    wide: bool = False


@dataclass
class Kpi:
    label: str
    value: str
    note: str = ""


def _cell(value: object) -> str:
    if value is None:
        return "–"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return "–" if math.isnan(value) else f"{value:,.2f}"
    if isinstance(value, datetime | date):
        return value.isoformat()
    return html.escape(str(value))


def table_html(frame: pl.DataFrame) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in frame.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(v)}</td>" for v in row) + "</tr>" for row in frame.iter_rows()
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _figure_json(chart: Chart) -> str:
    return str(pio.to_json(chart.figure, validate=False, pretty=False))


def _plotly_script(mode: PlotlyJS) -> str:
    from plotly.offline import get_plotlyjs, get_plotlyjs_version

    if mode == "cdn":
        src = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
        return f'<script src="{src}" charset="utf-8"></script>'
    return f'<script type="text/javascript">{get_plotlyjs()}</script>'


_CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --text: #0b0b0b; --text-2: #52514e;
  --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --text: #f0efec; --text-2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --text: #f0efec; --text-2: #c3c2b7;
  --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif;
}
main { max-width: 1200px; margin: 0 auto; padding: 32px 16px 64px; }
header { display: flex; gap: 16px; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; }
h1 { font-size: 28px; line-height: 1.2; font-weight: 600; margin: 0 0 4px; overflow-wrap: anywhere; }
header p { margin: 0; color: var(--text-2); }
.toggle {
  flex: none; font: inherit; font-size: 13px; color: var(--text-2); background: var(--surface);
  border: 1px solid var(--border); border-radius: 999px; padding: 6px 14px; cursor: pointer;
}
.toggle:hover { color: var(--text); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; min-width: 0; }
.kpi .label { color: var(--text-2); font-size: 13px; }
.kpi .value { font-size: 26px; font-weight: 600; line-height: 1.25; overflow-wrap: anywhere; }
.kpi .note { color: var(--muted); font-size: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 16px 4px; min-width: 0; }
.card.wide { grid-column: 1 / -1; }
.card h2 { font-size: 16px; font-weight: 600; margin: 0; }
.card .sub { color: var(--text-2); font-size: 13px; margin: 2px 0 8px; }
.plot { width: 100%; }
details { border-top: 1px solid var(--grid); margin-top: 4px; }
summary { cursor: pointer; color: var(--text-2); font-size: 13px; padding: 10px 0; }
.table-wrap { max-height: 320px; overflow: auto; margin-bottom: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums; }
th, td { padding: 4px 10px; border-bottom: 1px solid var(--grid); text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
thead th { position: sticky; top: 0; background: var(--surface); color: var(--text-2); font-weight: 600; }
footer { margin-top: 32px; color: var(--muted); font-size: 12px; }
"""

_JS = """
(function () {
  const root = document.documentElement;
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const button = document.getElementById("theme-toggle");
  const labels = { auto: "Theme: auto", light: "Theme: light", dark: "Theme: dark" };
  const config = { responsive: true, displaylogo: false,
                   modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] };
  try {
    const saved = localStorage.getItem("msganalyzer-theme");
    if (saved === "auto" || saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch (e) {}
  function mode() {
    const t = root.dataset.theme;
    return t === "light" || t === "dark" ? t : (media.matches ? "dark" : "light");
  }
  function layoutFor(id, layout) {
    // Range buttons collide with the legend on narrow screens; pinch-zoom covers it there.
    const narrow = document.getElementById(id).clientWidth < 600;
    if (!layout.xaxis || !layout.xaxis.rangeselector) return layout;
    const xaxis = Object.assign({}, layout.xaxis, {
      rangeselector: Object.assign({}, layout.xaxis.rangeselector, { visible: !narrow }),
    });
    return Object.assign({}, layout, { xaxis: xaxis });
  }
  function draw() {
    const m = mode();
    for (const [id, fig] of Object.entries(FIGURES)) {
      Plotly.react(id, fig[m].data, layoutFor(id, fig[m].layout), config);
    }
    button.textContent = labels[root.dataset.theme] || labels.auto;
  }
  let resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(draw, 200);
  });
  button.addEventListener("click", function () {
    const order = ["auto", "light", "dark"];
    root.dataset.theme = order[(order.indexOf(root.dataset.theme) + 1) % order.length];
    try { localStorage.setItem("msganalyzer-theme", root.dataset.theme); } catch (e) {}
    draw();
  });
  media.addEventListener("change", function () { if (root.dataset.theme === "auto") draw(); });
  draw();
})();
"""


def render_page(
    *,
    title: str,
    subtitle: str,
    sections: list[Section],
    kpis: list[Kpi] | None = None,
    theme: ThemeMode = "auto",
    plotly_js: PlotlyJS = "inline",
) -> str:
    figures = ",".join(
        f'{json.dumps(s.id)}:{{"light":{_figure_json(s.light)},"dark":{_figure_json(s.dark)}}}'
        for s in sections
    )
    # Chart text includes chat content; never let it close the script element.
    figures_js = "const FIGURES = {" + figures.replace("</", "<\\/") + "};"

    kpi_html = ""
    if kpis:
        tiles = "".join(
            f'<div class="kpi"><div class="label">{html.escape(k.label)}</div>'
            f'<div class="value">{html.escape(k.value)}</div>'
            + (f'<div class="note">{html.escape(k.note)}</div>' if k.note else "")
            + "</div>"
            for k in kpis
        )
        kpi_html = f'<section class="kpis">{tiles}</section>'

    cards = "".join(
        f'<section class="card{" wide" if s.wide else ""}">'
        f"<h2>{html.escape(s.light.title)}</h2>"
        f'<p class="sub">{html.escape(s.light.subtitle)}</p>'
        f'<div class="plot" id="{html.escape(s.id)}" style="height:{s.light.height}px"></div>'
        f"<details><summary>Data table</summary>"
        f'<div class="table-wrap">{table_html(s.light.table)}</div></details>'
        f"</section>"
        for s in sections
    )

    footer = (
        "Generated locally by msganalyzer. This page loads plotly.js from cdn.plot.ly; "
        "your data stays in the file."
        if plotly_js == "cdn"
        else "Generated locally by msganalyzer. This page loads nothing from the internet."
    )
    return f"""<!doctype html>
<html lang="en" data-theme="{theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_CSS}</style>
{_plotly_script(plotly_js)}
</head>
<body>
<main>
<header>
  <div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>
  <button class="toggle" id="theme-toggle" type="button">Theme: {theme}</button>
</header>
{kpi_html}
<div class="grid">{cards}</div>
<footer>{footer}</footer>
</main>
<script>{figures_js}</script>
<script>{_JS}</script>
</body>
</html>
"""
