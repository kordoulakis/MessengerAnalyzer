from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from nostos.charts import CHARTS, ChartOptions, chart_page
from nostos.charts.figures import MAX_SERIES, OTHER, build, kept_senders, sender_colors
from nostos.charts.html import table_html
from nostos.charts.theme import DARK, LIGHT
from nostos.loaders.messenger import MessengerLoader
from nostos.schema import Conversation

from .conftest import ms, write_export


@pytest.mark.parametrize("theme", [LIGHT, DARK], ids=["light", "dark"])
@pytest.mark.parametrize("name", sorted(CHARTS))
def test_every_chart_builds_in_both_themes(conversation: Conversation, name: str, theme) -> None:  # type: ignore[no-untyped-def]
    chart = build(conversation, name, ChartOptions(), theme)
    assert chart.figure.layout.paper_bgcolor == theme.surface
    assert chart.table.height > 0
    assert chart.title


def test_colours_follow_the_person_not_the_rank(conversation: Conversation) -> None:
    colors = sender_colors(conversation, LIGHT)
    # Conversation order: Ana first, Βασίλης second, though Βασίλης sends more.
    assert colors["Ana"] == LIGHT.series[0]
    assert colors["Βασίλης"] == LIGHT.series[1]
    dark = sender_colors(conversation, DARK)
    assert dark["Ana"] == DARK.series[0]


def test_monthly_by_participant_uses_identity_colours(conversation: Conversation) -> None:
    chart = build(conversation, "monthly", ChartOptions(by_sender=True), LIGHT)
    assert {t.name: t.marker.color for t in chart.figure.data} == {
        "Ana": LIGHT.series[0],
        "Βασίλης": LIGHT.series[1],
        "Cam": LIGHT.series[2],
    }


@pytest.fixture
def big_group(tmp_path: Path) -> Conversation:
    # 12 people; person i sends i + 1 messages, so the quietest fold into "Other".
    messages = [
        {
            "sender_name": f"P{i:02d}",
            "timestamp_ms": ms(2021, 1, 1 + j % 28, i, j % 60),
            "content": "hi",
        }
        for i in range(12)
        for j in range(i + 1)
    ]
    return MessengerLoader().load(write_export(tmp_path / "group", [messages]))


def test_large_groups_fold_into_other(big_group: Conversation) -> None:
    kept = kept_senders(big_group)
    assert len(kept) == MAX_SERIES - 1
    assert "P11" in kept
    assert "P00" not in kept
    chart = build(big_group, "monthly", ChartOptions(by_sender=True), LIGHT)
    names = [t.name for t in chart.figure.data]
    assert names[-1] == OTHER
    assert len(names) == MAX_SERIES
    total = sum(sum(t.y) for t in chart.figure.data)
    assert total == len(big_group)


def test_share_sums_to_100(conversation: Conversation) -> None:
    chart = build(conversation, "share", ChartOptions(), LIGHT)
    by_period = chart.table.select(pl.sum_horizontal(pl.exclude("period")).alias("total"))
    assert by_period["total"].to_list() == pytest.approx([100.0, 100.0])


def test_rhythm_is_7_by_24(conversation: Conversation) -> None:
    heatmap = build(conversation, "rhythm", ChartOptions(), LIGHT).figure.data[0]
    assert len(heatmap.z) == 7
    assert all(len(row) == 24 for row in heatmap.z)
    assert sum(map(sum, heatmap.z)) == len(conversation)


def test_end_labels_only_for_a_few_lines(
    conversation: Conversation, big_group: Conversation
) -> None:
    few = build(conversation, "words", ChartOptions(by_sender=True), LIGHT).figure
    assert {a.text for a in few.layout.annotations} <= set(conversation.participants)
    many = build(big_group, "activity", ChartOptions(by_sender=True), LIGHT).figure
    assert not many.layout.annotations


def test_page_escapes_chat_content(tmp_path: Path) -> None:
    evil = "</script><script>alert(1)</script>"
    folder = write_export(
        tmp_path / "x",
        [
            [
                {"sender_name": evil, "timestamp_ms": ms(2021, 1, 1), "content": "hi"},
                {"sender_name": "B", "timestamp_ms": ms(2021, 1, 2), "content": "yo"},
            ]
        ],
        title=evil,
    )
    page = chart_page(MessengerLoader().load(folder), "participants", ChartOptions())
    assert "<script>alert(1)" not in page


def test_table_html_formats_values() -> None:
    frame = pl.DataFrame({"name": ["<b>"], "count": [1234], "mean": [1.5], "none": [None]})
    html = table_html(frame)
    assert "&lt;b&gt;" in html
    assert "1,234" in html
    assert "1.50" in html
    assert "–" in html
