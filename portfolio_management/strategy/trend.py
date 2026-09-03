"""Time-series (trend-following) momentum — an absolute, per-asset strategy.

Distinct from ``MomentumStrategy`` (cross-sectional): there, assets are ranked
*against each other* and the book is dollar-neutral by construction. Here each
asset is judged **against its own past** — long if its own trailing return is
positive, short if negative — so in a broad bull market the book can be long
everything and in a crash short everything. That absolute signal is why
trend-following tends to profit in sustained sell-offs (it flips short as prices
fall), and it is the canonical managed-futures / CTA strategy
(Moskowitz, Ooi & Pedersen, "Time Series Momentum", JFE 2012).

Like the rest of the toolkit the strategy is **data-source agnostic**: it runs on
a returns panel (``DatetimeIndex`` x asset), so the same code serves synthetic
tests and a cached cross-asset ETF panel.

Signal convention (all configurable):
    At formation date ``t`` the signal is the cumulative return over the trailing
    ``lookback`` periods (ending at ``t``, optionally skipping the most recent
    ``gap`` periods). Its **sign** sets the position direction; the portfolio is
    held for the following period, so returns are lookahead-free.

Position sizing:
    ``scale=True`` (default) sizes each asset by inverse ex-ante volatility so
    every asset targets ``target_vol`` annualized risk before being averaged into
    the book — the textbook construction. ``scale=False`` uses the bare sign
    (equal gross weight per active asset), which isolates the trend *signal* from
    the volatility-timing effect.

Signal speed varies by asset class:
    ``lookback`` accepts a dict (asset -> periods) as well as an int, because the
    horizon over which trends persist is NOT the same across markets. Measured on
    35 futures over 1979-2026 and cross-checked on a 10-ETF basket, three speeds
    fall out — and the grouping is NOT the obvious "financials vs commodities":

        slow  (18m)  bonds, PRECIOUS metals
        mid    (9m)  equity indices, FX, REITs
        fast   (3m)  energy, INDUSTRIAL metals, agriculture

    The precious/industrial split inside "metals" is the part that matters and
    the part that is easy to get wrong. Per-market optima: gold 12m and silver
    6m against copper 3m and zinc 3m. Gold is a monetary asset driven by real
    rates and the dollar, so it trends on the same slow macro clock as bonds;
    copper is a consumption commodity whose inventory and supply response
    shortens trends. Bonds are the clearest case of all — 7 of 10 peak at 18m,
    and they are the strongest single markets in the basket (Bund 0.69,
    US 5y 0.70).

    Note this is trend PERSISTENCE, not volatility. Volatility differences are
    already handled by inverse-vol sizing, which is what lets a 1%-vol
    Australian 3-year and 62%-vol natural gas share one book. Group assets by
    how long their trends last, not by how much they move.

    Evidence that this is economic rather than fitted, in increasing order of
    weight:

    1. Falsification. Reversing the speeds (slow assets fast, fast assets slow)
       collapses Sharpe from 0.91 to 0.49 and raises turnover from 2.3x to 4.2x.
       Curve-fitting has no preferred direction.
    2. Independent basket. An earlier two-speed version labelled the split
       "financials slow / commodities fast". That FAILED on the ETF basket
       (0.60 -> 0.56, and the reversed version scored 0.68) because its two
       "commodities" were gold and a 14-commodity index, both of which are slow.
       Regrouping by the three speeds above lifts the same ETF basket to 0.73.
       The failed replication is what produced the correct grouping.
    3. Plateau, not spike. 18/9/3 and 18/9/6 score 0.91 and 0.90.

    The exact month is still not tunable: every asset class changed its precise
    optimum between sample halves. Use the coarse grouping via
    :func:`lookback_by_group`, and blend over neighbouring speeds rather than
    committing to one.

Mixed-frequency volatility:
    The rebalance clock and the volatility clock need not be the same. Estimating
    volatility monthly means a ``vol_window`` of 36 carries three-year-old
    information — far too stale to react to a volatility shock. ``backtest``
    therefore accepts a separate, higher-frequency ``vol_returns`` panel (e.g.
    weekly) used *only* for the risk estimate, while positions still turn over on
    the low-frequency clock. Precision on a second moment scales with the number
    of observations, so this sharpens sizing without adding any turnover.
"""

from typing import Dict, Mapping, Optional, Union

import numpy as np
import pandas as pd


class TimeSeriesMomentum:
    """Configurable time-series momentum / trend-following backtester."""

    def __init__(
        self,
        lookback: Union[int, Dict[str, int]] = 12,
        gap: int = 0,
        vol_window: int = 36,
        target_vol: float = 0.10,
        scale: bool = True,
        long_short: bool = True,
    ):
        """
        Args:
            lookback: Periods in the trailing signal window. Either an int
                (same speed everywhere) or a dict mapping asset name to periods,
                which lets slow and fast markets run at different speeds — see
                :func:`lookback_by_group`. Assets absent from the dict are
                dropped from the signal, so build it with a default.
            gap: Periods skipped between the signal window and the holding period
                (``0`` = use the full trailing window, the trend-following norm).
            vol_window: Window (periods) for the ex-ante volatility estimate used
                to size positions when ``scale=True``.
            target_vol: Annualized volatility each asset is scaled to before being
                averaged into the book (only used when ``scale=True``).
            scale: If True, size positions by inverse ex-ante volatility; if False,
                use the bare sign (equal gross weight per active asset).
            long_short: If True, take short positions on down-trending assets; if
                False, hold only up-trending assets (long-or-flat).
        """
        if isinstance(lookback, dict):
            if not lookback:
                raise ValueError("lookback dict must not be empty.")
            bad = {k: v for k, v in lookback.items() if not (isinstance(v, int) and v >= 1)}
            if bad:
                raise ValueError(f"lookback values must be ints >= 1; got {bad}")
        elif lookback < 1:
            raise ValueError("lookback must be >= 1.")
        if gap < 0:
            raise ValueError("gap must be >= 0.")
        if vol_window < 2:
            raise ValueError("vol_window must be >= 2.")
        if target_vol <= 0:
            raise ValueError("target_vol must be > 0.")

        self.lookback = lookback
        self.gap = gap
        self.vol_window = vol_window
        self.target_vol = target_vol
        self.scale = scale
        self.long_short = long_short

    def compute_signal(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Trailing cumulative return per (date, asset), lagged by ``gap``.

        With a dict ``lookback`` each column uses its own window, so a fast
        commodity and a slow bond can sit in the same panel. Columns missing from
        the dict are returned as all-NaN, which the eligibility test in
        :meth:`backtest` then excludes — silently trading them at some default
        speed would hide a configuration mistake.
        """
        gross = 1.0 + returns
        if not isinstance(self.lookback, dict):
            cum = gross.rolling(window=self.lookback,
                                min_periods=self.lookback).apply(np.prod, raw=True) - 1.0
            return cum.shift(self.gap)

        out = {}
        for col in returns.columns:
            lb = self.lookback.get(col)
            if lb is None:
                out[col] = pd.Series(np.nan, index=returns.index)
                continue
            out[col] = gross[col].rolling(window=lb, min_periods=lb).apply(
                np.prod, raw=True) - 1.0
        return pd.DataFrame(out, index=returns.index).shift(self.gap)

    def _ex_ante_vol(self, returns: pd.DataFrame, periods_per_year: int) -> pd.DataFrame:
        """Annualized rolling volatility per asset, known at each formation date."""
        vol = returns.rolling(
            window=self.vol_window, min_periods=max(2, self.vol_window // 2)
        ).std()
        return vol * np.sqrt(periods_per_year)

    def _aligned_vol(
        self,
        returns: pd.DataFrame,
        periods_per_year: int,
        vol_returns: Optional[pd.DataFrame],
        vol_periods_per_year: Optional[int],
    ) -> pd.DataFrame:
        """Ex-ante volatility evaluated on the formation dates of ``returns``.

        Without ``vol_returns`` this is just the same-frequency estimate. With it,
        volatility is estimated on the (higher-frequency) panel and then carried
        forward to each formation date using only observations dated on or before
        that date — so the alignment introduces no look-ahead.
        """
        if vol_returns is None:
            return self._ex_ante_vol(returns, periods_per_year)
        if vol_periods_per_year is None:
            raise ValueError(
                "vol_periods_per_year is required when vol_returns is supplied "
                "(e.g. 52 for weekly, 252 for daily)."
            )
        vol = self._ex_ante_vol(vol_returns, vol_periods_per_year)
        vol = vol.reindex(columns=returns.columns)
        # last estimate at or before each formation date (no look-ahead)
        merged = vol.reindex(vol.index.union(returns.index)).sort_index().ffill()
        return merged.reindex(returns.index)

    def backtest(
        self,
        returns: pd.DataFrame,
        periods_per_year: int = 12,
        return_weights: bool = False,
        vol_returns: Optional[pd.DataFrame] = None,
        vol_periods_per_year: Optional[int] = None,
    ):
        """Run the trend-following backtest.

        Args:
            returns: Simple returns panel (DatetimeIndex x asset), one row per
                rebalance period (monthly or daily).
            periods_per_year: 12 for monthly, 252 for daily — annualizes the vol
                estimate so ``target_vol`` is interpreted per year.
            return_weights: If True, also return a net-weights panel (holding date
                x asset) for turnover / transaction-cost analysis.
            vol_returns: Optional higher-frequency returns panel used *only* for
                the ex-ante volatility estimate (e.g. weekly returns while
                rebalancing monthly). ``vol_window`` is then counted in periods of
                *this* panel. Trading still happens on ``returns``' clock, so
                turnover is unchanged.
            vol_periods_per_year: Annualization factor for ``vol_returns``
                (52 weekly, 252 daily). Required when ``vol_returns`` is given.

        Returns:
            DataFrame indexed by holding period with columns ``strategy`` (net
            return), ``long`` and ``short`` (signed contribution of each side), and
            ``gross`` (gross exposure). With ``return_weights``, returns
            ``(result, weights)``.
        """
        signal = self.compute_signal(returns)
        direction = np.sign(signal)                 # +1 / -1 / 0 per asset
        if not self.long_short:
            direction = direction.clip(lower=0.0)   # long-or-flat
        vol = (self._aligned_vol(returns, periods_per_year,
                                 vol_returns, vol_periods_per_year)
               if self.scale else None)

        dates = returns.index
        records, weight_rows = [], {}
        for i, date in enumerate(dates):
            if i + 1 >= len(dates):
                continue                            # no holding period after the last row
            hold_date = dates[i + 1]

            dir_row = direction.loc[date]
            fwd = returns.loc[hold_date]
            eligible = dir_row.notna() & (dir_row != 0.0) & fwd.notna()
            if self.scale:
                v = vol.loc[date]
                eligible &= v.notna() & (v > 0.0)
            if eligible.sum() == 0:
                continue

            names = dir_row.index[eligible]
            if self.scale:
                raw = dir_row[names] * (self.target_vol / vol.loc[date][names])
            else:
                raw = dir_row[names]
            w = raw / len(names)                    # average the vol-scaled positions

            contrib = w * fwd[names].astype(float)
            long_ret = float(contrib[w > 0].sum())
            short_ret = float(contrib[w < 0].sum())
            records.append({
                "date": hold_date,
                "strategy": long_ret + short_ret,
                "long": long_ret,
                "short": short_ret,
                "gross": float(w.abs().sum()),
            })
            if return_weights:
                weight_rows[hold_date] = w.astype(float)

        cols = ["strategy", "long", "short", "gross"]
        result = (pd.DataFrame(records).set_index("date")
                  if records else pd.DataFrame(columns=cols))

        if return_weights:
            weights = (pd.DataFrame(weight_rows).T.sort_index()
                       if weight_rows else pd.DataFrame())
            weights.index.name = "date"
            return result, weights
        return result


#: Metals whose trends run on the slow macro clock rather than the commodity
#: clock. Gold optimises at 12m and silver at 6m against copper's and zinc's 3m:
#: they are priced off real rates and the dollar, not off inventory. Getting this
#: split wrong is what made the first version of the grouping fail on a second
#: basket — see the module docstring.
PRECIOUS_METALS = frozenset({"GOLD", "SILVER", "GLD", "SLV", "XAU", "XAG"})


def speed_group(asset: str, asset_class: str) -> str:
    """Which trend-speed group an asset belongs to: ``slow``, ``mid`` or ``fast``.

    The grouping measured best on both a 35-futures and a 10-ETF basket. Pair it
    with :data:`TREND_SPEEDS` via :func:`lookback_by_group`.

    Args:
        asset: the market's name, checked against :data:`PRECIOUS_METALS`.
        asset_class: one of ``bond``, ``equity``, ``fx``, ``energy``, ``metal``,
            ``ag``. Anything unrecognised falls to ``fast``, which is the
            commodity default.
    """
    if asset_class == "bond" or asset.upper() in PRECIOUS_METALS:
        return "slow"
    if asset_class in ("equity", "fx"):
        return "mid"
    return "fast"


#: Lookback periods (months) that measured best per speed group on both the
#: 35-futures and 10-ETF baskets. See the module docstring for the grouping and
#: the evidence. Treat as a starting point, not a tuned optimum: 18/9/6 scores
#: within 0.01 of 18/9/3, and the exact month is not stable across sample halves.
TREND_SPEEDS = {"slow": 18, "mid": 9, "fast": 3}


def lookback_by_group(
    group_of: Mapping[str, str],
    speeds: Mapping[str, int],
    default: Optional[int] = None,
) -> Dict[str, int]:
    """Build an asset -> lookback dict from a group map and a speed per group.

    Args:
        group_of: asset name -> group name (e.g. ``{"BUND": "bond", ...}``).
        speeds: group name -> lookback periods.
        default: lookback for assets whose group has no speed. ``None`` raises
            instead, so a market that silently falls through is caught rather
            than traded at an arbitrary speed.

    The grouping that measured best on both baskets (see the module docstring)
    splits metals by monetary vs industrial, which a plain asset-class map does
    not do — so build the group map for speed, not for reporting::

        PRECIOUS = {"GOLD", "SILVER"}

        def speed_group(asset, asset_class):
            if asset_class == "bond" or asset in PRECIOUS:
                return "slow"                       # rate-cycle clock
            if asset_class in ("equity", "fx"):
                return "mid"
            return "fast"                           # inventory / supply response

        groups = {a: speed_group(a, cls[a]) for a in cls}
        lb = lookback_by_group(groups, TREND_SPEEDS)
        TimeSeriesMomentum(lookback=lb).backtest(returns, ...)
    """
    out, missing = {}, []
    for asset, grp in group_of.items():
        if grp in speeds:
            out[asset] = int(speeds[grp])
        elif default is not None:
            out[asset] = int(default)
        else:
            missing.append((asset, grp))
    if missing:
        raise ValueError(
            f"no speed for {len(missing)} asset(s) and no default: "
            f"{missing[:5]}{' ...' if len(missing) > 5 else ''}")
    return out


def trend_signal_table(
    returns: pd.DataFrame,
    lookback: int = 12,
    gap: int = 0,
) -> Optional[pd.DataFrame]:
    """Convenience: the signed trend direction (+1/-1/0) per (date, asset).

    Useful for inspecting *what the strategy is positioned in* over time
    (e.g. "risk-on vs risk-off" counts) without running a full backtest.
    """
    tsm = TimeSeriesMomentum(lookback=lookback, gap=gap)
    return np.sign(tsm.compute_signal(returns))
