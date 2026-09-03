"""Dump one futures series in clean form, for eyeballing.

Usage:  python tools/sample_ds_futures.py [DSMNEM] [START] [END]
        python tools/sample_ds_futures.py GGECS03 2015-01-01 2016-12-31

Writes local_data/sample_<DSMNEM>.csv and prints the rows around each roll.

Reminder of the table's shape (see cache_futures_data_wrds.py): wrds_fut_series
is a SAS transpose, ~5 rows per date. Only `_name_ = 'Value_'` carries the
series; in that row `cmonth` is Datastream item 25 (contract month, YYYYMM) and
`life` is item 26 (calendar days to the contract's last trading day).
"""

import sys

import pandas as pd

from portfolio_management.dataloader import create_data_loader

SCHEMA = "tr_ds_fut"
VALUE_ROW = "Value_"


def fetch(loader, mnem: str, start: str, end: str):
    info = loader.raw_sql(f"""
        select i.calcseriescode, i.dsmnem, i.calcseriesname, i.isocurrcode,
               i.rollmethodcode, i.rollmethoddesc,
               (select count(*) from {SCHEMA}.wrds_fut_series v
                where v.calcseriescode = i.calcseriescode
                  and v._name_ = %(nm)s) as n_rows
        from {SCHEMA}.wrds_cseries_info i
        where i.dsmnem = %(m)s
    """, params={"m": mnem, "nm": VALUE_ROW})
    if info.empty:
        raise SystemExit(f"{mnem} not found")
    info["n_rows"] = pd.to_numeric(info["n_rows"]).astype("int64")
    row = info.sort_values("n_rows").iloc[-1]

    df = loader.raw_sql(f"""
        select date_, settlement, cmonth, life, volume, openinterest
        from {SCHEMA}.wrds_fut_series
        where calcseriescode = %(c)s and _name_ = %(nm)s
          and date_ between %(s)s and %(e)s
        order by date_
    """, params={"c": int(row["calcseriescode"]), "nm": VALUE_ROW,
                 "s": start, "e": end})
    for c in ("settlement", "cmonth", "life", "volume", "openinterest"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["date"] = pd.to_datetime(df["date_"])
    df = df.drop(columns=["date_"]).set_index("date").sort_index()
    df["ret_%"] = df["settlement"].pct_change() * 100
    df["is_roll"] = df["cmonth"].diff().fillna(0.0) != 0.0
    return row, df


def main() -> None:
    mnem = sys.argv[1] if len(sys.argv) > 1 else "GGECS03"
    start = sys.argv[2] if len(sys.argv) > 2 else "2015-01-01"
    end = sys.argv[3] if len(sys.argv) > 3 else "2016-12-31"

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        row, df = fetch(loader, mnem, start, end)
    finally:
        loader.close()

    print(f"{mnem}  code {int(row['calcseriescode'])}  {row['isocurrcode']}")
    print(f"  {row['calcseriesname']}")
    print(f"  roll {int(row['rollmethodcode'])}: {row['rollmethoddesc']}")
    print(f"  {int(row['n_rows']):,} rows total; window {start}..{end} "
          f"has {len(df)} rows, {df.index.nunique()} unique dates\n")

    out = f"local_data/sample_{mnem}.csv"
    df.to_csv(out)

    rolls = df.index[df["is_roll"]]
    print(f"=== {len(rolls)} rolls in window ===")
    cols = ["settlement", "cmonth", "life", "volume", "openinterest", "ret_%"]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        for r in rolls:
            i = df.index.get_loc(r)
            win = df.iloc[max(0, i - 3):i + 3][cols]
            print(f"\n-- roll on {r:%Y-%m-%d} --")
            print(win.to_string(float_format=lambda v: f"{v:,.2f}"))

    normal = df.loc[~df["is_roll"], "ret_%"].abs().mean()
    at_roll = df.loc[df["is_roll"], "ret_%"].abs().mean()
    print(f"\nmean |ret| on roll days   {at_roll:.3f}%")
    print(f"mean |ret| on normal days {normal:.3f}%   ratio {at_roll / normal:.1f}x")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
