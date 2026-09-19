"""Which markets in the basket are actually impractical to trade? READ-ONLY.

    python tools/rank_market_liquidity.py
    python tools/rank_market_liquidity.py --since 2018-01-01

Every liquidity figure produced so far in this project has been RELATIVE -- the
share of a market's own open interest carried by the contract we held. That says
we picked the right contract within a market; it says nothing about the size of
the market. WTI shows a 23% share and is the most traded commodity future in the
world, while a serial month nobody trades can show 90% of a class nobody trades.

This measures absolute quantity for ALL 51 markets, not just the 24 built from
contracts: the continuous-series markets have classes too, resolved here through
wrds_cseries_info, so one bar can be applied to the whole basket.

Two things make the ranking honest:

* Contract sizes differ -- COMEX gold is 100 troy oz, platinum 50, CBOT grains
  5,000 bushels -- so contract counts are not comparable as money. The tool
  looks for a size field in wrds_contract_info and reports notional if one
  exists; if not it says so and the counts must be read within an asset class.
* Zero-volume days are size-free and currency-free. Any material share of them
  disqualifies a market whatever its contract count.

USE THIS AS AN EX-ANTE SCREEN ONLY. Dropping a market because it trades badly is
selection on the outcome, and reintroduces exactly the bias that makes the older
35-market basket's recent Sharpe hard to trust. Liquidity is knowable in advance;
performance is not.
"""

import argparse

import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_contracts import (
    CONTINUOUS_MARKETS, CONTRACT_MARKETS, SCHEMA)

SIZE_HINTS = ("size", "mult", "unit", "lot")

#: Currencies that settle and repatriate without an access regime. Volume alone
#: cannot see this: KOSPI 200 futures are among the most traded index contracts
#: in the world by contract count, and the won is not freely deliverable --
#: foreign participation needs an Investment Registration Certificate and the
#: offshore market is non-deliverable forwards. A market can be enormous and
#: still be closed to you.
#:
#: HKD is here because the peg makes it freely convertible in practice.
FREE_CCY = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD",
                      "SEK", "NOK", "DKK", "HKD", "SGD"})

#: Convertible but with an access regime, onshore settlement, or a
#: non-deliverable offshore market. The friction is registration, custody and
#: repatriation rather than spread.
RESTRICTED_CCY = frozenset({"KRW", "TWD", "CNY", "INR", "BRL", "ZAR", "MYR",
                            "THB", "IDR", "PHP", "RUB", "TRY", "CLP", "COP"})


def ccy_tier(ccy: str) -> str:
    if ccy in FREE_CCY:
        return "free"
    if ccy in RESTRICTED_CCY:
        return "RESTRICTED"
    return "unknown"


def find_size_column(loader) -> tuple:
    cols = loader.raw_sql("""
        select column_name, data_type
        from information_schema.columns
        where table_schema = %(s)s and table_name = 'wrds_contract_info'
        order by ordinal_position
    """, params={"s": SCHEMA})
    names = list(cols["column_name"])
    cand = [n for n in names
            if any(h in n.lower() for h in SIZE_HINTS)
            and "date" not in n.lower()]
    return names, cand


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2015-01-01")
    opts = ap.parse_args()

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        names, cand = find_size_column(loader)
        print(f"wrds_contract_info has {len(names)} columns; "
              f"size-like candidates: {cand or 'NONE'}")
        if not cand:
            print("  -> no contract-size field, so counts cannot be turned into")
            print("     notional. Compare within an asset class, not across.\n")

        # every market's class: the built ones are known, the continuous ones
        # are resolved from their series mnemonic
        want = {c: lab for c, (_, lab, _) in CONTRACT_MARKETS.items()}
        info = loader.raw_sql(f"""
            select dsmnem, clscode from {SCHEMA}.wrds_cseries_info
            where dsmnem in %(m)s
        """, params={"m": tuple(CONTINUOUS_MARKETS)})
        info["clscode"] = pd.to_numeric(info["clscode"], errors="coerce")
        cls_of = {}
        for _, r in info.dropna(subset=["clscode"]).iterrows():
            lab = CONTINUOUS_MARKETS[r["dsmnem"]][1]
            want.setdefault(int(r["clscode"]), lab)
        asset_class = {}
        for c, (k, lab, _) in CONTRACT_MARKETS.items():
            asset_class[lab] = k
        for k, lab in CONTINUOUS_MARKETS.values():
            asset_class[lab] = k
        cls_of = want
        print(f"resolved {len(cls_of)} classes for "
              f"{len(CONTRACT_MARKETS)} built + {len(CONTINUOUS_MARKETS)} "
              f"continuous markets")

        df = loader.raw_sql(f"""
            with per_day as (
                select i.clscode, min(i.isocurrcode) as ccy, v.date_,
                       max(v.openinterest) as front_oi,
                       sum(v.volume)       as day_volume,
                       max(v.settlement)   as px
                from {SCHEMA}.wrds_contract_info i
                join {SCHEMA}.wrds_fut_contract v on v.futcode = i.futcode
                where i.clscode in %(c)s and v.date_ >= %(since)s
                  and v.settlement is not null
                group by i.clscode, v.date_
            )
            select clscode, min(ccy) as ccy, count(*) as days,
                   percentile_cont(0.5) within group (order by front_oi) as oi,
                   percentile_cont(0.5) within group (order by day_volume) as vol,
                   sum(case when coalesce(day_volume,0) = 0 then 1 else 0 end) as zv,
                   sum(case when front_oi is null then 1 else 0 end) as no_oi
            from per_day group by clscode
        """, params={"c": tuple(int(c) for c in cls_of), "since": opts.since})
    finally:
        loader.close()

    if df.empty:
        raise SystemExit("no rows in that window")
    df["clscode"] = pd.to_numeric(df["clscode"]).astype("int64")
    for c in ("days", "oi", "vol", "zv", "no_oi"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["market"] = df["clscode"].map(cls_of)
    df["ccy"] = df["ccy"].astype(str)
    df["tier"] = df["ccy"].map(ccy_tier)
    df["class"] = df["market"].map(asset_class)
    df["zero_vol_pct"] = 100.0 * df["zv"] / df["days"]
    df["no_oi_pct"] = 100.0 * df["no_oi"] / df["days"]
    df = df.dropna(subset=["market"]).sort_values(
        ["class", "vol"], ascending=[True, False])

    print(f"\nsince {opts.since}, medians per day, in CONTRACTS\n")
    print(f"  {'market':<14}{'class':<11}{'ccy':>5}{'days':>6}"
          f"{'front OI':>11}{'volume/day':>12}{'zero-vol':>10}{'access':>12}")
    prev = None
    for _, r in df.iterrows():
        if r["class"] != prev:
            print()
            prev = r["class"]
        oi = f"{r['oi']:,.0f}" if pd.notna(r["oi"]) else "--"
        vo = f"{r['vol']:,.0f}" if pd.notna(r["vol"]) else "--"
        tier = "" if r["tier"] == "free" else r["tier"]
        print(f"  {r['market']:<14}{r['class']:<11}{r['ccy']:>5}"
              f"{int(r['days']):>6}{oi:>11}{vo:>12}"
              f"{r['zero_vol_pct']:>9.1f}%{tier:>12}")

    print("\n  SCREEN -- two independent reasons a market may be untradeable")
    gated = df[df["tier"] != "free"]
    if len(gated):
        print("    currency access:")
        for _, r in gated.iterrows():
            print(f"      {r['market']:<14}{r['ccy']:<5}{r['tier']}"
                  f"   (volume {r['vol']:,.0f}/day -- size is not the problem)")
    # A market with NO volume on every single day has no volume DATA. JGB 10Y
    # is among the most traded bond futures anywhere and reports 100% zero-volume
    # days here; GILT, from the same continuous-series route, reports 990,948 a
    # day. Reading absent data as an absent market is the error this project has
    # made before, so it is separated out rather than screened on.
    missing = df[(df["zero_vol_pct"] > 95) & (df["oi"].fillna(0) == 0)]
    if len(missing):
        print("    NO VOLUME DATA (not a liquidity finding -- verify the class):")
        for _, r in missing.iterrows():
            print(f"      {r['market']:<14}{r['ccy']:<5}"
                  f"{int(r['days'])} priced days but volume and open interest "
                  f"are empty")
    # Zero-volume days track HOLIDAY CALENDARS, not thinness: the markets nearest
    # the old 2% threshold were GILT, FTSE 100, SPI 200 and UK gas -- every one
    # sterling or Australian dollar, and FTSE 100 trades 439,080 contracts a day.
    # So thinness is judged against a market's own asset class instead.
    thin = df[~df.index.isin(missing.index)].copy()
    thin["class_median"] = thin.groupby("class")["vol"].transform("median")
    thin["vs_class"] = thin["vol"] / thin["class_median"]
    flagged = thin[(thin["vs_class"] < 0.15) | (thin["vol"].fillna(0) < 2000)]
    print("    thin relative to its asset class (below 15% of the class median,"
          "\n    or under 2,000 contracts a day):")
    if flagged.empty:
        print("      none")
    else:
        for _, r in flagged.sort_values("vs_class").iterrows():
            print(f"      {r['market']:<14}{r['class']:<11}"
                  f"{r['vol']:>10,.0f}/day = {r['vs_class'] * 100:.0f}% of the "
                  f"{r['class']} median")
    thin = flagged
    if thin.empty:
        print("    no market has >2% zero-volume days or a median under 500 "
              "contracts/day")
    else:
        for _, r in thin.iterrows():
            why = []
            if r["zero_vol_pct"] > 2:
                why.append(f"{r['zero_vol_pct']:.0f}% zero-volume days")
            if (r["vol"] or 0) < 500:
                why.append(f"median {r['vol']:,.0f} contracts/day")
            print(f"    {r['market']:<14}{r['class']:<11}{'; '.join(why)}")
    print("\n  HOW FAR THIS CAN BE TAKEN. Without a contract size, counts are")
    print("  comparable only between markets whose contracts are of similar")
    print("  size -- palladium against platinum (100 vs 50 troy oz) is a fair")
    print("  comparison; Australian 10-year against Bund is not, and neither is")
    print("  UK gas, whose lot is a month of 1,000 therms a day, against Brent.")
    print("  Several markets flagged above are flagged for their units, not")
    print("  their liquidity. The screen raises questions; it does not answer")
    print("  them.")


if __name__ == "__main__":
    main()
