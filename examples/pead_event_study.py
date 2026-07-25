"""PEAD event study on cached S&P 500 data — reproduces the drift's decay.

Uses portfolio_management.strategy.{standardized_unexpected_earnings, event_car}.
Reads the cached files written by cache_pead_data.py (licensed data, gitignored):
  comp_earnings.csv, ccm_link.csv, crsp_daily.csv, crsp_monthly.csv

Shows, by era and firm size, the SUE quintile (Q5-Q1) spread in the
announcement window [0,+1] vs the drift window [+2,+63]. The historical PEAD
result: the drift shrinks (especially for large caps) while the announcement-day
reaction grows — the surprise gets priced immediately instead of drifting.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management.strategy import event_car, standardized_unexpected_earnings

D = Path("local_data")
ERAS = [(1985, 1994), (1995, 2000), (2001, 2006), (2007, 2015), (2016, 2026)]


def load_events() -> pd.DataFrame:
    """SUE per announcement, point-in-time mapped to a CRSP permno via CCM."""
    earn = pd.read_csv(D / "comp_earnings.csv", parse_dates=["datadate", "rdq"])
    earn = standardized_unexpected_earnings(earn)          # adds `sue`
    earn = earn.dropna(subset=["sue", "rdq"])

    link = pd.read_csv(D / "ccm_link.csv", parse_dates=["linkdt", "linkenddt"])
    link["linkenddt"] = link["linkenddt"].fillna(pd.Timestamp("2100-01-01"))
    m = earn.merge(link[["gvkey", "permno", "linkdt", "linkenddt"]], on="gvkey", how="inner")
    m = m[(m["rdq"] >= m["linkdt"]) & (m["rdq"] <= m["linkenddt"])]
    m["permno"] = m["permno"].astype(int)
    return m.drop_duplicates(subset=["permno", "rdq"])[["permno", "rdq", "sue"]]


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


def main() -> None:
    events = load_events()
    print(f"announcements with SUE + permno: {len(events)}")

    daily = pd.read_csv(D / "crsp_daily.csv", parse_dates=["date"])
    res = event_car(daily, events).dropna(subset=["ann_car", "drift_car"])
    print(f"announcements with event-time returns: {len(res)}")

    # size at announcement from monthly market cap; SUE quintile within each month
    mo = pd.read_csv(D / "crsp_monthly.csv", parse_dates=["mthcaldt"])
    mo["ym"] = mo["mthcaldt"].dt.to_period("M")
    res["ym"] = res["rdq"].dt.to_period("M")
    res = res.merge(mo[["permno", "ym", "mthcap"]], on=["permno", "ym"], how="left")
    med = res.groupby("ym")["mthcap"].transform("median")
    res["size"] = np.where(res["mthcap"] >= med, "large", "small")
    res["q"] = res.groupby("ym")["sue"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False)
        if s.notna().sum() >= 5 else np.nan)
    res = res.dropna(subset=["q"])
    res["q"] = res["q"].astype(int)
    res["year"] = res["rdq"].dt.year

    era_table(res, "ALL S&P 500 announcers")
    era_table(res[res["size"] == "large"], "LARGE (above-median cap)")
    era_table(res[res["size"] == "small"], "SMALL (below-median cap)")


if __name__ == "__main__":
    main()
