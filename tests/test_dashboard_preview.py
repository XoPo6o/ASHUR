import re
import unittest
from pathlib import Path

from dashboard.read_model import STRATEGY_IDS


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "wall-preview.html").read_text(encoding="utf-8")


class DashboardPreviewTests(unittest.TestCase):
    def test_all_six_runtime_strategy_ids_are_wired(self):
        found = set(re.findall(r'data-strategy-id="([^"]+)"', HTML))
        self.assertEqual(found, STRATEGY_IDS)

    def test_preview_uses_same_origin_read_only_feed(self):
        self.assertIn("fetch('/api/dashboard/v1/status'", HTML)
        self.assertIn("cache: 'no-store'", HTML)
        self.assertIn("credentials: 'same-origin'", HTML)
        self.assertIn("window.setInterval(refreshDashboard, 60000)", HTML)
        self.assertIn("fetch('/api/dashboard/v1/history?days=30'", HTML)
        self.assertIn("window.setInterval(refreshHistory, 60000)", HTML)
        self.assertIn('id="top-max-drawdown"', HTML)

    def test_history_dependent_panels_are_not_faked(self):
        self.assertRegex(HTML, r'id="history-status"[^>]*>COLLECTING</span>')
        self.assertIn("function drawEquityChart(points)", HTML)
        self.assertIn("at least two observations in the same UTC day", HTML)
        self.assertIn("No synthetic performance data is displayed", HTML)
        self.assertNotIn("NO TRADES YET", HTML)

    def test_offline_feed_is_not_presented_as_current_performance(self):
        self.assertIn("LAST SNAPSHOT UNAVAILABLE", HTML)
        self.assertIn("may reflect the previous successful snapshot", HTML)
        self.assertIn("must not be treated as current", HTML)
        self.assertIn("Historical analytics are supplied by the separate append-only collector", HTML)

    def test_archive_uses_observed_daily_history_without_fabricated_reports(self):
        self.assertIn('id="archive-heatmap"', HTML)
        self.assertIn('id="archive-reports"', HTML)
        self.assertIn("function renderArchive(daily, anchorTimestamp)", HTML)
        self.assertIn("history.daily || []", HTML)
        self.assertIn("at least two observations required", HTML)
        self.assertIn("No complete daily reports yet.", HTML)
        self.assertNotIn('aria-label="30-day archive has not accumulated daily reports"', HTML)

    def test_rolling_24h_report_is_explicitly_boundary_anchored(self):
        self.assertIn('id="history-24h-pnl"', HTML)
        self.assertIn("history.rolling_24h", HTML)
        self.assertIn("rolling.elapsed_hours", HTML)
        self.assertIn("last validated snapshot at or before the 24-hour boundary", HTML)
        self.assertIn("Not enough data", HTML)

    def test_rolling_24h_metrics_are_not_hidden_by_incomplete_utc_day(self):
        guard = HTML.split("if (history.sample_count < 2 || !latestDay || latestDay.snapshots < 2)", 1)[1]
        guard = guard.split("} else {", 1)[0]
        self.assertNotIn("history-24h-pnl", guard)
        self.assertNotIn("history-24h-realized", guard)
        self.assertIn("history-daily-pnl", guard)

    def test_feed_failures_do_not_mislabel_stale_values_as_baseline(self):
        offline = HTML.split("} catch (error) {", 1)[1].split("  }", 1)[0]
        self.assertIn("LAST SNAPSHOT UNAVAILABLE", offline)
        self.assertIn("may reflect the previous successful snapshot", offline)
        self.assertNotIn("BASELINE PREVIEW · NO LIVE FEED", offline)

    def test_history_failure_resets_rolling_and_intraday_metrics(self):
        history_offline = HTML.split("async function refreshHistory()", 1)[1].split("  refreshHistory();", 1)[0]
        catch = history_offline.split("} catch (error) {", 1)[1]
        for metric_id in ("history-24h-pnl", "history-24h-realized", "history-24h-trades",
                          "history-24h-fees", "history-24h-drawdown", "history-daily-pnl",
                          "history-realized-pnl", "history-daily-trades", "history-daily-fees",
                          "history-intraday-drawdown"):
            self.assertIn(metric_id, catch)

    def test_performance_charts_use_observed_history_payloads(self):
        self.assertIn('id="daily-pnl-chart"', HTML)
        self.assertIn('id="drawdown-chart"', HTML)
        self.assertIn('id="trade-distribution-chart"', HTML)
        self.assertIn("drawDailyPnlChart(history.daily || [])", HTML)
        self.assertIn("drawDrawdownChart(history.equity_curve || [])", HTML)
        self.assertIn("drawTradeDistribution(history.strategy_trade_stats || [])", HTML)
        self.assertIn("at least two validated snapshots in a UTC day", HTML)
        self.assertIn("Open positions are not counted as wins or losses", HTML)

    def test_mobile_touch_navigation_and_accessibility_rules(self):
        self.assertIn("min-height:44px", HTML)
        self.assertIn("overflow-x:auto", HTML)
        self.assertIn("touch-action:pan-x", HTML)
        self.assertIn(":focus-visible", HTML)
        self.assertIn("prefers-reduced-motion:reduce", HTML)
        self.assertIn('aria-live="polite"', HTML)

    def test_official_star_mark_and_no_full_page_grid(self):
        self.assertIn('fill="#ffe45c"', HTML)
        self.assertIn('fill="#ff397d"', HTML)
        self.assertIn("radial-gradient(ellipse at 14% 0%", HTML)
        self.assertNotIn("background-size:32px 32px", HTML)
        self.assertNotIn("𒀭", HTML)


if __name__ == "__main__":
    unittest.main()
