"""Cross-asset trend following: what the strategy is and what it does.

Runs the recommended construction end to end and shows the two design choices
that matter most. Findings and their evidence live in
``docs/trend-research-log.md``; this is the short version you can run.

    python examples/trend_demo.py

The recommended construction, in one line:

    speeds blended per asset class (slow 12+18, mid 9+12, fast 3+6),
    inverse-volatility sizing off daily returns, monthly rebalance, long/short

See also:
    trend_speed_demo.py      why the speed grouping matters
    trend_portfolio_demo.py  how to size it, and what it adds to a portfolio
"""

import numpy as np
import pandas as pd
from _trend_data import load_basket

from portfolio_management.strategy import (
    TREND_SPEEDS, TimeSeriesMomentum, lookback_by_group, speed_group)
from portfolio_management.strategy.performance import (
    apply_costs, capm, performance_summary, turnover)

COST = 0.0002          # 2 bps/side, realistic for liquid futures
BLEND = {"slow": (12, 18), "mid": (9, 12), "fast": (3, 6)}


def run(m, hf, ppy, lookback, cost=COST, scale=True, **kw):
    """One backtest -> (net returns, gross returns, weights)."""
    tsm = TimeSeriesMomentum(lookback=lookback, vol_window=126 if ppy == 252 else 52,
                             scale=scale, **kw)
    res, w = tsm.backtest(m, periods_per_year=12, return_weights=True,
                          vol_returns=hf, vol_periods_per_year=ppy if hf is not None else None)
    return apply_costs(res["strategy"], w, cost=cost), res["strategy"], w


def blended(m, hf, ppy, groups, **kw):
    """Average the weight panels of the per-group speed variants.

    Blending is averaging, not selecting: every slow asset ends up holding half
    its 12-month signal and half its 18-month signal, permanently.
    """
    panels, idx = [], None
    for i in (0, 1):
        lb = lookback_by_group(groups, {g: v[i] for g, v in BLEND.items()})
        _, _, w = run(m, hf, ppy, lb, **kw)
        panels.append(w)
        idx = w.index if idx is None else idx.intersection(w.index)
    cols = panels[0].columns
    W = sum(p.reindex(index=idx, columns=cols).fillna(0.0) for p in panels) / len(panels)
    gross = (W * m.reindex(index=idx, columns=cols)).sum(axis=1)
    return apply_costs(gross, W, cost=COST), gross, W


def show(label, net, w):
    s = performance_summary(net, periods_per_year=12)
    print(f"  {label:<34}{s['sharpe']:>6.2f}{s['sharpe'] * np.sqrt(len(net) / 12):>6.2f}"
          f"{s['ann_return'] * 100:>8.1f}%{s['ann_vol'] * 100:>7.1f}%"
          f"{s['max_drawdown'] * 100:>9.1f}%{turnover(w)['annualized']:>7.1f}x")


def main() -> None:
    m, hf, ppy, cls, name = load_basket()
    groups = {a: speed_group(a, cls.get(a, "?")) for a in m.columns}
    counts = pd.Series(groups).value_counts()
    print(f"{name}: {m.shape[0]} months x {m.shape[1]} markets, "
          f"{m.index.min():%Y-%m} .. {m.index.max():%Y-%m}")
    print("speed groups: " + ", ".join(f"{g} {counts.get(g, 0)}" for g in ("slow", "mid", "fast"))
          + f"   (slow {TREND_SPEEDS['slow']}m / mid {TREND_SPEEDS['mid']}m "
            f"/ fast {TREND_SPEEDS['fast']}m single-speed)\n")

    print(f"  {'construction':<34}{'SR':>6}{'t':>6}{'ret':>9}{'vol':>7}{'maxDD':>10}{'turn':>7}")
    print("  -- the recommended construction --")
    net, _, w = blended(m, hf, ppy, groups, long_short=True)
    show("blended speeds, long/short", net, w)

    print("  -- what each design choice is worth --")
    uni, _, w_uni = run(m, hf, ppy, 12, long_short=True)
    show("uniform 12m (no speed grouping)", uni, w_uni)
    sign, _, w_sign = run(m, hf, ppy, 12, long_short=True, scale=False)
    show("no inverse-vol sizing (sign only)", sign, w_sign)
    flat, _, w_flat = blended(m, hf, ppy, groups, long_short=False)
    show("long-or-flat (no short leg)", flat, w_flat)

    # crisis alpha: the short leg is what turns a hedge into a payoff
    def by_year(x):
        return (1 + x).groupby(x.index.year).prod() - 1

    a, b = by_year(net), by_year(flat)
    print("\n  equity-stress years: long/short vs long-or-flat")
    for y in (1980, 1987, 1990, 1998, 2002, 2008, 2020, 2022):
        if y in a.index and y in b.index:
            print(f"    {y}   {a[y] * 100:+7.1f}%   {b[y] * 100:+7.1f}%")
    print("  (long-or-flat can only step aside; only the short leg profits when"
          "\n   stocks and bonds fall together — 1980, 2008, 2022)")

    if "SPY" in m.columns:
        c = capm(net, m["SPY"].reindex(net.index), periods_per_year=12)
        print(f"\n  vs SPY: beta {c['beta']:+.2f}, annual alpha {c['alpha_annual'] * 100:+.1f}%")

    print("\n  Returns look small because portfolio volatility is only "
          f"{performance_summary(net, periods_per_year=12)['ann_vol'] * 100:.1f}% —"
          "\n  a leverage choice, not a property of the strategy. "
          "See trend_portfolio_demo.py")


if __name__ == "__main__":
    main()
