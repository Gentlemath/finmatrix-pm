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

            names = dir_row.index[eligible]  # tradble assets
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
#: FROZEN. This is the list as it stood when GROUPING_V1 was learned, and it is
#: deliberately incomplete: platinum is a precious metal, trends like one, and is
#: NOT here. It is added in GROUPING_V2's own overrides instead (see there).
#:
#: The reason is not that editing this would disturb v1 results -- the v1 basket
#: holds no platinum, so on that data the edit changes nothing at all. It is that
#: GROUPING_V1 serves as the BASELINE in every v2 comparison, standing for "a
#: prior fixed before the current data and untouched since".
#:
#: "Independent" would be too strong and was used too loosely at first. This
#: grouping was chosen on the v1 full sample -- the v1 research log records the
#: search: a two-speed split was tried, it failed to replicate on the ETF
#: basket, and it was changed to three speeds. So on v1 data it is contaminated
#: outright, and on v2 it is only partly clean: 20 markets and the years
#: 1973-1979 are genuinely new to it, while the other 30 markets over 1979-2026
#: were visible when it was chosen. What it has over a per-window refit is far
#: FEWER passes over the data, not zero.
#: Adding platinum because v2 data suggests it would inject v2 information into
#: the very baseline used to test whether injecting v2 information helps, and
#: §10.3 of the v2 research log -- learning loses to not-learning on all three
#: panels -- rests on that baseline being clean. Measured: the edit moves the
#: v1-grouping baseline on v2 data from 0.821 to 0.744.
#:
#: So the name is inaccurate on purpose. Read it as "the precious-metal overrides
#: v1 shipped with", not as a definition of the term.
PRECIOUS_METALS = frozenset({"GOLD", "SILVER", "GLD", "SLV", "XAU", "XAG"})


#: The grouping learned on the 35-market futures basket and the 10-ETF basket.
#: A grouping is DATA, not code: ``by_asset`` overrides ``by_class``, and
#: ``default`` catches anything unlisted (``None`` raises instead, which is what
#: a grouping intended to be exhaustive should use). Keeping it as a value means
#: a re-learned grouping, and the reversed grouping used to falsify it, are
#: alternative values of one mechanism rather than three copies of a function.
GROUPING_V1 = {
    "by_asset": {m: "slow" for m in PRECIOUS_METALS},
    "by_class": {"bond": "slow", "equity": "mid", "fx": "mid",
                 "energy": "fast", "metal": "fast", "ag": "fast"},
    "default": "fast",
}


#: The v1 grouping with its one hole filled. ``livestock`` was absent from the
#: class map, so cattle and hogs fell to the commodity default of 3 months --
#: where their trend Sharpe is NEGATIVE (-0.01 at 3m, 0.05 at 6m, against 0.21
#: at 9m). Moving them off 3m lifts the walk-forward out-of-sample Sharpe of the
#: whole basket from 0.88 to 0.91, and 9m, 12m and 18m all give the same 0.91:
#: the gain is in leaving 3m, not in locating an optimum. Two markets move the
#: portfolio that much because they are its least correlated -- lean hogs has a
#: mean |correlation| of 0.063 to the rest against a basket average of 0.184 --
#: so their marginal contribution per unit of weight is unusually high.
#:
#: ``slow`` rather than a fourth speed keeps the set at 18/9/3.
#:
#: ``default`` is None so that an unlisted asset class RAISES. Livestock's three
#: decades in the wrong bucket were the cost of a silent fallback, and the next
#: new class should be a question rather than a commodity.
#: Platinum, added here rather than to PRECIOUS_METALS. The v1 basket contains
#: no platinum, so editing that frozenset would change nothing on v1 data -- but
#: GROUPING_V1 is also the baseline for every v2 comparison, and on v2 data the
#: edit moves it from 0.821 to 0.744. See the note on PRECIOUS_METALS.
#:
#: The evidence is the SHAPE of its lookback profile, not an argmax whose margin
#: (0.05) is inside the noise. Platinum's 12-month Sharpe exceeds its 3-month by
#: +0.15, ahead of silver's +0.12, while all four base metals fall between -0.15
#: and +0.03. Its profile correlates +0.70 with gold and silver and only +0.22
#: with the base metals -- which themselves correlate -0.17 with gold and silver.
#:
#: Palladium, before it was dropped on liquidity, tilted the other way at -0.04,
#: matching a demand base that is roughly 85% autocatalyst against platinum's
#: 40%. Behaviour and demand structure agree on both metals.
#:
#: Portfolio impact is nil: walk-forward out-of-sample Sharpe is 0.90 with
#: platinum fast and 0.89-0.90 at every slower speed. This is a consistency
#: change, made because the override exists to hold metals that trend slowly and
#: platinum is one, not because it pays.
GROUPING_V2 = {
    "by_asset": {**{m: "slow" for m in PRECIOUS_METALS}, "PLATINUM": "slow"},
    "by_class": {"bond": "slow", "livestock": "slow",
                 "equity": "mid", "fx": "mid",
                 "energy": "fast", "metal": "fast", "ag": "fast"},
    "default": None,
}


def speed_group(asset: str, asset_class: str,
                grouping: Optional[Dict] = None) -> str:
    """Which trend-speed group an asset belongs to: ``slow``, ``mid`` or ``fast``.

    Pair it with :data:`TREND_SPEEDS` via :func:`lookback_by_group`.

    Args:
        asset: the market's name, matched case-insensitively against the
            grouping's ``by_asset`` overrides.
        asset_class: ``bond``, ``equity``, ``fx``, ``energy``, ``metal``,
            ``ag``, ... looked up in ``by_class``.
        grouping: a grouping dict; defaults to :data:`GROUPING_V1`, which was
            learned on a 35-market basket that had no livestock and no platinum
            or palladium. Pass a different one rather than editing this, so that
            earlier results stay reproducible.

    Raises:
        KeyError: if the class is unlisted and the grouping sets no ``default``.
            An exhaustive grouping should prefer that to silently defaulting --
            an unlisted class is a question, not a commodity.
    """
    g = grouping if grouping is not None else GROUPING_V1
    hit = g.get("by_asset", {}).get(asset.upper())
    if hit is not None:
        return hit
    by_class = g.get("by_class", {})
    if asset_class in by_class:
        return by_class[asset_class]
    default = g.get("default")
    if default is None:
        raise KeyError(
            f"asset_class {asset_class!r} (asset {asset!r}) is not in this "
            f"grouping and it sets no default; add it explicitly")
    return default


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
