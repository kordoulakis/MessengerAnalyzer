# Architecture

```
            ┌───────────────┐   Conversation    ┌────────────┐  tables / scalars  ┌──────────────┐
 export ──▶ │   loaders/    │ ────────────────▶ │  analysis/ │ ─────────────────▶ │ report.py    │──▶ text / JSON
 folder     │ messenger.py  │  (schema.py)      │ pure funcs │                    │ charts/      │──▶ html / png
            └───────────────┘                   └────────────┘                    └──────────────┘
                                                                                         ▲
                                                       cli.py: parses flags, wires the layers together
```

Each layer only depends on the ones to its left.

| Module | Responsibility | Must not |
|---|---|---|
| `schema.py` | The canonical `Conversation`: a Polars frame with `timestamp` (tz-aware), `sender`, `text`, `kind` | know about any platform |
| `loaders/` | Turn one platform's export into a `Conversation`. Registry in `loaders/__init__.py` | compute statistics |
| `analysis/` | Pure, vectorized functions: `DataFrame -> DataFrame \| scalar` | print, plot, read files |
| `report.py` | Run every analysis once, return JSON-serialisable data; render it as text or JSON | do I/O |
| `charts/theme.py` | Colour and type tokens for light and dark | know about charts |
| `charts/figures.py` | One function per chart: conversation -> Plotly figure + data table | write files |
| `charts/html.py` | Self-contained HTML page (one chart or the dashboard) with live theme switching | compute statistics |
| `cli.py` | Argument parsing, file paths, timing output, exit codes | contain analysis logic |

## Design decisions

- **Polars, not pandas or pure Python.** All statistics are columnar expressions
  run in Rust. Text-heavy work (tokenising, word counts) uses Polars' streaming
  engine, which spreads it across all CPU cores.
- **One canonical schema.** Adding Instagram or WhatsApp means writing a loader
  that outputs the same four columns; analysis, report, plots and CLI work
  unchanged.
- **Timezone is applied once.** Loaders emit UTC; `Conversation.in_timezone()`
  converts before analysis, so "messages per hour" means the user's local hours.
- **Tidy outputs.** Per-participant results are long tables
  (`period, sender, messages`), which serialize directly to JSON for a future
  web front end; plotting pivots them as needed.
- **Data and presentation are separate.** `build_report()` returns plain data;
  `to_text()` / `to_json()` render it. A web API can return `build_report()`
  as-is.
- **Interactive charts with Plotly.** Pages are self-contained HTML (plotly.js
  inlined, so they work offline). The figure JSON is the same format the future
  React/Vue front end can render with plotly.js. Plotly is optional
  (`pip install .[charts]`); static export adds kaleido (`.[export]`).
- **Chart colours are validated, not picked by eye.** The 8-slot categorical
  palette passes colour-vision-deficiency, separation and contrast checks in both
  light and dark mode. Each mode has its own steps, not an inversion. Colours follow the
  person (slot = order of first message), never their rank, and a 9th+
  participant folds into "Other" instead of getting a generated colour.
- **Every chart has a data table**, so no value is only readable by hover or colour.

## Adding a platform

1. Create `loaders/<platform>.py` with a class that has `name`, `can_load(path)`
   and `load(path) -> Conversation` (see `loaders/base.py`).
2. Build a frame with the four schema columns and return
   `Conversation.from_frame(frame, title=..., platform=name)`.
3. Register an instance in `LOADERS` in `loaders/__init__.py`.
4. Add fixture-based tests in `tests/test_<platform>_loader.py`.

## Performance

Measured on a synthetic 300,000-message, three-person export (66 MB, 31 files,
mostly non-ASCII text) on a 4-core machine. Reproduce with:

```bash
python benchmarks/generate_sample.py /tmp/bench --messages 300000 --participants 3
python benchmarks/run.py /tmp/bench
```

| Step | Time |
|---|---|
| Load and fix encoding | 0.57 s |
| Full report (every statistic) | 0.22 s |
| Dashboard (every chart, both themes) | 1.04 s |

End to end, including Python start-up, `nostos report` takes about 1.2 s and
`nostos dashboard` about 2.7 s.

Most of the load time is JSON parsing (orjson) plus undoing Messenger's
double-encoded text, which has to happen per string in Python. Parsing files in
parallel worker processes is the next step if that ever matters.
