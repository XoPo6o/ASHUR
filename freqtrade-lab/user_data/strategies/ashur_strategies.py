"""Freqtrade ports of ASHUR's six PAPER_ONLY baseline strategies."""
from datetime import datetime
from pandas import DataFrame
import numpy as np
import talib.abstract as ta

from freqtrade.strategy import IStrategy, stoploss_from_absolute, timeframe_to_prev_date


class AshurBase(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    startup_candle_count = 999
    minimal_roi = {}
    stoploss = -0.15
    use_custom_stoploss = True
    trailing_stop = False
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    timeframe = "15m"

    RISK_FRACTION = 0.005
    HARD_STOP_FRACTION = 0.15
    COST_PER_SIDE = 0.0015  # 0.10% fee + 0.05% slippage estimate.

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 24,
             "trade_limit": 2, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 96,
             "trade_limit": 4, "stop_duration_candles": 24,
             "max_allowed_drawdown": 0.02},
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for n in (20, 50, 100, 200):
            dataframe[f"ema{n}"] = ta.EMA(dataframe, timeperiod=n)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        for n in (20, 55, 100):
            dataframe[f"dh{n}"] = dataframe["high"].rolling(n).max().shift(1)
        dataframe["dl10"] = dataframe["low"].rolling(10).min().shift(1)
        dataframe["dl20"] = dataframe["low"].rolling(20).min().shift(1)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["atr_p80"] = dataframe["atr_pct"].rolling(100, min_periods=50).quantile(0.80)
        dataframe["keltner_upper"] = dataframe["ema20"] + 2.0 * dataframe["atr"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        for n in (20, 60, 120):
            dataframe[f"ret{n}"] = dataframe["close"].pct_change(n)
        # Causal Supertrend(10, 3) state; no future candles are referenced.
        mid = (dataframe["high"].to_numpy() + dataframe["low"].to_numpy()) / 2.0
        upper = mid + 3.0 * dataframe["atr"].to_numpy()
        lower = mid - 3.0 * dataframe["atr"].to_numpy()
        close = dataframe["close"].to_numpy()
        final_upper = np.full(len(dataframe), np.nan)
        final_lower = np.full(len(dataframe), np.nan)
        direction = np.zeros(len(dataframe), dtype=int)
        for i in range(len(dataframe)):
            if not np.isfinite(upper[i]) or not np.isfinite(lower[i]):
                continue
            if i == 0 or not np.isfinite(final_upper[i - 1]):
                final_upper[i], final_lower[i] = upper[i], lower[i]
                direction[i] = 1 if close[i] >= mid[i] else -1
                continue
            final_upper[i] = min(upper[i], final_upper[i - 1]) if close[i - 1] <= final_upper[i - 1] else upper[i]
            final_lower[i] = max(lower[i], final_lower[i - 1]) if close[i - 1] >= final_lower[i - 1] else lower[i]
            prior = direction[i - 1]
            if prior <= 0 and close[i] > final_upper[i]:
                direction[i] = 1
            elif prior >= 0 and close[i] < final_lower[i]:
                direction[i] = -1
            else:
                direction[i] = prior
        dataframe["supertrend_dir"] = direction
        return dataframe

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs
    ) -> float:
        """Conservative size: worst-case 15% stop plus two-sided estimated costs <=0.5% equity."""
        equity = float(self.wallets.get_total_stake_amount())
        if not np.isfinite(equity) or equity <= 0 or current_rate <= 0:
            return 0
        risk_per_unit = self.HARD_STOP_FRACTION + 2 * self.COST_PER_SIDE
        desired = equity * self.RISK_FRACTION / risk_per_unit
        stake = min(desired, float(max_stake) * 0.95, equity * 0.95)
        if min_stake is not None and stake < float(min_stake):
            return 0
        return max(0.0, stake)

    def _entry_atr(self, pair: str, trade) -> float | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        entry_time = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        candles = dataframe.loc[dataframe["date"] <= entry_time]
        if candles.empty:
            return None
        value = float(candles.iloc[-1]["atr"])
        return value if np.isfinite(value) and value > 0 else None

    def custom_stoploss(
        self, pair: str, trade, current_time: datetime, current_rate: float,
        current_profit: float, after_fill: bool, **kwargs
    ) -> float | None:
        """Use a 3-ATR stop; the strategy-level -15% stop remains the hard ceiling."""
        atr = self._entry_atr(pair, trade)
        if atr is None:
            return None
        stop_price = trade.open_rate - 3.0 * atr
        if stop_price <= 0 or stop_price >= current_rate:
            return None
        return stoploss_from_absolute(
            stop_price, current_rate=current_rate, is_short=False, leverage=trade.leverage
        )

    def custom_exit(
        self, pair: str, trade, current_time: datetime, current_rate: float,
        current_profit: float, **kwargs
    ) -> str | None:
        """Take profit at 4R, with R defined by the entry 3-ATR stop or 15% hard cap."""
        atr = self._entry_atr(pair, trade)
        if atr is None:
            return None
        risk_distance = min(3.0 * atr, self.HARD_STOP_FRACTION * trade.open_rate)
        if current_rate >= trade.open_rate + 4.0 * risk_distance:
            return "atr_4r_target"
        return None


class BNB_15M_EMA_TREND(AshurBase):
    timeframe = "15m"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] > dataframe["ema20"]) &
             (dataframe["ema20"] > dataframe["ema50"]) &
             (dataframe["adx"] > 12) & (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "ema20_50_adx12")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] < dataframe["ema50"]) |
             (dataframe["ema20"] < dataframe["ema50"])) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "ema_trend_lost")
        return dataframe


class BNB_1H_DONCHIAN_ADX25(AshurBase):
    timeframe = "1h"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        votes = ((dataframe["close"] > dataframe["dh20"]).astype(int) +
                 (dataframe["close"] > dataframe["dh55"]).astype(int) +
                 (dataframe["close"] > dataframe["dh100"]).astype(int))
        c = ((votes >= 2) & (dataframe["close"] > dataframe["ema200"]) &
             (dataframe["adx"] > 25) & (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "donchian_votes_adx25")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] < dataframe["dl20"]) |
             (dataframe["close"] < dataframe["ema100"])) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "donchian_or_ema_exit")
        return dataframe


class BNB_4H_ADX_TREND(AshurBase):
    timeframe = "4h"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["ema50"] > dataframe["ema200"]) &
             (dataframe["adx"] > 20) & (dataframe["close"] > dataframe["ema50"]) &
             (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "ema50_200_adx20")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["ema50"] < dataframe["ema200"]) |
             (dataframe["close"] < dataframe["ema50"])) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "adx_trend_lost")
        return dataframe


class BNB_4H_KELTNER_ADX(AshurBase):
    timeframe = "4h"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] > dataframe["keltner_upper"]) &
             (dataframe["ema50"] > dataframe["ema200"]) &
             (dataframe["adx"] > 15) & (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "keltner_breakout_adx15")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] < dataframe["ema20"]) |
             (dataframe["ema50"] < dataframe["ema200"])) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "keltner_trend_lost")
        return dataframe


class SOL_4H_DONCHIAN_VOL(AshurBase):
    timeframe = "4h"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] > dataframe["dh55"]) &
             (dataframe["close"] > dataframe["ema200"]) &
             (dataframe["atr_pct"] < dataframe["atr_p80"]) &
             (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "donchian55_low_vol")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] < dataframe["dl20"]) |
             (dataframe["close"] < dataframe["ema100"])) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "donchian_vol_exit")
        return dataframe


class BNB_1D_DONCHIAN55(AshurBase):
    timeframe = "1d"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = ((dataframe["close"] > dataframe["dh55"]) &
             (dataframe["close"] > dataframe["ema200"]) &
             (dataframe["volume"] > 0))
        dataframe.loc[c, ["enter_long", "enter_tag"]] = (1, "donchian55_daily")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = (dataframe["close"] < dataframe["dl10"]) & (dataframe["volume"] > 0)
        dataframe.loc[c, ["exit_long", "exit_tag"]] = (1, "donchian10_exit")
        return dataframe


def _set_entry(dataframe: DataFrame, condition, tag: str) -> DataFrame:
    valid = condition.fillna(False) & (dataframe["volume"] > 0)
    dataframe.loc[valid, ["enter_long", "enter_tag"]] = (1, tag)
    return dataframe


def _set_exit(dataframe: DataFrame, condition, tag: str) -> DataFrame:
    valid = condition.fillna(False) & (dataframe["volume"] > 0)
    dataframe.loc[valid, ["exit_long", "exit_tag"]] = (1, tag)
    return dataframe


class ASHUR_TIME_SERIES_MOMENTUM_60(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_entry(dataframe, (dataframe["ret60"] > 0) & (dataframe["close"] > dataframe["ema200"]), "momentum_60_ema200")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["ret20"] < 0) | (dataframe["close"] < dataframe["ema100"]), "momentum_lost")


class ASHUR_DONCHIAN_55_TREND(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_entry(dataframe, (dataframe["close"] > dataframe["dh55"]) & (dataframe["close"] > dataframe["ema200"]), "donchian55_ema200")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, dataframe["close"] < dataframe["dl10"], "donchian10_exit")


class ASHUR_SUPERTREND_10_3(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prior = dataframe["supertrend_dir"].shift(1)
        return _set_entry(dataframe, (dataframe["supertrend_dir"] > 0) & (prior <= 0), "supertrend_flip_long")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, dataframe["supertrend_dir"] < 0, "supertrend_flip_short")


class ASHUR_BULL_REGIME_MEAN_REVERSION(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prior = dataframe["rsi"].shift(1)
        return _set_entry(dataframe, (dataframe["close"] > dataframe["ema200"]) & (prior < 30) & (dataframe["rsi"] >= 30), "rsi_reclaim_30")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["rsi"] > 60) | (dataframe["close"] < dataframe["ema50"]), "mean_reversion_exit")


class ASHUR_MULTI_HORIZON_MOMENTUM(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        votes = ((dataframe["ret20"] > 0).astype(int) + (dataframe["ret60"] > 0).astype(int))
        return _set_entry(dataframe, (votes >= 2) & (dataframe["close"] > dataframe["ema200"]), "multi_horizon_momentum")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["ret20"] < 0) | (dataframe["close"] < dataframe["ema100"]), "momentum_lost")


class ASHUR_DONCHIAN_ENSEMBLE_20_55_100(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        votes = ((dataframe["close"] > dataframe["dh20"]).astype(int) +
                 (dataframe["close"] > dataframe["dh55"]).astype(int) +
                 (dataframe["close"] > dataframe["dh100"]).astype(int))
        return _set_entry(dataframe, (votes >= 2) & (dataframe["close"] > dataframe["ema200"]), "donchian_ensemble")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["close"] < dataframe["dl20"]) | (dataframe["close"] < dataframe["ema100"]), "donchian_ensemble_exit")


class ASHUR_DONCHIAN_COST_AWARE_025(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        votes = ((dataframe["close"] > dataframe["dh20"]).astype(int) +
                 (dataframe["close"] > dataframe["dh55"]).astype(int) +
                 (dataframe["close"] > dataframe["dh100"]).astype(int))
        distance = dataframe["close"] / dataframe["dh20"] - 1.0
        return _set_entry(dataframe, (votes >= 2) & (dataframe["close"] > dataframe["ema200"]) & (distance > 0.0025), "donchian_cost_filter")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["close"] < dataframe["dl20"]) | (dataframe["close"] < dataframe["ema100"]), "donchian_ensemble_exit")


class ASHUR_TREND_PULLBACK_RSI40(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prior = dataframe["rsi"].shift(1)
        return _set_entry(dataframe, (dataframe["ema50"] > dataframe["ema200"]) & (prior < 40) & (dataframe["rsi"] >= 40) & (dataframe["close"] > dataframe["ema50"]), "trend_pullback_rsi40")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["rsi"] < 45) | (dataframe["close"] < dataframe["ema100"]), "trend_pullback_exit")


class ASHUR_TRIPLE_HORIZON_MOMENTUM(AshurBase):
    timeframe = "4h"
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        votes = ((dataframe["ret20"] > 0).astype(int) +
                 (dataframe["ret60"] > 0).astype(int) +
                 (dataframe["ret120"] > 0).astype(int))
        return _set_entry(dataframe, (votes >= 2) & (dataframe["close"] > dataframe["ema200"]), "triple_horizon_momentum")
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return _set_exit(dataframe, (dataframe["ret20"] < 0) | (dataframe["close"] < dataframe["ema100"]), "triple_momentum_exit")
