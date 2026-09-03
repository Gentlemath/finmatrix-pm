"""Performance analytics for strategy return series.

All functions take **per-period** returns (e.g. monthly) and an optional
**per-period** risk-free rate ``rf`` (scalar or a Series aligned to the returns).
Set ``periods_per_year`` to annualize (12 for monthly, 252 for daily).

Note on the risk-free rate: a self-financing long-short portfolio is already an
excess return, so leave ``rf=0`` for it. A long-only portfolio should use the
real ``rf`` — otherwise its Sharpe is inflated by the risk-free rate.
"""

from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd

Number = Union[float, pd.Series]


def _per_period_rf(rf: Number, index: pd.Index) -> pd.Series:
    """Broadcast a scalar rf, or align an rf Series, to ``index``."""
    if isinstance(rf, pd.Series):
        return rf.reindex(index).fillna(0.0)
    return pd.Series(float(rf), index=index)


def max_drawdown(returns: pd.Series) -> float:
    """Worst peak-to-trough decline of the cumulative return (<= 0)."""
    r = returns.dropna()
    if r.empty:
        return float("nan")
    cum = (1 + r).cumprod()
    return float((cum / cum.cummax() - 1).min())


def performance_summary(
    returns: pd.Series,
    rf: Number = 0.0,
    periods_per_year: int = 12,
) -> dict:
    """Headline stats: annualized return/vol, (excess) Sharpe, max drawdown, cumulative."""
    r = returns.dropna()
    if r.empty:
        return {"periods": 0, "ann_return": float("nan"), "ann_vol": float("nan"),
                "sharpe": float("nan"), "max_drawdown": float("nan"),
                "cumulative": float("nan")}

    excess = r - _per_period_rf(rf, r.index)
    ann_vol = r.std() * np.sqrt(periods_per_year)
    return {
        "periods": len(r),
        "ann_return": (1 + r).prod() ** (periods_per_year / len(r)) - 1,
        "ann_vol": ann_vol,
        "sharpe": (excess.mean() * periods_per_year) / ann_vol if ann_vol else float("nan"),
        "max_drawdown": max_drawdown(r),
        "cumulative": (1 + r).prod() - 1,
    }


def capm(
    returns: pd.Series,
    benchmark: pd.Series,
    rf: Number = 0.0,
    periods_per_year: int = 12,
) -> dict:
    """CAPM-style stats of ``returns`` vs a ``benchmark`` (both per-period).

    Returns beta, annualized alpha, R^2, tracking error, and information ratio.
    """
    df = pd.concat([returns.rename("r"), benchmark.rename("b")], axis=1).dropna()
    if len(df) < 2:
        return {"beta": float("nan"), "alpha_annual": float("nan"), "r_squared": float("nan"),
                "tracking_error": float("nan"), "information_ratio": float("nan")}

    rf_s = _per_period_rf(rf, df.index)
    er, eb = df["r"] - rf_s, df["b"] - rf_s
    beta = er.cov(eb) / eb.var() if eb.var() else float("nan")
    alpha_period = er.mean() - beta * eb.mean()

    active = df["r"] - df["b"]
    te = active.std() * np.sqrt(periods_per_year)
    return {
        "beta": beta,
        "alpha_annual": alpha_period * periods_per_year,
        "r_squared": er.corr(eb) ** 2,
        "tracking_error": te,
        "information_ratio": (active.mean() * periods_per_year) / te if te else float("nan"),
    }


def turnover(weights: pd.DataFrame, periods_per_year: int = 12) -> dict:
    """Average one-way turnover from a weights panel (dates x securities).

    One-way turnover at each rebalance is ``0.5 * sum |w_t - w_{t-1}|`` on target
    weights (drift within a period is ignored). Returns the per-rebalance average
    and its annualized value.
    """
    w = weights.sort_index().fillna(0.0)
    if len(w) < 2:
        return {"avg_one_way": float("nan"), "annualized": float("nan")}
    one_way = 0.5 * w.diff().abs().sum(axis=1).iloc[1:]
    avg = float(one_way.mean())
    return {"avg_one_way": avg, "annualized": avg * periods_per_year}


def transaction_costs(weights: pd.DataFrame, cost: float = 0.0010) -> pd.Series:
    """Per-rebalance proportional trading cost from a net-weights panel.

    ``cost`` is the per-dollar cost of trading **one side** (e.g. 0.0010 = 10 bps).
    Dollars traded at each rebalance is ``sum |w_t - w_{t-1}|`` (two-way turnover,
    counting both buys and sells); the first row is charged for establishing the
    initial book. Returns a per-period cost Series aligned to the weights index.
    """
    w = weights.sort_index().fillna(0.0)
    if w.empty:
        return pd.Series(dtype=float)
    traded = w.diff().abs().sum(axis=1)
    traded.iloc[0] = w.iloc[0].abs().sum()  # establishing the initial position
    return (cost * traded).rename("cost")


def apply_costs(
    gross_returns: pd.Series,
    weights: pd.DataFrame,
    cost: float = 0.0010,
) -> pd.Series:
    """Net return series: ``gross - transaction cost`` at each rebalance.

    ``gross_returns`` and ``weights`` share the formation-date index (as returned
    by ``MomentumStrategy.backtest(..., return_weights=True)``).
    """
    costs = transaction_costs(weights, cost).reindex(gross_returns.index).fillna(0.0)
    return (gross_returns - costs).rename("net")


def volatility_target(
    gross_returns: pd.Series,
    weights: pd.DataFrame,
    target_vol: float,
    periods_per_year: int = 12,
    window: int = 36,
    min_periods: Optional[int] = None,
    max_leverage: float = 10.0,
    cost: float = 0.0010,
) -> Tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Scale a strategy to a constant ex-ante volatility target.

    Position sizing that targets risk *per asset* leaves the book's own
    volatility wherever the correlations put it — and because a weight of
    ``sign x (target/vol_i) / n`` shrinks as ``n`` grows, adding markets quietly
    lowers portfolio risk. A 35-market futures book runs at ~4% annualised
    volatility where a 10-market ETF book runs at ~5%. Portfolio volatility
    should be a decision, not a by-product of basket size.

    Leverage each period is ``target_vol / trailing_vol``, using an estimate that
    ends **one period before** the period it sizes, so no future information
    enters. The estimate comes from the strategy's own unlevered net returns,
    which keeps it a fixed reference rather than a circular function of the
    leverage being solved for.

    **Costs.** The naive implementation multiplies the net return series by
    leverage. That correctly scales the strategy's own trading costs but misses
    the cost of *changing leverage*: moving from 5.50x to 5.38x is itself a
    trade. This function instead scales the weights and re-costs them, so
    ``sum |w_t - w_{t-1}|`` is computed on the levered book and the rebalancing
    of leverage is charged exactly.

    Note that Sharpe is **not** invariant here. Scaling by a constant cannot
    change it, but scaling by a time-varying factor can: leverage rises when
    volatility is low, which adds a volatility-timing effect on top of the
    strategy. Measured on the futures trend book that is worth about +0.05
    Sharpe. Attribute it to the timing, not to the leverage.

    Args:
        gross_returns: per-period strategy returns before costs.
        weights: the net-weights panel that produced them, same index.
        target_vol: annualised volatility to target (e.g. 0.15).
        periods_per_year: 12 for monthly, 252 for daily.
        window: periods in the trailing volatility estimate.
        min_periods: minimum observations before sizing starts; defaults to
            ``window // 2``. Earlier periods are dropped, not sized at 1x.
        max_leverage: hard cap. Calm stretches can imply absurd gearing, and a
            cap is the difference between a backtest and a fantasy.
        cost: per-side proportional trading cost.

    Returns:
        ``(net, leverage, levered_weights)``.
    """
    if target_vol <= 0:
        raise ValueError("target_vol must be > 0.")
    if max_leverage <= 0:
        raise ValueError("max_leverage must be > 0.")

    w = weights.sort_index()
    gross = gross_returns.sort_index()
    base_net = apply_costs(gross, w, cost=cost)

    mp = window // 2 if min_periods is None else min_periods
    est = base_net.rolling(window, min_periods=mp).std() * np.sqrt(periods_per_year)
    lev = (target_vol / est.replace(0.0, np.nan)).shift(1).clip(upper=max_leverage)
    lev = lev.reindex(w.index)

    keep = lev.notna()
    lev = lev[keep]
    lw = w.loc[lev.index].mul(lev, axis=0)
    net = apply_costs(gross.loc[lev.index] * lev, lw, cost=cost)
    return net.rename("net"), lev.rename("leverage"), lw


def cap_weighted_return(
    returns: pd.DataFrame,
    market_caps: pd.DataFrame,
    membership: Optional[pd.DataFrame] = None,
) -> pd.Series:
    """Value-weighted return of the (member) universe -- an index-like benchmark.

    Weights each stock by its prior-period market cap (restricted to members if a
    membership panel is given), so month ``t`` earns lagged-cap-weighted returns.
    """
    caps = market_caps.copy()
    if membership is not None:
        caps = caps.where(membership.reindex_like(caps).fillna(False))
    weights = caps.shift(1)
    weights = weights.div(weights.sum(axis=1), axis=0)
    return (weights * returns).sum(axis=1, min_count=1)
