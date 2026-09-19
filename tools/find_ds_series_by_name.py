"""Find every CONTINUOUS SERIES for an underlying, and see which class it sits on.

    python tools/find_ds_series_by_name.py --plan
    python tools/find_ds_series_by_name.py GOLD "T-NOTE" YEN

The complement of ``survey_ds_classes.py``. That tool searches the CONTRACT table
and so sees every class, including live ones. This searches the CONTINUOUS-SERIES
table, which is what ``BASKET`` can actually reference.

Why both are needed. ``resolve_ds_series.py`` showed that 12 of the 17 rebuild
targets -- all of them US markets -- are live classes with NO continuous series,
while the basket's existing gold/silver/US-rates entries are continuous series on
DEAD classes. So for those markets the class and the series appear to have come
apart: the tradeable history is on one clscode and the usable series on another.

This prints, per underlying, every front-month series that exists WITH the clscode
it is pinned to, so the question "does a usable long series exist for gold at all,
under any class?" gets a yes/no answer instead of an inference. Read-only.

A series emits rows past the date its prices stop (pitfall 4 in ds_futures.py),
so counting ``_name_ = 'Value_'`` rows overstates coverage: COMEX gold has rows
to 2026-06 but settlements only to 2022-11. These queries therefore require a
non-null settlement, matching what ``fetch_series`` keeps after its dropna.
"""

import argparse
import re

import pandas as pd

from portfolio_management.dataloader import create_data_loader

SCHEMA = "tr_ds_fut"
VALUE_ROW = "Value_"
FRONT = re.compile(r"^[A-Z]+CS00$")     # front-month, first-position roll only

# underlying -> (search patterns, clscode the rebuild plan wanted)
PLAN = {
    "GOLD":      (["%GOLD%"], 1508),
    "SILVER":    (["%SILVER%"], 1574),
    "US30Y":     (["%T-BOND%", "%T BOND%", "%TREASURY BOND%", "%30 YR%"], 2441),
    "US10Y":     (["%10 YR%", "%10 YRS%", "%10-YEAR%", "%T-NOTE%"], 3896),
    "US5Y":      (["%5 YR%", "%5 YRS%", "%5-YEAR%"], 1997),
    "US2Y":      (["%2 YR%", "%2 YRS%", "%2-YEAR%"], 2523),
    "SP500":     (["%S&P 500%", "%S&P500%", "%MINI S&P%"], 1035),
    "JPYUSD":    (["%YEN%"], 2125),
    "GBPUSD":    (["%STERLING%", "%BRITISH POUND%"], 2059),
    "CHFUSD":    (["%FRANC%"], 2094),
    "CADUSD":    (["%CANADIAN DOLLAR%"], 2072),
    "AUDUSD":    (["%AUSTRALIAN DOLLAR%"], 2047),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("patterns", nargs="*", help="substrings to search (case-insensitive)")
    ap.add_argument("--plan", action="store_true", help="search the 12 unresolved targets")
    ap.add_argument("--min-months", type=int, default=60)
    args = ap.parse_args()

    if args.plan:
        jobs = PLAN
    elif args.patterns:
        jobs = {p: ([f"%{p.upper()}%"], None) for p in args.patterns}
    else:
        raise SystemExit(__doc__)

    all_pats = sorted({p for pats, _ in jobs.values() for p in pats})
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        df = loader.raw_sql(f"""
            select i.clscode, i.dsmnem, i.calcseriesname, i.isocurrcode,
                   (select count(*) from {SCHEMA}.wrds_fut_series v
                    where v.calcseriescode = i.calcseriescode
                      and v._name_ = %(nm)s
                      and v.settlement is not null) as n_px,
                   (select min(v.date_) from {SCHEMA}.wrds_fut_series v
                    where v.calcseriescode = i.calcseriescode
                      and v._name_ = %(nm)s
                      and v.settlement is not null) as first_px,
                   (select max(v.date_) from {SCHEMA}.wrds_fut_series v
                    where v.calcseriescode = i.calcseriescode
                      and v._name_ = %(nm)s
                      and v.settlement is not null) as last_px
            from {SCHEMA}.wrds_cseries_info i
            where upper(i.calcseriesname) like any(%(pats)s)
              and i.dsmnem ~ '^[A-Z]+CS00$'
""", params={"pats": all_pats, "nm": VALUE_ROW})
    finally:
        loader.close()

    if df.empty:
        raise SystemExit("no front-month continuous series matched any pattern")

    df["clscode"] = pd.to_numeric(df["clscode"]).astype("int64")
    df["n_px"] = pd.to_numeric(df["n_px"]).astype("int64")
    for c in ("first_px", "last_px"):
        df[c] = pd.to_datetime(df[c])
    df["name_u"] = df["calcseriesname"].fillna("").str.upper()
    df = df[df["n_px"] >= args.min_months * 21]

    for label, (pats, want) in jobs.items():
        rx = "|".join(p.strip("%").replace("&", "&") for p in pats)
        rows = df[df["name_u"].str.contains(rx, regex=True, na=False)]
        tgt = f"  (plan wanted clscode {want})" if want else ""
        print(f"\n=== {label}{tgt} ===")
        if rows.empty:
            print(f"  no front-month series with >= {args.min_months} months")
            continue
        print(f"  {'dsmnem':<11}{'clscode':>8}{'ccy':>5}{'obs':>8}"
              f"{'first':>10}{'last':>12}  name")
        for _, r in rows.sort_values("first_px").iterrows():
            hit = " <-- plan's class" if want and r["clscode"] == want else ""
            first, last = f"{r['first_px']:%Y-%m}", f"{r['last_px']:%Y-%m-%d}"
            print(f"  {str(r['dsmnem']):<11}{r['clscode']:>8}"
                  f"{str(r['isocurrcode']):>5}{r['n_px']:>8}"
                  f"{first:>10}{last:>12}"
                  f"  {str(r['calcseriesname'])[:38]}{hit}")
        best = rows.sort_values("first_px").iloc[0]
        print(f"  -> longest history: {best['dsmnem']} on clscode {best['clscode']}"
              f", {best['first_px']:%Y-%m}..{best['last_px']:%Y-%m}")


if __name__ == "__main__":
    main()
