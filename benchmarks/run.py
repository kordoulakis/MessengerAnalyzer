"""Time loading and the full report on an export folder.

python benchmarks/run.py PATH [--repeat 3]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from nostos import loaders, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    load_times, report_times = [], []
    for _ in range(args.repeat):
        start = time.perf_counter()
        conversation = loaders.load(args.path).in_timezone("UTC")
        load_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        report.to_text(report.build_report(conversation))
        report_times.append(time.perf_counter() - start)

    print(f"messages: {len(conversation):,}")
    print(f"load:   best {min(load_times):.3f}s")
    print(f"report: best {min(report_times):.3f}s")


if __name__ == "__main__":
    main()
