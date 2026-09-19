"""Walk-forward: does learning the speed grouping beat not learning it?

    python examples/trend_walkforward_study.py --dataset 2
    python examples/trend_walkforward_study.py --dataset 1
    python examples/trend_walkforward_study.py --step 3 --min-train 120

One split is one draw, and trend_grouping_study.py's single split separated the
best configuration from the worst by 1.4 standard errors — not enough to choose.
This re-learns the grouping at the start of every window from data available up
to that date only, freezes it, trades the next `step` years, and moves on. The
test blocks are disjoint, so stitching them gives ONE out-of-sample track record
per configuration rather than one number per split date.

Configurations fall into two kinds, and the comparison is between the kinds:

  LEARNED    re-fitted at every window start from the training data
  FIXED      chosen once and never re-fitted -- the v1 grouping, a single
             12-month lookback, and the uniform multi-speed blends the
             literature actually uses (Moskowitz-Ooi-Pedersen use 12 months
             uniformly; Hurst-Ooi-Pedersen blend 1/3/12 equally, applied to
             every market regardless of class)

"Fixed" is not the same as "clean". The v1 grouping was itself selected on the
v1 full sample -- the v1 log records trying a two-speed split, watching it fail
on an independent ETF basket, and changing it. So this contest is between ONE
pass over the whole sample and a refit in every window, not between a clean
prior and a fitted one. Fewer passes, not zero.

Nor is the LEARNED column here the same thing the v1 log's walk-forward learns.
That procedure fits a lookback per MARKET, buckets markets into slow/mid/fast by
the result, and blends the top two lookbacks per bucket. This one fits a single
lookback per asset CLASS. Both beat uniform 12m; neither reproduces the other.

If learning helps, the learned configuration should win. On a single split it
lost, and training fit correlated NEGATIVELY with test performance (-0.70).

Two correctness notes:

* `TimeSeriesMomentum` is strictly causal -- running it on the full panel and
  truncating gives returns identical to running it on the truncated panel (max
  difference 0.0). Class portfolios are therefore computed once and sliced.
* Market counts per window are counted from markets that actually have data in
  that window. An earlier version of this analysis in the v1 log reported group
  counts summing to the full basket in years when half of it did not yet exist.
"""

import argparse

import numpy as np
import pandas as pd
from _trend_data import add_dataset_arg, load_basket

from portfolio_management.strategy import (
    GROUPING_V1, GROUPING_V2, TREND_SPEEDS, TimeSeriesMomentum, speed_group)

MENU = (3, 6, 9, 12, 18, 24)
VOL_WINDOW = 126
MIN_CLASS_MONTHS = 60      # a class needs this much training to be learned from


def panel_returns(m, hf, ppy, cols, lookback):
    sub = m[list(cols)].dropna(how="all")
    tsm = TimeSeriesMomentum(lookback=lookback, vol_window=VOL_WINDOW,
                             scale=True, long_short=True)
    return tsm.backtest(sub, periods_per_year=12,
                        vol_returns=hf[list(cols)] if hf is not None else None,
                        vol_periods_per_year=ppy)["strategy"].dropna()


def blended_returns(m, hf, ppy, cols, lookbacks):
    sub = m[list(cols)].dropna(how="all")
    panels, idx = [], None
    for lb in lookbacks:
        tsm = TimeSeriesMomentum(lookback=lb, vol_window=VOL_WINDOW,
                                 scale=True, long_short=True)
        _, w = tsm.backtest(sub, periods_per_year=12, return_weights=True,
                            vol_returns=hf[list(cols)] if hf is not None else None,
                            vol_periods_per_year=ppy)
        panels.append(w)
        idx = w.index if idx is None else idx.intersection(w.index)
    c = panels[0].columns
    W = sum(p.reindex(index=idx, columns=c).fillna(0.0) for p in panels) / len(panels)
    return (W * sub.reindex(index=idx, columns=c)).sum(axis=1).dropna()


def sharpe(r):
    if len(r) < 12 or r.std() == 0:
        return np.nan
    return r.mean() / r.std() * np.sqrt(12)


def main() -> None:
    ap = add_dataset_arg(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--step", type=int, default=5, help="test block, years")
    ap.add_argument("--min-train", type=int, default=120,
                    help="months of training before the first window")
    ap.add_argument("--only-classes", default=None,
                    help="comma-separated asset classes to keep")
    opts = ap.parse_args()
    m, hf, ppy, cls, name = load_basket(opts.dataset, opts.through, opts.start)
    if opts.only_classes:
        keep = {c.strip() for c in opts.only_classes.split(",")}
        m = m[[a for a in m.columns if cls.get(a) in keep]]
        hf = hf[m.columns]
        name = f"{name} [{','.join(sorted(keep))}]"
    classes = sorted({cls.get(a, "?") for a in m.columns})
    v1_lb = {a: TREND_SPEEDS[speed_group(a, cls.get(a, "?"), GROUPING_V1)]
             for a in m.columns}
    v2_lb = {a: TREND_SPEEDS[speed_group(a, cls.get(a, "?"), GROUPING_V2)]
             for a in m.columns}
    print(f"{name}: {m.index.min():%Y-%m} .. {m.index.max():%Y-%m}")
    print(f"walk-forward: re-learn every {opts.step}y, "
          f"{opts.min_train}m minimum training\n")

    # class portfolios, computed once (the backtest is causal, so slicing is
    # equivalent to re-running on truncated data)
    cls_ret = {}
    for c in classes:
        cols = [a for a in m.columns if cls.get(a) == c]
        for lb in MENU:
            cls_ret[(c, lb)] = panel_returns(m, hf, ppy, cols, lb)

    # fixed configurations: no refitting, ever
    fixed = {
        "v1 grouping 18/9/3": panel_returns(m, hf, ppy, m.columns, v1_lb),
        "v2 grouping 18/9/3": panel_returns(m, hf, ppy, m.columns, v2_lb),
        # The falsification that matters is reversing the grouping IN USE. The
        # "learned REVERSED" row below reverses the LEARNED grouping instead,
        # which on v2 collapses to two speeds, so its reversal swaps 3m and 12m
        # rather than 3m and 18m -- a much milder perturbation, and a test of a
        # different object.
        "v2 grouping REVERSED": panel_returns(
            m, hf, ppy, m.columns,
            {a: TREND_SPEEDS[{"slow": "fast", "mid": "mid", "fast": "slow"}[
                speed_group(a, cls.get(a, "?"), GROUPING_V2)]]
             for a in m.columns}),
        "uniform 12m": panel_returns(m, hf, ppy, m.columns, 12),
        "blend 3+9+18": blended_returns(m, hf, ppy, m.columns, (3, 9, 18)),
        "blend 3+6+12": blended_returns(m, hf, ppy, m.columns, (3, 6, 12)),
    }
    # Livestock is the one market group the v1 grouping places by DEFAULT rather
    # than by evidence -- the class is absent from its map, so it falls to the
    # commodity speed of 3m. On v2 livestock's 3m and 6m Sharpes are NEGATIVE
    # (-0.01, 0.05) and it peaks at 9m. That is a sign problem, not a marginal
    # argmax, so correcting it is not the same kind of choice as re-fitting.
    # Whether it matters at portfolio level is a separate question: livestock is
    # 2 of 51 markets.
    livestock = [a for a in m.columns if cls.get(a) == "livestock"]
    if livestock:
        for lb_liv in (9, 12, 18):
            v = dict(v1_lb)
            for a in livestock:
                v[a] = lb_liv
            fixed[f"v1 + livestock {lb_liv}m"] = panel_returns(
                m, hf, ppy, m.columns, v)
    # Platinum sits on the precious/industrial line. Its trend profile leans
    # slower than silver's (12m minus 3m of +0.15 against +0.12) and its shape
    # correlates +0.70 with gold and silver but only +0.22 with the base metals,
    # which themselves correlate -0.17 with gold and silver. That is suggestive
    # and not significant, so the test is the same one livestock passed: a real
    # effect should be insensitive to WHICH slower speed is used.
    if "PLATINUM" in m.columns:
        base = v2_lb          # read-only here; every use copies via dict()
        # GROUPING_V2 already holds platinum slow, so the informative
        # counterfactual is putting it back with the base metals, plus the two
        # other slow speeds to show the choice is not knife-edged.
        for lb_pt, tag in ((3, "back to fast 3m"), (9, "at 9m"), (12, "at 12m")):
            v = dict(base)
            v["PLATINUM"] = lb_pt
            fixed[f"v2, platinum {tag}"] = panel_returns(
                m, hf, ppy, m.columns, v)

    starts = []
    t0 = m.index[opts.min_train]
    t = pd.Timestamp(t0)
    while t < m.index[-1]:
        starts.append(t)
        t = t + pd.DateOffset(years=opts.step)

    print(f"  {'window':<18}{'mkts':>5}{'fallback':>9}  {'learned':<34}")
    stitched = {k: [] for k in list(fixed) + ["learned", "learned REVERSED"]}
    for i, t in enumerate(starts):
        end = t + pd.DateOffset(years=opts.step)
        te = (m.index > t) & (m.index <= end)
        if te.sum() < 12:
            continue
        live = [a for a in m.columns if m.loc[te, a].notna().any()]
        learned, fallback = {}, 0
        for c in classes:
            r = cls_ret[(c, 12)]
            if (r.index <= t).sum() < MIN_CLASS_MONTHS:
                learned[c] = None
                continue
            best, bs = None, -np.inf
            for lb in MENU:
                s = sharpe(cls_ret[(c, lb)][cls_ret[(c, lb)].index <= t])
                if not np.isnan(s) and s > bs:
                    best, bs = lb, s
            learned[c] = best
        lb_learned = {}
        for a in m.columns:
            c = cls.get(a, "?")
            if learned.get(c):
                lb_learned[a] = learned[c]
            else:
                lb_learned[a] = v1_lb[a]
                fallback += 1
        used = sorted({v for v in learned.values() if v})
        rev_map = dict(zip(used, reversed(used)))
        lb_rev = {a: rev_map.get(lb_learned[a], lb_learned[a]) for a in m.columns}

        test_months = m.index[te]
        for label, series in fixed.items():
            stitched[label].append(series[series.index.isin(test_months)])
        for label, lb in (("learned", lb_learned),
                          ("learned REVERSED", lb_rev)):
            r = panel_returns(m, hf, ppy, m.columns, lb)
            stitched[label].append(r[r.index.isin(test_months)])

        desc = " ".join(f"{c[:3]}:{learned[c] or '--'}" for c in classes)
        print(f"  {t:%Y-%m}..{end:%Y-%m}{len(live):>5}{fallback:>9}  {desc}")

    print(f"\n  {'configuration':<22}{'OOS months':>11}{'Sharpe':>8}"
          f"{'SE':>7}{'t':>7}{'wins':>6}")
    per_window = {k: [sharpe(x) for x in v] for k, v in stitched.items()}
    fixed_and_learned = [k for k in stitched if k != "learned REVERSED"]
    wins = {k: 0 for k in stitched}
    n_win = len(next(iter(per_window.values())))
    for i in range(n_win):
        vals = {k: per_window[k][i] for k in fixed_and_learned
                if not np.isnan(per_window[k][i])}
        if vals:
            wins[max(vals, key=vals.get)] += 1
    for k in list(fixed) + ["learned", "learned REVERSED"]:
        r = pd.concat(stitched[k]).sort_index()
        s, se = sharpe(r), 1.0 / np.sqrt(len(r) / 12.0)
        print(f"  {k:<22}{len(r):>11}{s:>8.2f}{se:>7.2f}{s / se:>7.2f}"
              f"{wins[k]:>6}")
    print("\n  'wins' counts windows where a configuration had the highest test")
    print(f"  Sharpe, out of {n_win}. The reversed grouping is excluded from the")
    print("  contest and shown only as the falsification.")


if __name__ == "__main__":
    main()
