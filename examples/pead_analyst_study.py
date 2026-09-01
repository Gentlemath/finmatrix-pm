"""Upgraded PEAD event study — analyst-based SUE + characteristic (size) adjustment.

Compares two pipelines on the same cached S&P 500 data, era by era:

  A. BASELINE   Compustat seasonal-random-walk SUE, market-adjusted CARs (daily
                cross-sectional mean removed), event date = Compustat `rdq`.
  B. UPGRADE    IBES analyst-based SUE = (actual - consensus median) / dispersion,
                from the last consensus before the announcement; size-decile daily
                benchmark subtracted (characteristic adjustment); event = `anndats`.

Question: does the analyst signal + size benchmark produce a cleaner, more
monotone SUE->drift relation and a decay path closer to the published PEAD?

Reads cached (licensed, gitignored) files written by cache_pead_data.py and
cache_ibes_data.py:
  comp_earnings.csv, ccm_link.csv, crsp_daily.csv, crsp_monthly.csv,
  ibes_actuals.csv, ibes_consensus.csv, ibes_link.csv

CAVEAT: size deciles are formed *within the S&P 500* (all large caps), so the
characteristic adjustment removes only the size tilt relative to other index
members — it is not a full-market DGTW benchmark. Book-to-market is not adjusted.
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from portfolio_management.strategy import (  # noqa: E402
    analyst_sue,
    event_car,
    standardized_unexpected_earnings,
)

D = Path("local_data")
ERAS = [(1985, 1994), (1995, 2000), (2001, 2006), (2007, 2015), (2016, 2026)]
# ordered SUE quintiles -> diverging blue(bad news) .. gray .. red(good news)
Q_COLORS = ["#2166AC", "#67A9CF", "#999999", "#EF8A62", "#B2182B"]


# --------------------------------------------------------------------------- #
# shared machinery
# --------------------------------------------------------------------------- #
def quintile_within_month(res: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    Add `ym`, `year`, and SUE quintile `q` (0..4) formed within each month.
    q=0 = the lowest-SUE fifth (biggest negative surprises)
    q=4 = the highest-SUE fifth (biggest positive surprises)
    """
    res = res.copy()
    res["ym"] = res[date_col].dt.to_period("M")
    res["year"] = res[date_col].dt.year
    res["q"] = res.groupby("ym")["sue"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False)
        if s.notna().sum() >= 5 else np.nan)
    return res.dropna(subset=["q"]).assign(q=lambda d: d["q"].astype(int))


def spread(sub: pd.DataFrame, col: str) -> float:
    g = sub.groupby("q")[col].mean()
    return (g.get(4, np.nan) - g.get(0, np.nan)) * 100      # Q5 - Q1, in %


def era_table(res: pd.DataFrame, label: str) -> None:
    print(f"\n=== {label}  (SUE Q5-Q1 spread, %) ===")
    print(f"  {'era':11} {'n':>7} {'announce[0,+1]':>15} {'drift[+2,+63]':>15}")
    for a, b in ERAS:
        s = res[(res["year"] >= a) & (res["year"] <= b)]
        if len(s) < 50:
            continue
        print(f"  {a}-{b:<6}{len(s):>7} {spread(s, 'ann_car'):>15.2f} "
              f"{spread(s, 'drift_car'):>15.2f}")


def quintile_ladder(res: pd.DataFrame, label: str) -> None:
    """Full-sample mean drift CAR by SUE quintile — is it monotone in SUE?"""
    g = res.groupby("q")["drift_car"].mean() * 100
    row = "  ".join(f"Q{q + 1}:{g.get(q, np.nan):+5.2f}" for q in range(5))
    mono = all(g.get(i, -np.inf) <= g.get(i + 1, np.inf) for i in range(4))
    print(f"  {label:16} {row}   monotone={'yes' if mono else 'no'}")


# --------------------------------------------------------------------------- #
# size-decile daily benchmark (characteristic adjustment)
# --------------------------------------------------------------------------- #
def size_benchmark(daily: pd.DataFrame) -> pd.DataFrame:
    """Add `bench` = equal-weighted return of the stock's size decile that day.

    Deciles are formed on prior-month market cap (point-in-time, no look-ahead)
    and held for the following month. Rows with no assignable decile are dropped.
    """
    mo = pd.read_csv(D / "crsp_monthly.csv", parse_dates=["mthcaldt"])
    mo["ym"] = mo["mthcaldt"].dt.to_period("M")
    mo["decile"] = mo.groupby("ym")["mthcap"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False)
        if s.notna().sum() >= 10 else np.nan)
    mo["ym"] = mo["ym"] + 1                                  # effective next month
    decmap = mo.dropna(subset=["decile"])[["permno", "ym", "decile"]]

    daily = daily.copy()
    daily["ym"] = daily["date"].dt.to_period("M")
    daily = daily.merge(decmap, on=["permno", "ym"], how="left")
    daily = daily.dropna(subset=["decile"])
    daily["bench"] = daily.groupby(["date", "decile"])["ret"].transform("mean")
    return daily.drop(columns=["ym", "decile"])


# --------------------------------------------------------------------------- #
# pipeline A: Compustat SUE + market adjustment + rdq
# --------------------------------------------------------------------------- #
def events_compustat() -> pd.DataFrame:
    earn = pd.read_csv(D / "comp_earnings.csv", parse_dates=["datadate", "rdq"])
    earn = standardized_unexpected_earnings(earn).dropna(subset=["sue", "rdq"])
    link = pd.read_csv(D / "ccm_link.csv", parse_dates=["linkdt", "linkenddt"])
    link["linkenddt"] = link["linkenddt"].fillna(pd.Timestamp("2100-01-01"))
    m = earn.merge(link[["gvkey", "permno", "linkdt", "linkenddt"]], on="gvkey")
    m = m[(m["rdq"] >= m["linkdt"]) & (m["rdq"] <= m["linkenddt"])]
    m["permno"] = m["permno"].astype(int)
    return m.drop_duplicates(subset=["permno", "rdq"])[["permno", "rdq", "sue"]]


# --------------------------------------------------------------------------- #
# pipeline B: IBES analyst SUE + anndats, mapped ticker -> permno point-in-time
# --------------------------------------------------------------------------- #
def events_ibes() -> pd.DataFrame:
    actu = pd.read_csv(D / "ibes_actuals.csv")
    cons = pd.read_csv(D / "ibes_consensus.csv")
    sue = analyst_sue(actu, cons).dropna(subset=["sue"])     # ticker, anndats, sue

    link = pd.read_csv(D / "ibes_link.csv", parse_dates=["sdate", "edate"])
    m = sue.merge(link[["ticker", "permno", "sdate", "edate"]], on="ticker")
    m = m[(m["anndats"] >= m["sdate"]) & (m["anndats"] <= m["edate"])]  # point-in-time
    m["permno"] = m["permno"].astype(int)
    return m.drop_duplicates(subset=["permno", "anndats"])[["permno", "anndats", "sue"]]


def _era_quintile_means(res: pd.DataFrame, col: str) -> pd.DataFrame:
    """Mean `col` (%) indexed by era label x SUE quintile (columns 0..4)."""
    rows = {}
    for a, b in ERAS:
        s = res[(res["year"] >= a) & (res["year"] <= b)]
        if len(s) < 50:
            continue
        rows[f"{a}-{b}"] = s.groupby("q")[col].mean() * 100
    return pd.DataFrame(rows).T


def era_quintile_table(res: pd.DataFrame, col: str, label: str) -> None:
    """Print the era x quintile means behind the figure.

    The Q5-Q1 spread in ``era_table`` collapses two moving parts into one number;
    this shows whether a widening spread comes from good news being rewarded more
    or bad news being punished harder.
    """
    tbl = _era_quintile_means(res, col)
    tbl.columns = [f"Q{int(c) + 1}" for c in tbl.columns]
    print(f"\n=== {label} — mean CAR (%) by era x SUE quintile ===")
    print(tbl.to_string(float_format=lambda v: f"{v:6.2f}"))
    print(f"  {'Q5-Q1':<10}" + "".join(
        f"{tbl['Q5'][i] - tbl['Q1'][i]:>7.2f}" for i in tbl.index))


def plot_decay(res_a: pd.DataFrame, res_b: pd.DataFrame, out: Path) -> None:
    """2x2 grid: rows = announce/drift window, cols = pipeline A/B; a line per SUE quintile."""
    panels = [
        ("ann_car", res_a, "A: Compustat SUE + market-adj  |  announce [0,+1]"),
        ("ann_car", res_b, "B: IBES SUE + size-adj  |  announce [0,+1]"),
        ("drift_car", res_a, "A: Compustat SUE + market-adj  |  drift [+2,+63]"),
        ("drift_car", res_b, "B: IBES SUE + size-adj  |  drift [+2,+63]"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, (col, res, title) in zip(axes.ravel(), panels):
        tbl = _era_quintile_means(res, col)
        x = range(len(tbl.index))
        for q in range(5):
            if q in tbl.columns:
                ax.plot(x, tbl[q], marker="o", lw=2, color=Q_COLORS[q],
                        label=f"Q{q + 1}")
        ax.axhline(0, color="0.6", lw=0.8, zorder=0)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("mean CAR (%)")
        ax.set_xticks(list(x))
        ax.set_xticklabels(tbl.index, rotation=30, ha="right", fontsize=8)
        ax.grid(True, axis="y", color="0.9")
    axes[0, 1].legend(title="SUE quintile", fontsize=8, ncol=5,
                      loc="upper center", bbox_to_anchor=(0.5, 1.28))
    fig.suptitle("PEAD decay by SUE quintile and era: baseline (A) vs upgrade (B)",
                 fontsize=13, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"\nfigure -> {out}")


def main() -> None:
    daily = pd.read_csv(D / "crsp_daily.csv", parse_dates=["date"])

    # ---- A. baseline -----------------------------------------------------
    ev_a = events_compustat()
    res_a = event_car(daily, ev_a, event_date_col="rdq", market_adjust=True)
    res_a = quintile_within_month(res_a.dropna(subset=["ann_car", "drift_car"]), "rdq")

    # ---- B. upgrade ------------------------------------------------------
    daily_b = size_benchmark(daily)
    ev_b = events_ibes()
    res_b = event_car(daily_b, ev_b, event_date_col="anndats", benchmark_col="bench")
    res_b = quintile_within_month(res_b.dropna(subset=["ann_car", "drift_car"]), "anndats")

    print(f"A baseline (Compustat SUE / mkt-adj / rdq):   {len(res_a):>6} events")
    print(f"B upgrade  (IBES SUE / size-adj / anndats):   {len(res_b):>6} events")

    era_table(res_a, "A  Compustat SUE + market-adjust")
    era_table(res_b, "B  IBES SUE + size-adjust")

    era_quintile_table(res_a, "ann_car", "A baseline  announce [0,+1]")
    era_quintile_table(res_a, "drift_car", "A baseline  drift [+2,+63]")
    era_quintile_table(res_b, "ann_car", "B upgrade   announce [0,+1]")
    era_quintile_table(res_b, "drift_car", "B upgrade   drift [+2,+63]")

    print("\n=== full-sample drift CAR by SUE quintile (Q1=worst .. Q5=best) ===")
    quintile_ladder(res_a, "A baseline")
    quintile_ladder(res_b, "B upgrade")

    plot_decay(res_a, res_b, D / "figures" / "pead_decay.png")


if __name__ == "__main__":
    main()
