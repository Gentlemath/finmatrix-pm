"""What the monthly backtest hides: the daily path inside each month.

    python examples/trend_intramonth_demo.py            # worst months by intra-month risk
    python examples/trend_intramonth_demo.py 2020-03    # the daily path of one month

Positions are formed at each month end and held unchanged for the whole month —
the signal is a 12-to-18-month lookback and the rebalance is monthly, so within
a month the book cannot react at all. Futures mark to market daily, though, so
the equity curve inside a month is what actually determines margin calls.

Two DIFFERENT measures get confused here, and the demo reports both:

  peak-to-trough   worst drop from the highest point reached INSIDE the month.
                   This is what a margin desk watches, because equity is marked
                   from its high-water mark.

  start-to-trough  worst cumulative loss measured from the month's opening
                   value. This is what "how much was I down on the month" means.

They diverge whenever the book rallies before falling: a month that gains 8% and
then gives back 10% has a 10% peak-to-trough but only a 2.7% start-to-trough.
"""

import sys

import pandas as pd
from _trend_data import load_basket

from portfolio_management.strategy import (
    TimeSeriesMomentum, lookback_by_group, speed_group, volatility_target)

COST = 0.0002
BLEND = {"slow": (12, 18), "mid": (9, 12), "fast": (3, 6)}
TARGET_VOL = 0.15


def build_daily_path(m, hf, ppy, groups):
    """Daily P&L of the monthly-rebalanced, volatility-targeted book."""
    panels, idx = [], None
    for i in (0, 1):
        lb = lookback_by_group(groups, {g: v[i] for g, v in BLEND.items()})
        tsm = TimeSeriesMomentum(lookback=lb, vol_window=126 if ppy == 252 else 52,
                                 scale=True, long_short=True)
        _, w = tsm.backtest(m, periods_per_year=12, return_weights=True,
                            vol_returns=hf, vol_periods_per_year=ppy)
        panels.append(w)
        idx = w.index if idx is None else idx.intersection(w.index)
    cols = panels[0].columns
    W = sum(p.reindex(index=idx, columns=cols).fillna(0.0) for p in panels) / len(panels)
    gross = (W * m.reindex(index=idx, columns=cols)).sum(axis=1)
    net_m, lev, lw = volatility_target(gross, W, TARGET_VOL, cost=COST)

    # Weights indexed at a month end are HELD DURING that month, so apply them
    # to that month's daily returns.
    hf = hf[cols]
    lwp = lw.copy()
    lwp.index = lwp.index.to_period("M")
    parts = {}
    for ym, block in hf.groupby(hf.index.to_period("M")):
        if ym not in lwp.index:
            continue
        row = lwp.loc[ym]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        parts[ym] = (block.fillna(0.0) * row.reindex(cols).fillna(0.0)).sum(axis=1)
    daily = pd.concat(parts.values()).sort_index()
    return daily[daily.index >= lw.index.min()], net_m, lw


def month_measures(daily):
    """Per-month: return, peak-to-trough, start-to-trough."""
    df = pd.DataFrame({"r": daily})
    df["ym"] = df.index.to_period("M")
    out = {}
    for ym, s in df.groupby("ym")["r"]:
        nav = (1 + s).cumprod()
        out[ym] = {
            "month_return": nav.iloc[-1] - 1.0,
            "peak_to_trough": (nav / nav.cummax() - 1.0).min(),
            "start_to_trough": nav.min() - 1.0,
            "days": len(s),
        }
    return pd.DataFrame(out).T


def show_month(daily, ym):
    s = daily[daily.index.to_period("M") == pd.Period(ym, "M")]
    if s.empty:
        raise SystemExit(f"no daily data for {ym}")
    nav = (1 + s).cumprod()
    peak = nav.cummax()
    print(f"\n=== {ym}: daily path of a 1.00 portfolio ===")
    print(f"  {'date':<12}{'day ret':>9}{'net value':>11}{'from start':>12}"
          f"{'from peak':>11}")
    for d in s.index:
        print(f"  {d:%Y-%m-%d}{s[d] * 100:>+8.2f}%{nav[d]:>11.4f}"
              f"{(nav[d] - 1) * 100:>+11.2f}%{(nav[d] / peak[d] - 1) * 100:>+10.2f}%")
    print(f"\n  month return      {(nav.iloc[-1] - 1) * 100:+.2f}%")
    print(f"  start-to-trough   {(nav.min() - 1) * 100:+.2f}%"
          f"   (worst cumulative loss on the month)")
    print(f"  peak-to-trough    {(nav / peak - 1).min() * 100:+.2f}%"
          f"   (worst drop from the intra-month high)")
    hi = nav.idxmax()
    print(f"  intra-month high  {nav.max():.4f} on {hi:%Y-%m-%d}, "
          f"then {(nav.min() / nav.max() - 1) * 100:+.2f}% to the low")


def main() -> None:
    m, hf, ppy, cls, name = load_basket()
    if hf is None or ppy != 252:
        raise SystemExit("This demo needs a DAILY panel; run "
                         "examples/cache_futures_data_wrds.py")
    groups = {a: speed_group(a, cls.get(a, "?")) for a in m.columns}
    daily, net_m, lw = build_daily_path(m, hf, ppy, groups)
    print(f"{name}: {len(daily):,} days, {daily.index.min():%Y-%m} .. "
          f"{daily.index.max():%Y-%m}")
    print("positions held constant within each month, no intra-month trading")

    if len(sys.argv) > 1:
        show_month(daily, sys.argv[1])
        return

    mm = month_measures(daily)
    print("\n=== The two measures are not the same thing ===")
    print(f"  {'month':<10}{'month ret':>11}{'start->trough':>15}{'peak->trough':>14}")
    for ym in mm.nsmallest(8, "peak_to_trough").index:
        r = mm.loc[ym]
        print(f"  {str(ym):<10}{r.month_return * 100:>+10.1f}%"
              f"{r.start_to_trough * 100:>+14.1f}%{r.peak_to_trough * 100:>+13.1f}%")
    print("  Where the two differ, the book rallied first and gave it back.")

    print("\n=== Months that look calm monthly but were not ===")
    bad = mm[(mm.month_return > -0.02) & (mm.peak_to_trough < -0.06)]
    print(f"  {len(bad)} of {len(mm)} months ended better than -2% but fell "
          f">6% from an intra-month peak")
    for ym in bad.nsmallest(6, "peak_to_trough").index:
        r = bad.loc[ym]
        print(f"    {str(ym):<10}month {r.month_return * 100:>+6.1f}%   "
              f"start->trough {r.start_to_trough * 100:>+6.1f}%   "
              f"peak->trough {r.peak_to_trough * 100:>+6.1f}%")

    print("\n=== Which one matters for margin ===")
    print(f"  worst start-to-trough ever  {mm.start_to_trough.min() * 100:>6.1f}%  "
          f"({mm.start_to_trough.idxmin()})")
    print(f"  worst peak-to-trough ever   {mm.peak_to_trough.min() * 100:>6.1f}%  "
          f"({mm.peak_to_trough.idxmin()})")
    print("  A margin desk marks equity from its high-water mark, so peak-to-trough")
    print("  is the binding number. Neither reaches a level that would call a")
    print("  well-funded account, but both are invisible in the monthly series.")
    print("\n  Inspect any month:  python examples/trend_intramonth_demo.py 2020-03")


if __name__ == "__main__":
    main()
