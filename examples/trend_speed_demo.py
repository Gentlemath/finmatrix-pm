"""Why trend speed must vary by asset class — and how to know it is not fitted.

    python examples/trend_speed_demo.py

The claim: bonds and precious metals trend on a slow macro clock (18 months),
equities and FX in between (9 months), energy and industrial metals fast (3
months) because inventory and supply responses truncate their trends.

The demo runs three checks in the order that makes the claim believable:

  1. per-market optima      -- is the pattern visible in the raw data?
  2. the falsification test -- does REVERSING the grouping cost anything?
  3. per-asset tuning       -- would fitting each market separately do better?

Check 2 is the one that matters. Curve-fitting has no preferred direction: if
the grouping were noise, swapping slow and fast would score about the same.

Full evidence, including out-of-sample tests, is in docs/trend-research-log.md.
"""

import argparse

import numpy as np
import pandas as pd
from _trend_data import add_dataset_arg, load_basket

from portfolio_management.strategy import (
    TREND_SPEEDS, TimeSeriesMomentum, lookback_by_group, speed_group)
from portfolio_management.strategy.performance import apply_costs, performance_summary, turnover

COST = 0.0002
MENU = [3, 6, 9, 12, 18, 24]
REVERSE = {"slow": "fast", "mid": "mid", "fast": "slow"}


def single_market_sharpe(returns, col, lookback):
    """Sharpe of holding sign(trailing return) in one market, unscaled."""
    r = returns[col]
    sig = np.sign((1 + r).rolling(lookback).apply(np.prod, raw=True) - 1)
    fwd = r.shift(-1)
    ok = sig.notna() & fwd.notna() & (sig != 0)
    if ok.sum() < 48:
        return np.nan
    pnl = sig[ok] * fwd[ok]
    return pnl.mean() / pnl.std() * np.sqrt(12)


def backtest(m, hf, ppy, lookback):
    tsm = TimeSeriesMomentum(lookback=lookback, vol_window=126 if ppy == 252 else 52,
                             scale=True, long_short=True)
    res, w = tsm.backtest(m, periods_per_year=12, return_weights=True,
                          vol_returns=hf, vol_periods_per_year=ppy if hf is not None else None)
    return apply_costs(res["strategy"], w, cost=COST), w


def main() -> None:
    opts = add_dataset_arg(argparse.ArgumentParser(description=__doc__)).parse_args()
    m, hf, ppy, cls, name = load_basket(opts.dataset, opts.through, opts.start)
    groups = {a: speed_group(a, cls.get(a, "?")) for a in m.columns}
    print(f"{name}: {m.index.min():%Y-%m} .. {m.index.max():%Y-%m}\n")

    # ---- 1. is the pattern in the raw data? ------------------------------
    print("=== 1. Per-class trend Sharpe by lookback (single markets, unscaled) ===")
    print(f"  {'class':<9}{'n':>3}" + "".join(f"{lb:>7}m" for lb in MENU) + f"{'best':>8}")
    # Classes come from the panel, not a list: v2 added livestock, and a
    # hard-coded list silently omits a whole asset class from the evidence.
    ordered = sorted({cls.get(a, "?") for a in m.columns},
                     key=lambda c: -sum(1 for a in m.columns if cls.get(a) == c))
    for c in ordered:
        cols = [a for a in m.columns if cls.get(a) == c]
        if not cols:
            continue
        avg = {}
        for lb in MENU:
            vals = [single_market_sharpe(m, a, lb) for a in cols]
            vals = [v for v in vals if not np.isnan(v)]
            if vals:
                avg[lb] = float(np.mean(vals))
        if avg:
            best = max(avg, key=avg.get)
            print(f"  {c:<9}{len(cols):>3}"
                  + "".join(f"{avg.get(lb, float('nan')):>8.2f}" for lb in MENU)
                  + f"{str(best) + 'm':>8}")
    print("  Bonds peak late (18m), energy early (3m), equities and FX between.")
    print("  Metals and agriculture look FLAT at class level -- and that is the")
    print("  clue: those classes MIX speeds, so the average hides the structure.")
    print("  Look inside 'metal' and the split is obvious:")
    for a in ("GOLD", "SILVER", "COPPER", "ZINC"):
        if a in m.columns:
            v = {lb: single_market_sharpe(m, a, lb) for lb in MENU}
            v = {k: x for k, x in v.items() if not np.isnan(x)}
            if v:
                print(f"    {a:<8}best {max(v, key=v.get):>2}m   "
                      + "  ".join(f"{lb}m:{v[lb]:+.2f}" for lb in MENU if lb in v))

    # ---- 2. the falsification test ---------------------------------------
    print("\n=== 2. Falsification: reverse the grouping and see what it costs ===")
    print(f"  {'configuration':<38}{'SR':>6}{'t':>6}{'maxDD':>9}{'turn':>7}")
    variants = {
        "uniform 12m (no grouping)": {a: 12 for a in m.columns},
        "three-speed 18/9/3": lookback_by_group(groups, TREND_SPEEDS),
        "REVERSED (slow<->fast)": lookback_by_group(
            {a: REVERSE[g] for a, g in groups.items()}, TREND_SPEEDS),
    }
    got = {}
    for label, lb in variants.items():
        net, w = backtest(m, hf, ppy, lb)
        s = performance_summary(net, periods_per_year=12)
        got[label] = (s["sharpe"], s["max_drawdown"], turnover(w)["annualized"])
        print(f"  {label:<38}{s['sharpe']:>6.2f}"
              f"{s['sharpe'] * np.sqrt(len(net) / 12):>6.2f}"
              f"{s['max_drawdown'] * 100:>8.1f}%{turnover(w)['annualized']:>6.1f}x")

    # Narrated from THIS run, not from the one this section was written on.
    # The hardcoded version said "reversing halves the Sharpe", which was true
    # of v1's full sample (-49%) and of nothing else: the cost is -31% to -36%
    # on the other three dataset/window combinations.
    uni, grp, rev = (got[k][0] for k in variants)
    print(f"  Reversing costs {(1 - rev / grp) * 100:.0f}% of the Sharpe "
          f"({grp:.2f} -> {rev:.2f}), takes the drawdown from "
          f"{got['three-speed 18/9/3'][1] * 100:.1f}% to "
          f"{got['REVERSED (slow<->fast)'][1] * 100:.1f}%, and raises turnover "
          f"from {got['three-speed 18/9/3'][2]:.1f}x to "
          f"{got['REVERSED (slow<->fast)'][2]:.1f}x.")
    print("  A fitted pattern would not care which way round it went. This is"
          "\n  the robust half of the section: reversal is costly on every"
          "\n  dataset and window tried (-31% to -49%).")
    # The fragile half, stated rather than hidden. Whether the GROUPING beats
    # plain uniform 12m is a different and much weaker claim than whether the
    # ORDER matters, and on the wider basket it does not survive.
    if grp > uni + 0.02:
        print(f"  Here the grouping also beats uniform 12m ({grp:.2f} vs "
              f"{uni:.2f}).")
    else:
        print(f"  Note: the grouping does NOT beat uniform 12m here "
              f"({grp:.2f} vs {uni:.2f}).")
        print("  Both results are real. Reversal being costly says the speed"
              "\n  ORDER carries information; it does not say the three-speed"
              "\n  grouping earns more than one lookback for everything. On the"
              "\n  35-market basket it did (+0.19); on 50 markets it does not.")
    if got["three-speed 18/9/3"][1] > got["uniform 12m (no grouping)"][1]:
        print(f"  The grouping does still cut the drawdown: "
              f"{got['three-speed 18/9/3'][1] * 100:.1f}% vs "
              f"{got['uniform 12m (no grouping)'][1] * 100:.1f}%.")

    # ---- 3. would per-asset tuning do better? ----------------------------
    print("\n=== 3. Per-asset tuning: fit on the early period, test on the rest ===")
    # The markets do not all start together. Evaluating a 24-month lookback needs
    # roughly 24 + 48 months, so the split has to be late enough that every
    # market is assessable -- otherwise the fit silently picks whichever lookback
    # happened to have data, which is not a fit at all.
    latest_start = max(m[a].dropna().index.min() for a in m.columns)
    cut = m.index[m.index >= latest_start + pd.DateOffset(months=72)][0]
    fit = m.loc[:cut]
    per_asset = {}
    for a in m.columns:
        v = {lb: single_market_sharpe(fit, a, lb) for lb in MENU}
        v = {k: x for k, x in v.items() if not np.isnan(x)}
        per_asset[a] = max(v, key=v.get) if len(v) >= 5 else TREND_SPEEDS[groups[a]]
    print(f"  {'configuration':<38}{'params':>7}{'fit':>7}{'test':>7}")
    for label, lb, npar in [
        ("uniform 12m", {a: 12 for a in m.columns}, 1),
        ("three-speed grouping", lookback_by_group(groups, TREND_SPEEDS), 3),
        ("per-asset optimum", per_asset, len(m.columns)),
    ]:
        net, _ = backtest(m, hf, ppy, lb)
        f = net.loc[:cut]
        t = net.loc[cut:]
        sr = lambda x: x.mean() / x.std() * np.sqrt(12)      # noqa: E731
        print(f"  {label:<38}{npar:>7}{sr(f):>7.2f}{sr(t):>7.2f}")
    print(f"  Split at {cut:%Y-%m} (72 months after the last market starts, so")
    print(f"  all {len(m.columns)} are assessable). More parameters fit better "
          f"and test worse —")
    print("  and the fitted speeds agree with the grouping for only "
          f"{sum(1 for a in m.columns if per_asset[a] == TREND_SPEEDS[groups[a]])}"
          f"/{len(m.columns)} markets.")
    print("\n  NOTE: one split is one draw. The research log runs both split dates")
    print("  and a walk-forward, and reports the reversal test out of sample too.")


if __name__ == "__main__":
    main()
