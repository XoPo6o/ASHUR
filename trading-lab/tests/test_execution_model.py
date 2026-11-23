import unittest

from execution_model import (
    adverse_cost_bps,
    adverse_cost_components_bps,
    capacity_limited_fill,
    fill_price,
    participation_rate,
    within_participation_limit,
)


class ExecutionModelTests(unittest.TestCase):
    def test_cost_includes_half_spread_and_base_slippage(self):
        cost = adverse_cost_bps(0.0, 1_000_000, 0.0)
        self.assertAlmostEqual(cost, 3.0)

    def test_cost_increases_with_volatility(self):
        calm = adverse_cost_bps(0.005, 1_000_000, 10_000)
        volatile = adverse_cost_bps(0.02, 1_000_000, 10_000)
        self.assertGreater(volatile, calm)

    def test_cost_increases_with_order_size(self):
        small = adverse_cost_bps(0.01, 1_000_000, 1_000)
        large = adverse_cost_bps(0.01, 1_000_000, 100_000)
        self.assertGreater(large, small)

    def test_buy_is_more_expensive_and_sell_is_worse(self):
        buy = fill_price(100, "buy", 0.01, 1_000_000, 10_000)
        sell = fill_price(100, "sell", 0.01, 1_000_000, 10_000)
        self.assertGreater(buy, 100)
        self.assertLess(sell, 100)

    def test_missing_liquidity_uses_maximum_impact(self):
        cost = adverse_cost_bps(0.01, 0, 10_000)
        self.assertAlmostEqual(cost, 53.0)

    def test_cost_components_sum_to_total(self):
        parts = adverse_cost_components_bps(0.01, 1_000_000, 10_000)
        self.assertAlmostEqual(
            parts["spread_bps"] + parts["base_slippage_bps"] + parts["market_impact_bps"],
            parts["total_bps"],
        )
        self.assertAlmostEqual(parts["spread_bps"], 2.0)
        self.assertAlmostEqual(parts["base_slippage_bps"], 1.0)

    def test_capacity_limited_partial_fill(self):
        result = capacity_limited_fill(50_000, 1_000_000, 0.02)
        self.assertEqual(result["requested_notional"], 50_000)
        self.assertEqual(result["filled_notional"], 20_000)
        self.assertEqual(result["unfilled_notional"], 30_000)
        self.assertAlmostEqual(result["fill_ratio"], 0.4)

    def test_no_liquidity_means_no_fill(self):
        result = capacity_limited_fill(1_000, 0, 0.02)
        self.assertEqual(result["filled_notional"], 0)
        self.assertEqual(result["fill_ratio"], 0)

    def test_participation_limit(self):
        self.assertTrue(within_participation_limit(10_000, 1_000_000))
        self.assertFalse(within_participation_limit(30_000, 1_000_000))
        self.assertEqual(participation_rate(10_000, 1_000_000), 0.01)


if __name__ == "__main__":
    unittest.main()
