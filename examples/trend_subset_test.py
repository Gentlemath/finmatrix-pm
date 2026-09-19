"""Is the older 35-market basket's recent Sharpe unusual, or was it selected?

    python examples/trend_subset_test.py
    python examples/trend_subset_test.py --n 35 --draws 2000 --test-from 2012-02

Over a matched window (1979-01 onward, tested from 2012-02) the v1 basket scores
0.85 out of sample against v2's 0.61 on the same grouping. Two explanations fit:

  SELECTION  v1's 35 markets were assembled from whatever the continuous-series
             tables happened to offer and what looked usable, so the set carries
             hindsight. v2's additions were included by an ex-ante rule -- every
             liquid CME market -- regardless of how they had performed.
  LUCK       v2's extra markets simply did badly after 2012.

The natural test -- draw random 35-market subsets from v2 and see where 0.85
falls -- is VALID ONLY IF v1's markets are all inside v2's universe. They are
not: five of them were dropped, and those five returned 0.928 over this very
window against 0.52 over the full sample. No draw can contain them, so a high
percentile shows that v2's fifty cannot assemble v1's result, not that v1's set
was chosen with hindsight. The tool now says so in its output, because the first
reading of it here drew exactly that wrong conclusion.

Attribute by sleeve first. On this window the thirty shared markets score 0.685
in v1 and 0.695 in v2 -- construction and coverage explain nothing -- while the
five dropped markets score 0.928 and the twenty added ones 0.314.

This is fast because of how the backtest weights: ``w = raw / len(names)``, an
equal-weighted average of volatility-scaled positions, so a subset's return is
the mean of its members' per-date contributions. Those are computed once and
then averaged over thousands of draws, rather than re-running a backtest each
time. The identity is asserted against the real backtest before any sampling.
"""

import argparse

import numpy as np
import pandas as pd
from _trend_data import add_dataset_arg, load_basket

from portfolio_management.strategy import (
    GROUPING_V2, TREND_SPEEDS, TimeSeriesMomentum, speed_group)

VOL_WINDOW = 126


def contributions(m, hf, ppy, cls):
    """Per-market, per-date contribution and eligibility.

    Mirrors TimeSeriesMomentum.backtest: direction from the sign of the trailing
    return, scaled by target_vol / realised vol, held one period forward. The
    division by the number of eligible markets is left to the caller, since that
    is the only part that depends on the subset.
    """
    lb = {a: TREND_SPEEDS[speed_group(a, cls[a], GROUPING_V2)] for a in m.columns}
    tsm = TimeSeriesMomentum(lookback=lb, vol_window=VOL_WINDOW, scale=True,
                             long_short=True)
    direction = np.sign(tsm.compute_signal(m))
    vol = tsm._aligned_vol(m, 12, hf, ppy)
    dates = m.index
    contrib = pd.DataFrame(np.nan, index=dates[1:], columns=m.columns)
    for i in range(len(dates) - 1):
        d, h = dates[i], dates[i + 1]
        dir_row, fwd, v = direction.loc[d], m.loc[h], vol.loc[d]
        ok = (dir_row.notna() & (dir_row != 0.0) & fwd.notna()
              & v.notna() & (v > 0.0))
        names = dir_row.index[ok]
        if len(names) == 0:
            continue
        contrib.loc[h, names] = (dir_row[names] * (tsm.target_vol / v[names])
                                 * fwd[names].astype(float))
    return contrib


def subset_returns(contrib, cols):
    sub = contrib[list(cols)]
    n = sub.notna().sum(axis=1)
    return (sub.sum(axis=1, min_count=1) / n.replace(0, np.nan)).dropna()


def sharpe(r):
    return r.mean() / r.std() * np.sqrt(12) if len(r) > 11 else np.nan


def main() -> None:
    ap = add_dataset_arg(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--n", type=int, default=35, help="markets per draw")
    ap.add_argument("--draws", type=int, default=2000)
    ap.set_defaults(start="1979-01")   # v1 begins here; the default window
    ap.add_argument("--test-from", default="2012-02")
    ap.add_argument("--seed", type=int, default=0)
    opts = ap.parse_args()

    m2, h2, ppy, c2, n2 = load_basket(2, through="2026-03")
    m1, h1, _, c1, n1 = load_basket(1, through="2026-03")
    cut0 = pd.Period(opts.start, "M").start_time
    m2, h2 = m2[m2.index >= cut0], h2[h2.index >= cut0]
    m1, h1 = m1[m1.index >= cut0], h1[h1.index >= cut0]
    m2 = m2.loc[:, m2.notna().any()]
    m1 = m1.loc[:, m1.notna().any()]
    h2, h1 = h2[m2.columns], h1[m1.columns]
    test0 = pd.Period(opts.test_from, "M").start_time
    print(f"{n2}\n{n1}\ntest window {opts.test_from} .. "
          f"{m2.index.max():%Y-%m}\n")

    c = contributions(m2, h2, ppy, c2)
    full = subset_returns(c, m2.columns)

    # the shortcut must reproduce the real backtest before it is trusted
    lb = {a: TREND_SPEEDS[speed_group(a, c2[a], GROUPING_V2)] for a in m2.columns}
    real = TimeSeriesMomentum(lookback=lb, vol_window=VOL_WINDOW, scale=True,
                              long_short=True).backtest(
        m2, periods_per_year=12, vol_returns=h2,
        vol_periods_per_year=ppy)["strategy"].dropna()
    j = pd.concat([full.rename("fast"), real.rename("real")], axis=1).dropna()
    err = (j["fast"] - j["real"]).abs().max()
    print(f"shortcut vs backtest: {len(j)} months, max |difference| {err:.2e}")
    assert err < 1e-12, "the decomposition does not reproduce the backtest"

    lb1 = {a: TREND_SPEEDS[speed_group(a, c1[a], GROUPING_V2)] for a in m1.columns}
    r1 = TimeSeriesMomentum(lookback=lb1, vol_window=VOL_WINDOW, scale=True,
                            long_short=True).backtest(
        m1, periods_per_year=12, vol_returns=h1,
        vol_periods_per_year=ppy)["strategy"].dropna()
    s_v1 = sharpe(r1[r1.index >= test0])
    s_v2 = sharpe(full[full.index >= test0])
    print(f"\n  v1 basket ({m1.shape[1]} markets) out-of-sample Sharpe: {s_v1:.3f}")
    print(f"  v2 basket ({m2.shape[1]} markets) out-of-sample Sharpe: {s_v2:.3f}")

    rng = np.random.default_rng(opts.seed)
    cols = list(m2.columns)
    draws = []
    for _ in range(opts.draws):
        pick = rng.choice(len(cols), size=opts.n, replace=False)
        r = subset_returns(c, [cols[i] for i in pick])
        draws.append(sharpe(r[r.index >= test0]))
    d = np.array([x for x in draws if np.isfinite(x)])
    pct = 100.0 * (d < s_v1).mean()
    print(f"\n  {len(d)} random {opts.n}-market subsets of v2, same window:")
    print(f"    mean {d.mean():.3f}   sd {d.std():.3f}   "
          f"min {d.min():.3f}   max {d.max():.3f}")
    for q in (5, 25, 50, 75, 95, 99):
        print(f"    p{q:<3}{np.percentile(d, q):>8.3f}")
    print(f"\n  v1's {s_v1:.3f} falls at the {pct:.1f}th percentile of what a "
          f"{opts.n}-market\n  basket drawn from v2 could have produced.")

    missing = sorted(set(m1.columns) - set(m2.columns))
    print("\n  READ THIS BEFORE THE PERCENTILE.")
    if missing:
        print(f"  {len(missing)} of v1's markets are NOT in v2 and therefore "
              f"cannot appear in\n  any draw: {', '.join(missing)}.")
        print("  A high percentile then shows only that v2's universe cannot"
              "\n  assemble v1's result -- NOT that v1's set was chosen with"
              "\n  hindsight. If those markets carry v1's edge, the sampling"
              "\n  distribution is answering a different question than the one"
              "\n  asked. Attribute the gap by sleeve before concluding"
              "\n  anything: shared labels, markets only in v1, markets only in"
              "\n  v2.")
    else:
        print("  Every v1 market is in v2's universe, so the percentile is"
              "\n  interpretable: a high value means a set that good was"
              "\n  unlikely to be drawn by accident.")


if __name__ == "__main__":
    main()
