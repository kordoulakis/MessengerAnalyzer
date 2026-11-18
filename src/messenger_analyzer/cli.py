"""Command-line interface: ``msganalyzer {list,report,plot,charts}``."""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from messenger_analyzer import __version__, loaders
from messenger_analyzer.analysis import UNITS
from messenger_analyzer.loaders import LoaderError
from messenger_analyzer.schema import Conversation

DEFAULT_SOURCES = Path("MessagesSources")

_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*$", re.IGNORECASE)
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "": 60}


def parse_duration(text: str) -> timedelta:
    """'90s', '30m', '6h', '2d'; a bare number means minutes."""
    match = _DURATION.match(text)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid duration {text!r} (examples: 30m, 6h, 2d)")
    value, unit = match.groups()
    return timedelta(seconds=float(value) * _DURATION_UNITS[unit.lower()])


def parse_keywords(text: str) -> tuple[str, ...]:
    words = tuple(w.strip() for w in text.split(",") if w.strip())
    if not words:
        raise argparse.ArgumentTypeError("expected comma-separated words, e.g. hello,world")
    return words


def parse_timezone(text: str) -> str:
    try:
        ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"unknown timezone {text!r}") from exc
    return text


def local_timezone() -> str:
    try:
        from tzlocal import get_localzone_name

        name = get_localzone_name()
    except Exception:  # tzlocal can fail on unusual systems; UTC is a safe default
        return "UTC"
    return name or "UTC"


def resolve_source(source: str, sources_dir: Path) -> Path:
    """A path to an export folder, or the name of a folder inside ``sources_dir``."""
    direct = Path(source).expanduser()
    if direct.is_dir():
        return direct
    candidate = sources_dir / source
    if candidate.is_dir():
        return candidate
    raise LoaderError(
        f"{source!r} is not a folder, nor a folder inside {sources_dir}/. "
        "Run 'msganalyzer list' to see what is available."
    )


def _load(args: argparse.Namespace) -> Conversation:
    path = resolve_source(args.source, args.sources)
    started = time.perf_counter()
    conversation = loaders.load(path, args.platform).in_timezone(args.tz)
    if args.verbose:
        print(
            f"Loaded {len(conversation):,} messages from {path} in "
            f"{time.perf_counter() - started:.2f}s (timezone {args.tz})",
            file=sys.stderr,
        )
    return conversation


def cmd_list(args: argparse.Namespace) -> int:
    if not args.sources.is_dir():
        print(f"No sources folder at {args.sources}/", file=sys.stderr)
        return 1
    folders = sorted(p for p in args.sources.iterdir() if p.is_dir())
    found = False
    for folder in folders:
        platform = next((ld.name for ld in loaders.LOADERS if ld.can_load(folder)), None)
        if platform:
            found = True
            print(f"{folder.name}\t({platform})")
    if not found:
        print(f"No conversations found in {args.sources}/", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from messenger_analyzer import report

    conversation = _load(args)
    started = time.perf_counter()
    data = report.build_report(
        conversation, top=args.top, keywords=args.keywords or (), max_gap=args.max_gap
    )
    output = report.to_json(data) if args.format == "json" else report.to_text(data)
    if args.verbose:
        print(f"Analysed in {time.perf_counter() - started:.2f}s", file=sys.stderr)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


def _plotting() -> ModuleType:
    try:
        from messenger_analyzer import plotting
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise LoaderError(
            "Plotting needs matplotlib: pip install 'messenger-analyzer[plot]'"
        ) from exc
    return plotting


def cmd_charts(args: argparse.Namespace) -> int:
    for name, (description, _) in _plotting().CHARTS.items():
        print(f"{name:<18} {description}")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    plotting = _plotting()
    if args.chart not in plotting.CHARTS:
        raise LoaderError(f"Unknown chart {args.chart!r}. Run 'msganalyzer charts' for the list.")
    conversation = _load(args)
    options = plotting.ChartOptions(
        by_sender=args.by_participant or args.separate,
        separate=args.separate,
        keywords=args.keywords or (),
        case_sensitive=args.case_sensitive,
        unit=args.unit,
        max_gap=args.max_gap,
    )
    if args.output:
        from matplotlib.figure import Figure

        fig = plotting.render(conversation, args.chart, options, Figure(figsize=plotting.FIGSIZE))
        fig.savefig(args.output, dpi=args.dpi)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        import matplotlib.pyplot as plt

        plotting.render(conversation, args.chart, options, plt.figure(figsize=plotting.FIGSIZE))
        plt.show()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="msganalyzer", description="Statistics and charts for chat exports."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sources = argparse.ArgumentParser(add_help=False)
    sources.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="folder holding one sub-folder per conversation (default: %(default)s)",
    )

    common = argparse.ArgumentParser(add_help=False, parents=[sources])
    common.add_argument("source", help="conversation folder, or its name inside --sources")
    common.add_argument(
        "--platform",
        choices=[ld.name for ld in loaders.LOADERS],
        help="export format (default: detect)",
    )
    common.add_argument(
        "--tz",
        type=parse_timezone,
        default=local_timezone(),
        help="IANA timezone for dates and hours, e.g. Europe/Athens (default: this machine's)",
    )
    common.add_argument(
        "--max-gap",
        type=parse_duration,
        help="ignore response times longer than this (e.g. 6h); they are usually new conversations",
    )
    common.add_argument("--keywords", type=parse_keywords, help="comma-separated words")
    common.add_argument("-v", "--verbose", action="store_true", help="print timings to stderr")

    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("list", parents=[sources], help="list conversations in the sources folder")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("report", parents=[common], help="print every statistic")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("-o", "--output", type=Path, help="write to a file instead of stdout")
    p.add_argument(
        "--top", type=int, default=5, help="entries in top-N lists (default: %(default)s)"
    )
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("charts", help="list available charts")
    p.set_defaults(func=cmd_charts)

    p = sub.add_parser("plot", parents=[common], help="draw a chart")
    p.add_argument("chart", help="chart name; see 'msganalyzer charts'")
    p.add_argument(
        "-o", "--output", type=Path, help="save to an image (png, svg, pdf) instead of showing"
    )
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--by-participant", action="store_true", help="one series per participant")
    p.add_argument("--separate", action="store_true", help="one panel per participant (daily)")
    p.add_argument("--case-sensitive", action="store_true", help="match --keywords exactly")
    p.add_argument("--unit", choices=list(UNITS), default="minutes", help="unit for response times")
    p.set_defaults(func=cmd_plot)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except LoaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
