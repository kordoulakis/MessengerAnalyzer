from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from nostos.charts import CHARTS
from nostos.cli import main, parse_duration

from .conftest import ms, write_export


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
def test_every_chart_writes_html(chart: str, export_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / f"{chart}.html"
    assert main(["plot", str(export_dir), chart, "-o", str(out), "--tz", "UTC"]) == 0
    page = out.read_text(encoding="utf-8")
    assert f'id="chart-{chart}"' in page
    assert '"light":' in page
    assert '"dark":' in page


@pytest.mark.parametrize(
    "flags", [["--by-participant"], ["--keywords", "hello"], ["--window", "3"]]
)
@pytest.mark.parametrize(
    "chart", ["activity", "monthly", "response-times", "response-trend", "words"]
)
def test_chart_variants(chart: str, flags: list[str], export_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.html"
    assert main(["plot", str(export_dir), chart, "-o", str(out), *flags]) == 0


def test_dashboard(export_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "d.html"
    assert (
        main(["dashboard", str(export_dir), "-o", str(out), "--tz", "UTC", "--theme", "dark"]) == 0
    )
    page = out.read_text(encoding="utf-8")
    assert '<html lang="en" data-theme="dark">' in page
    assert page.count('class="card') == len(CHARTS)
    assert "Typical reply" in page
    assert "loads nothing from the internet" in page


def test_unknown_chart(export_dir: Path) -> None:
    assert main(["plot", str(export_dir), "pie"]) == 2


def test_unavailable_chart_is_a_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_export(
        tmp_path / "solo", [[{"sender_name": "A", "timestamp_ms": ms(2021, 1, 1), "content": "hi"}]]
    )
    assert main(["plot", str(folder), "share", "-o", str(tmp_path / "s.html")]) == 2
    assert "two participants" in capsys.readouterr().err


def test_png_export(export_dir: Path, tmp_path: Path) -> None:
    pytest.importorskip("kaleido")
    out = tmp_path / "monthly.png"
    code = main(["plot", str(export_dir), "monthly", "-o", str(out), "--by-participant"])
    if code != 0:
        pytest.skip("kaleido could not find a Chrome browser")
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
