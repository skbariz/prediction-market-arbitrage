from datetime import datetime, timezone

from prediction_arb.detector import evaluate_pair
from prediction_arb.report import escape_md, render_markdown
from prediction_arb.scanner import ScanResult
from tests.conftest import make_pair


def test_escape_md_neutralizes_untrusted_titles():
    hostile = "Win? | [click](https://evil.example) <script>alert(1)</script>\n# heading"
    escaped = escape_md(hostile, max_len=500)
    assert "|" not in escaped.replace("\\|", "")
    assert "](" not in escaped
    assert "<script>" not in escaped
    assert "\n" not in escaped


def test_escape_md_breaks_autolinks_and_mentions():
    escaped = escape_md("Visit https://evil.example or WWW.evil.example, ask @someone", max_len=500)
    assert "://" not in escaped
    assert "www." not in escaped.lower()
    assert "@s" not in escaped and "@\u200bs" in escaped


def test_escape_md_truncates():
    assert escape_md("x" * 100, max_len=10) == "x" * 9 + "…"


def test_render_with_opportunity(settings):
    pair = make_pair(0.40, 0.62, 0.57, 0.45)
    opp = evaluate_pair(pair, settings)
    result = ScanResult([pair.kalshi], [pair.polymarket], [pair], [opp])
    md = render_markdown(result, settings, now=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc))

    assert "**Last updated:** 2026-01-02 03:04 UTC" in md
    assert "## 1 opportunity" in md
    assert f"| {opp.contracts} |" in md
    assert "Matched pairs: 1" in md


def test_render_without_opportunities(settings):
    md = render_markdown(ScanResult([], [], [], []), settings)
    assert "## No opportunities right now" in md
    assert "| *none* |" in md
