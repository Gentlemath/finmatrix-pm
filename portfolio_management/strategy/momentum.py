"""Cross-sectional momentum strategy.

The strategy is deliberately **data-source agnostic**: it operates on panels
(``DatetimeIndex`` x security), so the same code runs on synthetic data in
tests and on survivorship-bias-free CRSP data in production.

Signal convention (all configurable):
    At each formation month ``t``, the momentum signal is the cumulative return
    over a window of ``lookback`` months that ends ``gap`` months before ``t``.
    Stocks are ranked into ``n_quantiles`` buckets; the top bucket is the
    "winner" leg. The portfolio is held for the following month (monthly
    rebalance), so returns are lookahead-free.

Defaults give the classic "11-month return, skip the most recent month"
momentum (``lookback=11``, ``gap=1``).
"""

from typing import Optional

import numpy as np
import pandas as pd


class MomentumStrategy:
    """Configurable cross-sectional momentum backtester (monthly rebalance)."""

    def __init__(
        self,
        lookback: int = 11,
        gap: int = 1,
        n_quantiles: int = 10,
        long_short: bool = True,
        weighting: str = "equal",
    ):
        """
        Args:
            lookback: Number of months in the signal window.
            gap: Months skipped between the signal window and the holding month
                (``gap=1`` skips the most recent month to avoid short-term
                reversal).
            n_quantiles: Number of ranking buckets (10 = deciles, 5 = quintiles).
            long_short: If True, go long the top bucket and short the bottom
                bucket. If False, hold only the top bucket (long-only).
            weighting: ``"equal"`` or ``"value"`` (needs a market-cap panel).
        """
        if lookback < 1:
            raise ValueError("lookback must be >= 1.")
        if gap < 0:
            raise ValueError("gap must be >= 0.")
        if n_quantiles < 2:
            raise ValueError("n_quantiles must be >= 2.")
        if weighting not in ("equal", "value"):
            raise ValueError("weighting must be 'equal' or 'value'.")

        self.lookback = lookback
        self.gap = gap
        self.n_quantiles = n_quantiles
        self.long_short = long_short
        self.weighting = weighting

    def compute_signal(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Momentum signal per (month, security): cumulative window return, lagged."""
        gross = 1.0 + returns
        cum = gross.rolling(window=self.lookback, min_periods=self.lookback).apply(
            np.prod, raw=True
        ) - 1.0
        return cum.shift(self.gap)

    def backtest(
        self,
        returns: pd.DataFrame,
        membership: Optional[pd.DataFrame] = None,
        market_caps: Optional[pd.DataFrame] = None,
        return_weights: bool = False,
    ):
        """Run the monthly backtest.

        Args:
            returns: Monthly simple returns panel (DatetimeIndex x security).
            membership: Optional boolean panel; only ``True`` cells are eligible
                at each date (point-in-time index membership).
            market_caps: Market-cap panel, required when ``weighting="value"``.
            return_weights: If True, also return a net-weights panel (formation
                date x security; winners positive, losers negative) for turnover.

        Returns:
            DataFrame indexed by holding month with columns ``long``, ``short``
            (NaN when long-only), and ``strategy``. If ``return_weights`` is True,
            returns ``(result, weights)``.
        """
        if self.weighting == "value" and market_caps is None:
            raise ValueError("market_caps is required when weighting='value'.")

        signal = self.compute_signal(returns)
        dates = signal.index

        records = []
        weight_rows = {}
        for i, date in enumerate(dates):
            if i + 1 >= len(dates):
                continue  # no holding month after the last date
            hold_date = dates[i + 1]  # the month the portfolio actually earns

            sig = signal.loc[date]            # signal is known at formation date
            fwd = returns.loc[hold_date]      # return realized in the holding month
            eligible = sig.notna() & fwd.notna()
            if membership is not None and date in membership.index:
                eligible &= membership.loc[date].reindex(eligible.index).fillna(False)

            sig = sig[eligible]
            fwd = fwd[eligible]
            if len(sig) < self.n_quantiles:
                continue

            buckets = pd.qcut(sig.rank(method="first"), self.n_quantiles, labels=False)
            winners = sig.index[buckets == self.n_quantiles - 1]
            losers = sig.index[buckets == 0]

            long_w = self._leg_weights(winners, market_caps, date)
            long_ret = self._weighted_return(long_w, fwd)
            short_w = None
            if self.long_short:
                short_w = self._leg_weights(losers, market_caps, date)
                short_ret = self._weighted_return(short_w, fwd)
                strat = long_ret - short_ret
            else:
                short_ret = np.nan
                strat = long_ret

            # index by the realized (holding) month so returns align with any
            # benchmark / risk-free series.
            records.append(
                {"date": hold_date, "long": long_ret, "short": short_ret, "strategy": strat}
            )
            if return_weights:
                net = {name: float(w) for name, w in long_w.items()}
                if short_w is not None:
                    for name, w in short_w.items():
                        net[name] = net.get(name, 0.0) - float(w)
                weight_rows[hold_date] = pd.Series(net, dtype=float)

        result = pd.DataFrame(records)
        result = result.set_index("date") if not result.empty else pd.DataFrame(
            columns=["long", "short", "strategy"]
        )

        if return_weights:
            weights = pd.DataFrame(weight_rows).T.sort_index() if weight_rows else pd.DataFrame()
            weights.index.name = "date"
            return result, weights
        return result

    @staticmethod
    def _weighted_return(weights, forward_row) -> float:
        """Weighted forward return of a leg given its weights (NaN if empty)."""
        if len(weights) == 0:
            return np.nan
        return float((weights * forward_row[weights.index].astype(float)).sum())

    def _leg_weights(self, names, market_caps, date) -> pd.Series:
        """Portfolio weights for one leg (equal- or value-weighted)."""
        if len(names) == 0:
            return pd.Series(dtype=float)
        if self.weighting == "equal":
            return pd.Series(1.0 / len(names), index=names)

        caps = market_caps.loc[date].reindex(names).astype(float)
        caps = caps.where(caps > 0)
        if caps.notna().sum() == 0 or caps.sum() == 0:
            return pd.Series(1.0 / len(names), index=names)  # fallback
        return caps.fillna(0.0) / caps.sum()
