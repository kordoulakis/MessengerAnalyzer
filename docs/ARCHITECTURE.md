# Architecture

```
            ┌───────────────┐   Conversation    ┌────────────┐  tables / scalars  ┌──────────────┐
 export ──▶ │   loaders/    │ ────────────────▶ │  analysis/ │ ─────────────────▶ │ report.py    │──▶ text / JSON
            │ messenger.py  │  (schema.py)      │ pure funcs │                    │ charts/      │──▶ html / png
            │ instagram.py  │                   └────────────┘                    └──────────────┘
            │ whatsapp.py   │
            └───────────────┘
                                                                                         ▲
                                                       cli.py: parses flags, wires the layers together
```

Each layer only depends on the ones to its left.

| Module | Responsibility | Must not |
|---|---|---|
| `schema.py` | The canonical `Conversation`: a Polars frame with `timestamp` (tz-aware), `sender`, `text`, `kind` | know about any platform |
| `loaders/` | Turn one platform's export into a `Conversation`. Registry and format detection in `loaders/__init__.py` | compute statistics |
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
- **One canonical schema.** Each platform is a loader that outputs the same four
  columns; analysis, report, plots and CLI never see platform differences.
- **Timezone is applied once.** Loaders emit UTC; `Conversation.in_timezone()`
  converts before analysis, so "messages per hour" means the user's local hours.
  WhatsApp writes local times with no zone, so its loader reads them in the zone
  passed as `load(path, timezone=...)` (the CLI passes `--tz`), which shows them
  exactly as the phone did.
- **Platforms are told apart by content, not by flags.** `loaders.detect()` asks
  each loader in `LOADERS` order whether it recognises a path. Instagram and
  Messenger share Meta's JSON format, so Instagram goes first and looks for the
  `your_instagram_activity` download folder or traces only Instagram leaves
  (reaction notices, `original_content_owner`); Messenger is the fallback. WhatsApp
  files are recognised by their first lines. `--platform` overrides detection.
- **Platform noise is removed in the loader.** Instagram's "Reacted 😂 to your
  message" notices and WhatsApp's encryption and group notices are not messages, so
  loaders drop them rather than leaving every analysis to filter them out.
- **Tidy outputs.** Per-participant results are long tables
  (`period, sender, messages`), which serialize directly to JSON for a future
  web front end; plotting pivots them as needed.
- **Data and presentation are separate.** `build_report()` returns plain data;
  `to_text()` / `to_json()` render it. A web API can return `build_report()`
  as-is.
- **Local-only, enforced.** Nothing makes network requests: pages inline
  plotly.js, image export runs kaleido with MathJax disabled, and
  `tests/test_offline.py` fails if any command opens a connection or a page
  references a remote resource.
- **Interactive charts with Plotly.** Pages are self-contained HTML. The figure
  JSON is the same format the future React/Vue front end can render with
  plotly.js. Static image export is the optional `export` extra (kaleido).
- **Chart colours are validated, not picked by eye.** The 8-slot categorical
  palette passes colour-vision-deficiency, separation and contrast checks in both
  light and dark mode. Each mode has its own steps, not an inversion. Colours follow the
  person (slot = order of first message), never their rank, and a 9th+
  participant folds into "Other" instead of getting a generated colour.
- **Every chart has a data table**, so no value is only readable by hover or colour.

## Adding a platform

1. Create `loaders/<platform>.py` with a class that has `name`, `can_load(path)`
   and `load(path, *, timezone=None) -> Conversation` (see `loaders/base.py`).
   `timezone` only matters if the export stores times without a zone.
2. Build a frame with the four schema columns and return
   `Conversation.from_frame(frame, title=..., platform=name)`.
3. Register an instance in `LOADERS` in `loaders/__init__.py`. Order matters for
   detection: put it before any loader that would also accept its exports.
4. Add tests in `tests/test_<platform>_loader.py` with small, hand-written
   fixtures. Never copy real chats into tests.

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

These numbers are for Messenger; Instagram uses the same parser.
Most of the load time is JSON parsing (orjson) plus undoing Messenger's
double-encoded text, which has to happen per string in Python. Parsing files in
parallel worker processes is the next step if that ever matters.

WhatsApp exports are parsed line by line in Python: about 3.3 s for 300,000
messages on the same machine, well under a second for typical chats. Vectorising
the header parsing with Polars string expressions is the next step if that matters.
