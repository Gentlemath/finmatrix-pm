"""Re-learn the trend-speed grouping, with the error bars the demo omits.

    python examples/trend_grouping_study.py --dataset 2
    python examples/trend_grouping_study.py --dataset 1     # the v1 comparison
    python examples/trend_grouping_study.py --train-through 2004-12

Why this exists rather than a reading of trend_speed_demo.py. That demo averages
single-market Sharpes per class. Two problems:

1. NO ERROR BARS. A Sharpe measured over T years carries a standard error of
   about 1/sqrt(T) -- 0.16 over 40 years -- and averaging across markets does not
   divide it by sqrt(n) because the markets are correlated. Differences of 0.04
   between lookbacks were being read as structure.
2. An average of per-market Sharpes is not a quantity anyone can trade.

So each class is evaluated as a PORTFOLIO instead: hold that class's markets at
one lookback, size by inverse volatility, and measure the portfolio. Its Sharpe
has a well-defined standard error and it is a thing you could actually run.

The grouping is then learned on a TRAINING window only and applied to the rest.
An in-sample argmax over six lookbacks and seven classes is 42 choices; reporting
the best of those as a finding is how the v1 log ended up retracting a split.
"""

import argparse

import numpy as np
import pandas as pd
from _trend_data import add_dataset_arg, load_basket

from portfolio_management.strategy import (
    GROUPING_V1, GROUPING_V2, TREND_SPEEDS, TimeSeriesMomentum,
    lookback_by_group, speed_group)

MENU = (3, 6, 9, 12, 18, 24)
MIN_MONTHS = 120          # a market needs history for the longest lookback
VOL_WINDOW = 126


def portfolio(m, hf, ppy, cols, lookback, scale=True):
    """Equal-risk trend portfolio over ``cols`` at one lookback."""
    sub = m[list(cols)].dropna(how="all")
    tsm = TimeSeriesMomentum(lookback=lookback, vol_window=VOL_WINDOW,
                             scale=scale, long_short=True)
    res = tsm.backtest(sub, periods_per_year=12,
                       vol_returns=hf[list(cols)] if hf is not None else None,
                       vol_periods_per_year=ppy)
    return res["strategy"].dropna()


def blended(m, hf, ppy, cols, lookbacks):
    """Hold every market at SEVERAL lookbacks at once, equally weighted.

    This is what the literature actually does. Hurst, Ooi & Pedersen combine
    1-, 3- and 12-month signals with equal weight and apply the same combination
    to every market regardless of asset class; Moskowitz, Ooi & Pedersen use a
    single 12-month lookback, likewise uniformly. Neither assigns a speed per
    asset class. Levine & Pedersen show why that can be enough: trend signals at
    different horizons are highly correlated, so the choice of horizon matters
    less within a sensible range than the decision to trade trend at all.

    Averaging weight panels rather than returns is what makes this one portfolio
    rather than a portfolio of portfolios -- the positions net off.
    """
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
    cols_w = panels[0].columns
    W = sum(pan.reindex(index=idx, columns=cols_w).fillna(0.0)
            for pan in panels) / len(panels)
    return (W * sub.reindex(index=idx, columns=cols_w)).sum(axis=1).dropna()


def sharpe_se(r):
    """Annualised Sharpe and its standard error, ~1/sqrt(years)."""
    if len(r) < 24 or r.std() == 0:
        return np.nan, np.nan, 0
    yrs = len(r) / 12.0
    return r.mean() / r.std() * np.sqrt(12), 1.0 / np.sqrt(yrs), yrs


def profile(m, hf, ppy, cols):
    """Sharpe at each lookback for one set of markets, plus SE and argmax."""
    out = {}
    for lb in MENU:
        sr, se, yrs = sharpe_se(portfolio(m, hf, ppy, cols, lb))
        out[lb] = (sr, se, yrs)
    best = max((lb for lb in MENU if not np.isnan(out[lb][0])),
               key=lambda lb: out[lb][0], default=None)
    return out, best


def show_profile(label, n, prof, best, se_ref):
    cells = "".join(f"{prof[lb][0]:>7.2f}" if not np.isnan(prof[lb][0])
                    else f"{'--':>7}" for lb in MENU)
    margin = ""
    if best is not None:
        others = [prof[lb][0] for lb in MENU if lb != best
                  and not np.isnan(prof[lb][0])]
        if others:
            gap = prof[best][0] - max(others)
            margin = f"{gap:>7.2f}{'  *' if gap > se_ref else '   '}"
    print(f"  {label:<11}{n:>3}{cells}{best if best else '--':>7}m{margin}")


def main() -> None:
    ap = add_dataset_arg(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--train-through", default=None,
                    help="last month of the training window, YYYY-MM")
    opts = ap.parse_args()
    m, hf, ppy, cls, name = load_basket(opts.dataset, opts.through, opts.start)
    classes = sorted({cls.get(a, "?") for a in m.columns},
                     key=lambda c: -sum(1 for a in m.columns if cls.get(a) == c))
    print(f"{name}: {m.index.min():%Y-%m} .. {m.index.max():%Y-%m}\n")

    # -- 1. class portfolios, full sample, with error bars ----------------
    print("=== 1. Class trend portfolios by lookback (inverse-vol, long/short) ===")
    print(f"  {'class':<11}{'n':>3}" + "".join(f"{lb:>6}m" for lb in MENU)
          + f"{'best':>8}{'margin':>10}")
    full = {}
    for c in classes:
        cols = [a for a in m.columns if cls.get(a) == c]
        prof, best = profile(m, hf, ppy, cols)
        full[c] = (prof, best, len(cols))
        se = np.nanmean([prof[lb][1] for lb in MENU])
        show_profile(c, len(cols), prof, best, se)
    se_typ = np.nanmean([full[c][0][12][1] for c in classes])
    print("\n  'margin' is the best lookback's lead over the runner-up. A star")
    print(f"  marks a lead wider than the typical standard error ({se_typ:.2f}).")
    print("  Anything unstarred is a coin flip between lookbacks, whatever the")
    print("  argmax says.")

    # -- 2. the markets v1's grouping never saw ---------------------------
    print("\n=== 2. Markets the v1 grouping places by default, not by evidence ===")
    unseen = [a for a in m.columns
              if cls.get(a) in ("livestock",)
              or a in ("PLATINUM", "PALLADIUM")]
    if not unseen:
        print("  none in this dataset")
    else:
        print(f"  {'market':<11}{'n':>3}" + "".join(f"{lb:>6}m" for lb in MENU)
              + f"{'best':>8}{'margin':>10}")
        for a in unseen:
            if m[a].notna().sum() < MIN_MONTHS:
                continue
            prof, best = profile(m, hf, ppy, [a])
            show_profile(a, m[a].notna().sum() // 12, prof, best, prof[12][1])
        print("  v1 puts all of these in 'fast' (3m): precious metals lists")
        print("  only gold and silver, and 'livestock' is absent entirely.")

    # -- 3. learn on a training window, apply to the rest -----------------
    cut = opts.train_through or str(m.index[int(len(m) * 0.6)].to_period("M"))
    cut = pd.Period(cut, "M")
    train = m[m.index <= cut.end_time]
    print(f"\n=== 3. Grouping learned on {train.index.min():%Y-%m}.."
          f"{cut}, tested after ===")
    learned_class = {}
    for c in classes:
        cols = [a for a in m.columns if cls.get(a) == c]
        prof, best = profile(train, hf, ppy, cols)
        learned_class[c] = best
    speeds = sorted({v for v in learned_class.values() if v})
    print("  learned: " + ", ".join(
        f"{c}->{learned_class[c]}m" for c in classes))
    print("  v1 says: " + ", ".join(
        f"{c}->{TREND_SPEEDS[speed_group('X', c, GROUPING_V1)]}m"
        for c in classes))

    configs = {
        "uniform 12m": {a: 12 for a in m.columns},
        "v1 grouping (18/9/3)": lookback_by_group(
            {a: speed_group(a, cls.get(a, "?"), GROUPING_V1) for a in m.columns},
            TREND_SPEEDS),
        "v2 grouping (v1 + livestock slow)": lookback_by_group(
            {a: speed_group(a, cls.get(a, "?"), GROUPING_V2) for a in m.columns},
            TREND_SPEEDS),
        "v2 grouping REVERSED": lookback_by_group(
            {a: {"slow": "fast", "mid": "mid", "fast": "slow"}[
                speed_group(a, cls.get(a, "?"), GROUPING_V2)]
             for a in m.columns}, TREND_SPEEDS),
        "learned on training window": {a: learned_class[cls.get(a, "?")]
                                       for a in m.columns},
        "learned, REVERSED": {a: dict(zip(speeds, reversed(speeds)))
                              .get(learned_class[cls.get(a, "?")],
                                   learned_class[cls.get(a, "?")])
                              for a in m.columns},
    }
    # The literature's default, never tested against the grouping until now.
    blends = {
        "uniform blend 3+12 (MOP-ish)": (3, 12),
        "uniform blend 3+6+12 (HOP-ish)": (3, 6, 12),
        "uniform blend 3+9+18": (3, 9, 18),
    }
    print(f"\n  {'configuration':<30}{'train SR':>10}{'test SR':>9}{'test SE':>9}")
    for label, lbs in blends.items():
        r = blended(m, hf, ppy, m.columns, lbs)
        tr, te = r[r.index <= cut.end_time], r[r.index > cut.end_time]
        s_tr, _, _ = sharpe_se(tr)
        s_te, se_te, _ = sharpe_se(te)
        print(f"  {label:<30}{s_tr:>10.2f}{s_te:>9.2f}{se_te:>9.2f}")
    for label, lb in configs.items():
        r = portfolio(m, hf, ppy, m.columns, lb)
        tr, te = r[r.index <= cut.end_time], r[r.index > cut.end_time]
        s_tr, _, _ = sharpe_se(tr)
        s_te, se_te, _ = sharpe_se(te)
        print(f"  {label:<30}{s_tr:>10.2f}{s_te:>9.2f}{se_te:>9.2f}")
    print("\n  The reversal is the falsification: a grouping that captured real")
    print("  structure must lose when turned upside down. One that merely fitted")
    print("  the training window has no reason to care.")
    print("\n  As a value that can be passed to speed_group(..., grouping=):")
    learned_repr = repr({c: learned_class[c] for c in classes})
    print('    {"by_asset": {}, "by_class": ' + learned_repr
          + ', "default": None}')


if __name__ == "__main__":
    main()
