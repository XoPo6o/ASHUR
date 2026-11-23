import unittest

from execution_model import (
    adverse_cost_bps,
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

    def test_participation_limit(self):
        self.assertTrue(within_participation_limit(10_000, 1_000_000))
        self.assertFalse(within_participation_limit(30_000, 1_000_000))
        self.assertEqual(participation_rate(10_000, 1_000_000), 0.01)


if __name__ == "__main__":
    unittest.main()
