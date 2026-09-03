"""Sizing trend following, and what it adds to an equity portfolio.

    python examples/trend_portfolio_demo.py

Two things this demo exists to correct, because both are easy to get wrong:

  1. "The returns are tiny." They are, as built -- because weights are
     sign x (target_vol / vol_i) / n, so portfolio volatility FALLS as markets
     are added. That is a construction artifact, not a property of the strategy.
     Volatility should be targeted explicitly.

  2. "Its Sharpe is not high, so who cares." Standalone Sharpe is the wrong
     test for a leg whose beta is about -0.2. What matters is the marginal
     contribution to a portfolio -- and that depends on the leg being LEVERED.
     Unlevered, a 40% allocation gives up a third of the return.

Full numbers and caveats: docs/trend-research-log.md
"""

import numpy as np
import pandas as pd
from _trend_data import load_basket, load_equity_benchmark

from portfolio_management.strategy import (
    TimeSeriesMomentum, lookback_by_group, speed_group, volatility_target)
from portfolio_management.strategy.performance import (
    apply_costs, capm, performance_summary, turnover)

COST = 0.0002
BLEND = {"slow": (12, 18), "mid": (9, 12), "fast": (3, 6)}
RF_ANNUAL = 0.018          # rough average cash rate over the ETF overlap
MARGIN_RATE = 0.05         # futures initial margin as a share of notional


def build(m, hf, ppy, groups):
    """The recommended construction -> (gross returns, weights)."""
    panels, idx = [], None
    for i in (0, 1):
        lb = lookback_by_group(groups, {g: v[i] for g, v in BLEND.items()})
        tsm = TimeSeriesMomentum(lookback=lb, vol_window=126 if ppy == 252 else 52,
                                 scale=True, long_short=True)
        _, w = tsm.backtest(m, periods_per_year=12, return_weights=True,
                            vol_returns=hf,
                            vol_periods_per_year=ppy if hf is not None else None)
        panels.append(w)
        idx = w.index if idx is None else idx.intersection(w.index)
    cols = panels[0].columns
    W = sum(p.reindex(index=idx, columns=cols).fillna(0.0) for p in panels) / len(panels)
    return (W * m.reindex(index=idx, columns=cols)).sum(axis=1), W


def sharpe(x, rf_annual=0.0):
    return (x - rf_annual / 12).mean() / x.std() * np.sqrt(12)


def main() -> None:
    m, hf, ppy, cls, name = load_basket()
    groups = {a: speed_group(a, cls.get(a, "?")) for a in m.columns}
    gross, W = build(m, hf, ppy, groups)
    unlev = apply_costs(gross, W, cost=COST)
    print(f"{name}: {m.index.min():%Y-%m} .. {m.index.max():%Y-%m}\n")

    # ---- 1. the return level is a leverage choice -------------------------
    print("=== 1. Volatility targeting: same strategy, different size ===")
    s0 = performance_summary(unlev, periods_per_year=12)
    print(f"  {'target':<16}{'SR':>7}{'ann.ret':>10}{'realised vol':>14}"
          f"{'maxDD':>9}{'median lev':>12}")
    print(f"  {'none (as built)':<16}{s0['sharpe']:>7.2f}{s0['ann_return'] * 100:>9.1f}%"
          f"{s0['ann_vol'] * 100:>13.1f}%{s0['max_drawdown'] * 100:>8.1f}%"
          f"{W.abs().sum(axis=1).median():>11.1f}x")
    levered = {}
    for target in (0.10, 0.15, 0.20):
        net, lev, lw = volatility_target(gross, W, target, cost=COST)
        levered[target] = (net, lev, lw)
        s = performance_summary(net, periods_per_year=12)
        print(f"  {f'{int(target * 100)}% vol':<16}{s['sharpe']:>7.2f}"
              f"{s['ann_return'] * 100:>9.1f}%{s['ann_vol'] * 100:>13.1f}%"
              f"{s['max_drawdown'] * 100:>8.1f}%{lev.median():>11.1f}x")
    print("  Return scales linearly; Sharpe barely moves. The small rise comes")
    print("  from the rescaling itself leaning in when the book is calm --")
    print("  volatility timing, not leverage. A constant multiple cannot change")
    print("  Sharpe at all; only a time-varying one can.")

    # ---- 2. marginal contribution, levered vs not ------------------------
    spy = load_equity_benchmark()
    if spy is None:
        print("\n(no cached SPY series -- run cache_etf_data_av.py for the"
              " portfolio section)")
        return
    net15, lev15, lw15 = levered[0.15]
    gross_exp = lw15.abs().sum(axis=1).median()

    print("\n=== 2. Added to equities: the leverage is the precondition ===")
    for label, leg, exp in [("trend leg UNLEVERED", unlev, W.abs().sum(axis=1).median()),
                            ("trend leg at 15% vol target", net15, gross_exp)]:
        j = pd.concat([leg.rename("T"), spy.rename("S")], axis=1).dropna()
        print(f"\n  {label} (leg vol {j['T'].std() * np.sqrt(12) * 100:.1f}%, "
              f"{exp:.1f}x notional per unit of leg capital)")
        print(f"    {'mix':<24}{'SR':>7}{'ann.ret':>10}{'vol':>8}{'maxDD':>9}"
              f"{'notional':>10}{'margin':>9}")
        for wt in (0.0, 0.2, 0.4):
            mix = (1 - wt) * j["S"] + wt * j["T"]
            s = performance_summary(mix, periods_per_year=12)
            notional = (1 - wt) + wt * exp
            margin = wt * exp * MARGIN_RATE
            tag = "100% SPY" if wt == 0 else f"{int((1 - wt) * 100)}/{int(wt * 100)} SPY/trend"
            print(f"    {tag:<24}{sharpe(mix, RF_ANNUAL * (1 - wt)):>7.2f}"
                  f"{s['ann_return'] * 100:>9.1f}%{s['ann_vol'] * 100:>7.1f}%"
                  f"{s['max_drawdown'] * 100:>8.1f}%{notional:>9.1f}x{margin * 100:>8.0f}%")

    print("\n  Unlevered, 40% in trend gives up a third of the return: a")
    print("  3-4% volatility leg cannot contribute enough risk to matter, so the")
    print("  portfolio is mostly equities plus cash. Levered to 15%, the return")
    print("  is unchanged and the drawdown halves. That is the result worth")
    print("  having -- and it is a claim about the LEVERED leg.")
    j = pd.concat([net15.rename("T"), spy.rename("S")], axis=1).dropna()
    c = capm(j["T"], j["S"], periods_per_year=12)
    print(f"\n  What makes it work: beta {c['beta']:+.2f}, "
          f"correlation {j['T'].corr(j['S']):+.2f}, "
          f"turnover {turnover(lw15)['annualized']:.1f}x")
    print("  Sharpe convention: futures are self-financing so rf=0 is correct for")
    print(f"  the strategy; SPY has cash subtracted ({RF_ANNUAL * 100:.1f}%/yr), or"
          " its Sharpe")
    print("  would be inflated by the cash return it does not earn.")


if __name__ == "__main__":
    main()
