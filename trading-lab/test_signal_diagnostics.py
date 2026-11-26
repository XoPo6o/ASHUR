"""Regression tests for the read-only Paper/Shadow signal diagnostics."""
import math

import pandas as pd

import live_shadow_worker as worker


def sample_row():
    return pd.Series({
        "timestamp": 1795651200000,
        "open": 500.0, "high": 510.0, "low": 490.0,
        "close": 505.0, "volume": 1000.0,
        "ema20": 501.0, "ema50": 499.0, "ema100": 495.0,
        "ema200": 490.0, "adx": 24.0, "atr": 8.0,
        "atr_pct": 0.015, "atr_p80": 0.02,
        "keltner_upper": 517.0,
        "dh20": 508.0, "dh55": 512.0, "dh100": 515.0,
        "dl10": 480.0, "dl20": 475.0,
    })


def test_diagnostics_match_existing_signal_decisions_for_all_six_strategies():
    row = sample_row()
    for strategy in worker.STRATEGIES:
        expected = worker.signals(row, strategy["id"])
        diagnostic = worker.signal_diagnostics(row, strategy["id"])
        assert (diagnostic["entry_signal"], diagnostic["exit_signal"]) == expected
        assert diagnostic["entry_signal"] is (len(diagnostic["entry_blockers"]) == 0)
        assert diagnostic["exit_signal"] is (len(diagnostic["exit_triggers"]) > 0)


def test_diagnostics_report_failed_conditions_without_changing_signal():
    row = sample_row()
    row["adx"] = 5.0
    expected = worker.signals(row, "BNB_4H_ADX_TREND")
    diagnostic = worker.signal_diagnostics(row, "BNB_4H_ADX_TREND")
    assert expected[0] is False
    assert "adx_above_20" in diagnostic["entry_blockers"]


def test_non_finite_indicator_values_are_json_safe_nulls():
    row = sample_row()
    row["atr_p80"] = float("nan")
    diagnostic = worker.signal_diagnostics(row, "SOL_4H_DONCHIAN_VOL")
    assert diagnostic["indicators"]["atr_p80"] is None
    assert math.isfinite(diagnostic["indicators"]["close"])
