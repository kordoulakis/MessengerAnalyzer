# Architecture

```
            ┌───────────────┐   Conversation    ┌────────────┐  tables / scalars  ┌──────────────┐
 export ──▶ │   loaders/    │ ────────────────▶ │  analysis/ │ ─────────────────▶ │ report.py    │──▶ text / JSON
 folder     │ messenger.py  │  (schema.py)      │ pure funcs │                    │ plotting.py  │──▶ png / window
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
| `plotting.py` | One function per chart, drawing onto a supplied matplotlib `Figure` | use global pyplot state |
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
- **matplotlib is optional** (`pip install .[plot]`), so the core library and
  `report` command stay light.

## Adding a platform

1. Create `loaders/<platform>.py` with a class that has `name`, `can_load(path)`
   and `load(path) -> Conversation` (see `loaders/base.py`).
2. Build a frame with the four schema columns and return
   `Conversation.from_frame(frame, title=..., platform=name)`.
3. Register an instance in `LOADERS` in `loaders/__init__.py`.
4. Add fixture-based tests in `tests/test_<platform>_loader.py`.

## Performance

Measured on a synthetic 300,000-message, two-person export (65 MB, 30 files,
mostly non-ASCII text) on a 4-core machine. Reproduce with:

```bash
python benchmarks/generate_sample.py /tmp/bench --messages 300000
python benchmarks/run.py /tmp/bench
```

| Step | v1 (`main.py`) | v2 |
|---|---|---|
| Load + fix encoding | 0.58 s | 0.57 s |
| Full report | 2.30 s | 0.21 s |

Loading is now the bottleneck, and most of it is JSON parsing (orjson) plus
undoing Messenger's double-encoded text, which has to happen per string in
Python. Parsing files in parallel worker processes is the next step if that
ever matters.
