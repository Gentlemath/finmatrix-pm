"""Which roll convention should the futures basket use? Decide on evidence.

For every market in the basket, compare the CS00..CS05 roll variants on the
things that actually matter:

  rows        - history length (the whole point of using futures)
  cmonth      - contract month, and whether it really looks like YYYYMM.
                Without it, roll days cannot be masked and the return series
                carries the carry gap at every roll.
  volume / oi - liquidity evidence; also the only way to check whether a
                "volume switch" rule really switches when volume moves.

Why this is needed: Datastream populates DIFFERENT item sets for different roll
variants of the SAME market. Measured on the Bund: CS00/CS01 carry price,
contract month, life, volume and open interest; CS03 carries price and contract
month only; CS02 has life but NO contract month; CS05 has price alone. And
coverage varies wildly - CZNCS01 (US 10Y, roll 1) holds 1,401 rows from 2024
while CZNCS00 holds 33,512 from 1998.

So a blanket choice of roll method has to be justified, not assumed.
Read-only; one aggregate query per roll method.
"""

import pandas as pd

from portfolio_management.dataloader import create_data_loader

SCHEMA = "tr_ds_fut"
VALUE_ROW = "Value_"
ROLLS = [0, 1, 2, 3, 4, 5]
MIN_ROWS = 2000                     # ~8 years of daily data

# market code -> label (the basket, with the CSxx suffix stripped)
MARKETS = {
    "GDX": "DAX", "GEX": "ESTOXX50", "LSX": "FTSE100", "ONA": "NIKKEI225",
    "AAP": "SPI200", "HSI": "HANGSENG", "KKX": "KOSPI200",
    "CZN": "US10Y", "CZB": "US30Y", "CZF": "US5Y", "CZT": "US2Y",
    "GGE": "BUND", "GBE": "BOBL", "GEB": "SCHATZ", "LIG": "GILT",
    "SJG": "JGB10Y", "AGB": "AUS10Y", "ATY": "AUS3Y",
    "NDX": "USDINDEX", "NEU": "EURUSD", "NDY": "USDJPY", "NDF": "USDCHF",
    "NSY": "GBPJPY",
    "LLC": "BRENT", "LTC": "WTI", "NNG": "NATGAS",
    "CZG": "GOLD", "CZI": "SILVER", "LCP": "COPPER", "LAH": "ALUMINIUM",
    "LZZ": "ZINC", "LNI": "NICKEL",
    "NSB": "SUGAR", "NKC": "COFFEE", "NCC": "COCOA", "LWH": "WHEAT_LIF",
    "PMW": "WHEAT_MAT", "PCO": "CORN_MAT", "NJO": "ORANGEJUICE",
}


def scan(loader, roll: int) -> pd.DataFrame:
    mnems = tuple(f"{m}CS0{roll}" for m in MARKETS)
    df = loader.raw_sql(f"""
        select i.dsmnem, i.calcseriescode, i.isocurrcode,
               count(*)                as n_rows,
               min(v.date_)            as first_dt,
               max(v.date_)            as last_dt,
               count(v.cmonth)         as n_cmonth,
               count(v.life)           as n_life,
               count(v.volume)         as n_volume,
               count(v.openinterest)   as n_oi,
               sum(case when v.cmonth >= 190001 and v.cmonth <= 210012
                        then 1 else 0 end) as n_yyyymm
        from {SCHEMA}.wrds_cseries_info i
        join {SCHEMA}.wrds_fut_series v
          on v.calcseriescode = i.calcseriescode and v._name_ = %(nm)s
        where i.dsmnem in %(m)s
        group by i.dsmnem, i.calcseriescode, i.isocurrcode
    """, params={"m": mnems, "nm": VALUE_ROW})
    if df.empty:
        return df
    for c in ("n_rows", "n_cmonth", "n_life", "n_volume", "n_oi", "n_yyyymm"):
        df[c] = pd.to_numeric(df[c]).astype("int64")
    df["roll"] = roll
    df["market"] = df["dsmnem"].str[:-4]
    df["label"] = df["market"].map(MARKETS)
    df["first_dt"] = pd.to_datetime(df["first_dt"])
    df["last_dt"] = pd.to_datetime(df["last_dt"])
    df["years"] = (df["last_dt"] - df["first_dt"]).dt.days / 365.25
    # cmonth is usable only if nearly every row carries a YYYYMM value
    df["roll_ok"] = df["n_yyyymm"] / df["n_rows"] > 0.95
    df["has_vol"] = df["n_volume"] / df["n_rows"] > 0.5
    return df


def main() -> None:
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    frames = []
    try:
        for roll in ROLLS:
            print(f"scanning CS0{roll} ...", flush=True)
            f = scan(loader, roll)
            if not f.empty:
                frames.append(f)
    finally:
        loader.close()

    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv("local_data/ds_roll_comparison.csv", index=False)

    n_mkt = len(MARKETS)
    print(f"\n=== summary by roll method (of {n_mkt} markets) ===")
    print(f"  {'roll':<6}{'found':>7}{'>=2k rows':>11}{'roll_ok':>9}"
          f"{'volume':>8}{'med yrs':>9}{'earliest':>10}")
    summary = []
    for roll in ROLLS:
        d = all_df[all_df["roll"] == roll]
        if d.empty:
            print(f"  CS0{roll} {'':<3}{0:>7}")
            continue
        long_enough = d[d["n_rows"] >= MIN_ROWS]
        usable = long_enough[long_enough["roll_ok"]]
        row = {"roll": roll, "found": len(d), "long": len(long_enough),
               "usable": len(usable), "vol": int(long_enough["has_vol"].sum()),
               "med_years": long_enough["years"].median(),
               "earliest": long_enough["first_dt"].min()}
        summary.append(row)
        earliest = f"{row['earliest']:%Y-%m}"
        print(f"  CS0{roll} {'':<3}{row['found']:>7}{row['long']:>11}"
              f"{row['usable']:>9}{row['vol']:>8}{row['med_years']:>9.1f}"
              f"{earliest:>10}")

    s = pd.DataFrame(summary)
    # decide: most markets with a USABLE contract month, then longest history
    best = s.sort_values(["usable", "med_years"], ascending=False).iloc[0]
    roll = int(best["roll"])
    print(f"\n=== recommendation: CS0{roll} ===")
    print(f"  {int(best['usable'])}/{n_mkt} markets have >={MIN_ROWS} rows AND a "
          f"usable contract month; median history {best['med_years']:.1f} years")

    d = all_df[all_df["roll"] == roll].set_index("label")
    print(f"\n=== per-market detail for CS0{roll} ===")
    print(f"  {'label':<13}{'ccy':<5}{'rows':>8}{'first':>10}{'last':>10}"
          f"{'yrs':>6}{'roll_ok':>9}{'vol':>6}")
    for lab in sorted(MARKETS.values()):
        if lab not in d.index:
            print(f"  {lab:<13}{'--':<5}{'MISSING':>8}")
            continue
        r = d.loc[lab]
        first, last = f"{r['first_dt']:%Y-%m}", f"{r['last_dt']:%Y-%m}"
        print(f"  {lab:<13}{str(r['isocurrcode']):<5}{r['n_rows']:>8,}"
              f"{first:>10}{last:>10}{r['years']:>6.1f}"
              f"{str(bool(r['roll_ok'])):>9}{str(bool(r['has_vol'])):>6}")

    bad = d[~d["roll_ok"].astype(bool)]
    if len(bad):
        print(f"\n!! {len(bad)} market(s) lack a usable contract month under "
              f"CS0{roll}: {', '.join(bad.index)}")
        print("   For these, check another variant in "
              "local_data/ds_roll_comparison.csv, or derive roll dates from "
              "wrds_contract_info.lasttrddate.")

    print("\n-> local_data/ds_roll_comparison.csv (all variants, all markets)")


if __name__ == "__main__":
    main()
