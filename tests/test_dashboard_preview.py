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

    def test_history_dependent_panels_are_not_faked(self):
        self.assertIn("HISTORY PENDING", HTML)
        self.assertIn("historical snapshot series", HTML)
        self.assertNotIn("NO TRADES YET", HTML)

    def test_offline_feed_is_not_presented_as_current_performance(self):
        self.assertIn("verified starting baseline only", HTML)
        self.assertIn("must not be read as current balances", HTML)
        self.assertIn("Historical equity and drawdown remain unavailable", HTML)

    def test_official_star_mark_and_no_full_page_grid(self):
        self.assertIn('fill="#ffe45c"', HTML)
        self.assertIn('fill="#ff397d"', HTML)
        self.assertIn("radial-gradient(ellipse at 14% 0%", HTML)
        self.assertNotIn("background-size:32px 32px", HTML)
        self.assertNotIn("𒀭", HTML)


if __name__ == "__main__":
    unittest.main()
