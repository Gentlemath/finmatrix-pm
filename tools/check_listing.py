"""Which listing is a market, and does that listing actually trade? READ-ONLY.

    python tools/check_listing.py NIKKEI
    python tools/check_listing.py "JGB" "T-BOND" --min-obs 2000
    python tools/check_listing.py --basket           # every market in the basket

The same underlying is often listed on more than one exchange, and the offshore
listing can be nearly dead while carrying a full, plausible price history. The
basket's JGB 10-year was `SJGCS00`, "SGX DT-10YR JGB CONTINUOUS" -- the Singapore
listing -- with 27,568 settlement prices, normal volatility, normal correlations,
no gaps, no spikes, and **twenty-six days of non-zero volume out of 27,539**, the
largest being 80 contracts. Tokyo's `JGBCS00` trades on 49,242 days of 58,804,
peaking at 151,075, and starts eighteen years earlier.

Every check this project runs passed the Singapore listing, because they all
measured price quality or RELATIVE liquidity -- the share of a market's own open
interest held by the contract we chose, which a market nobody trades satisfies
perfectly. Absolute volume is the only thing that separates "has prices" from
"has a market".

For each matching continuous series this prints the exchange its class belongs
to and how much of its contract history actually traded, so the listings can be
compared side by side before one is adopted.
"""

import argparse

import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_contracts import (
    CONTINUOUS_MARKETS, SCHEMA)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("patterns", nargs="*", help="substrings of the series name")
    ap.add_argument("--basket", action="store_true",
                    help="check every continuous market the basket holds")
    ap.add_argument("--min-obs", type=int, default=1000,
                    help="ignore series with fewer priced contract-days")
    opts = ap.parse_args()
    if not (opts.patterns or opts.basket):
        raise SystemExit(__doc__)

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        if opts.basket:
            info = loader.raw_sql(f"""
                select dsmnem, clscode, calcseriesname
                from {SCHEMA}.wrds_cseries_info where dsmnem in %(m)s
            """, params={"m": tuple(CONTINUOUS_MARKETS)})
        else:
            pats = [f"%{p.upper()}%" for p in opts.patterns]
            info = loader.raw_sql(f"""
                select dsmnem, clscode, calcseriesname
                from {SCHEMA}.wrds_cseries_info
                where upper(calcseriesname) like any(%(p)s)
                  and dsmnem ~ '^[A-Z]+CS00$'
            """, params={"p": pats})
        if info.empty:
            raise SystemExit("no continuous series matched")
        info["clscode"] = pd.to_numeric(info["clscode"], errors="coerce")
        info = info.dropna(subset=["clscode"]).drop_duplicates("dsmnem")
        info["clscode"] = info["clscode"].astype("int64")

        act = loader.raw_sql(f"""
            select i.clscode,
                   count(v.settlement)                             as px,
                   count(v.volume)                                 as vol_field,
                   sum(case when v.volume > 0 then 1 else 0 end)   as vol_gt0,
                   max(v.volume)                                   as max_vol,
                   max(v.openinterest)                             as max_oi,
                   min(v.date_) as first_, max(v.date_) as last_
            from {SCHEMA}.wrds_contract_info i
            join {SCHEMA}.wrds_fut_contract v on v.futcode = i.futcode
            where i.clscode in %(c)s
            group by i.clscode
        """, params={"c": tuple(int(c) for c in info["clscode"])})
    finally:
        loader.close()

    act["clscode"] = pd.to_numeric(act["clscode"]).astype("int64")
    for c in ("px", "vol_field", "vol_gt0", "max_vol", "max_oi"):
        act[c] = pd.to_numeric(act[c], errors="coerce").fillna(0)
    for c in ("first_", "last_"):
        act[c] = pd.to_datetime(act[c])
    df = info.merge(act, on="clscode", how="left").fillna({"px": 0})
    df = df[df["px"] >= opts.min_obs].copy()
    if df.empty:
        raise SystemExit(f"nothing with >= {opts.min_obs} priced contract-days")
    df["traded_pct"] = 100.0 * df["vol_gt0"] / df["px"].replace(0, pd.NA)
    held = {v[1]: k for k, v in CONTINUOUS_MARKETS.items()}
    inv = {k: v[1] for k, v in CONTINUOUS_MARKETS.items()}
    df["held"] = df["dsmnem"].map(lambda m: inv.get(m, ""))
    df = df.sort_values(["traded_pct"], ascending=False)

    print(f"  {'dsmnem':<10}{'cls':>6}{'px days':>9}{'traded':>9}"
          f"{'max vol':>12}{'first':>9}{'last':>9}  name")
    for _, r in df.iterrows():
        tp = f"{r['traded_pct']:.0f}%" if pd.notna(r["traded_pct"]) else "--"
        flag = "  <= IN BASKET" if r["held"] else ""
        first = f"{r['first_']:%Y-%m}" if pd.notna(r["first_"]) else "--"
        last = f"{r['last_']:%Y-%m}" if pd.notna(r["last_"]) else "--"
        print(f"  {r['dsmnem']:<10}{r['clscode']:>6}{int(r['px']):>9,}{tp:>9}"
              f"{r['max_vol']:>12,.0f}{first:>9}{last:>9}"
              f"  {str(r['calcseriesname'])[:32]}{flag}")

    # The PERCENTAGE traded is confounded by curve depth, exactly as the
    # share-of-open-interest diagnostic was. LME lists daily prompt dates out to
    # three months and then monthlies to ten years, so an LME class holds a huge
    # number of contract-days that never trade: copper reports 12% while its
    # busiest day is 164,009 contracts. Depth is not death.
    #
    # Maximum volume is the discriminator that is not confounded. Every market
    # in the basket peaks above 39,000 contracts; the Singapore JGB listing that
    # had to be removed peaked at 80.
    dead = df[(df["max_vol"] < 1000) & (df["px"] > 5000)]
    if len(dead):
        print("\n  PRICES WITHOUT A MARKET -- a long history whose busiest day"
              "\n  never reached 1,000 contracts:")
        for _, r in dead.iterrows():
            print(f"    {r['dsmnem']:<10}{int(r['px']):,} priced days, "
                  f"{int(r['vol_gt0'])} with volume, max "
                  f"{r['max_vol']:,.0f}  {str(r['calcseriesname'])[:40]}"
                  f"{'  <= IN BASKET' if r['held'] else ''}")
    if opts.basket:
        missing = sorted(set(held) - set(df["held"]))
        if missing:
            print(f"\n  not reported (under --min-obs or unresolved): {missing}")


if __name__ == "__main__":
    main()
