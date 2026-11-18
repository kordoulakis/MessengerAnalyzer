from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from messenger_analyzer.cli import main, parse_duration
from messenger_analyzer.plotting import CHARTS


def test_parse_duration() -> None:
    assert parse_duration("90s") == timedelta(seconds=90)
    assert parse_duration("6h") == timedelta(hours=6)
    assert parse_duration("15") == timedelta(minutes=15)


def test_list(export_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--sources", str(export_dir.parent)]) == 0
    assert "chat\t(messenger)" in capsys.readouterr().out


def test_report_text_by_name(export_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["report", "chat", "--sources", str(export_dir.parent), "--tz", "UTC"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Total messages: 8" in out
    assert "Βασίλης: 4 (50.0%)" in out
    assert "Busiest month: 2020-01 with 4 messages" in out


def test_report_json_to_file(export_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    args = ["report", str(export_dir), "--format", "json", "-o", str(out), "--tz", "UTC"]
    assert main([*args, "--keywords", "hello,nope", "--max-gap", "1h"]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total_messages"] == 8
    assert data["span_days"] == 33
    assert data["response_time"]["mean_seconds"] == 180.0
    assert data["keywords"] == [{"word": "hello", "count": 3}, {"word": "nope", "count": 0}]


def test_missing_source_is_a_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["report", "nope", "--sources", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("chart", sorted(CHARTS))
def test_every_chart_renders(chart: str, export_dir: Path, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    out = tmp_path / f"{chart}.png"
    assert main(["plot", str(export_dir), chart, "-o", str(out), "--tz", "UTC", "--dpi", "40"]) == 0
    assert out.stat().st_size > 0


@pytest.mark.parametrize("flags", [["--by-participant"], ["--separate"], ["--keywords", "hello"]])
def test_chart_variants(flags: list[str], export_dir: Path, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    out = tmp_path / "x.png"
    assert main(["plot", str(export_dir), "daily", "-o", str(out), "--dpi", "40", *flags]) == 0
    assert main(["plot", str(export_dir), "monthly", "-o", str(out), "--dpi", "40", *flags]) == 0


def test_unknown_chart(export_dir: Path) -> None:
    assert main(["plot", str(export_dir), "pie"]) == 2
