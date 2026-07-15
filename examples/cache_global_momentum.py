"""Cache per-country momentum DECILE returns from the JKP Global Factor Data.

The heavy work runs in-database: for each (country, month) it ranks large-cap
stocks by 12-1 momentum (`ret_12_1`) into deciles and cap-weights next-month
excess returns (`ret_exc_lead1m`). We pull only the aggregated decile table
(~tens of thousands of rows) and build the long-short spread + stats offline.

Filtered to mega/large caps so it is comparable to the S&P 500 (large-cap) work.

Run in YOUR terminal (needs your WRDS account + network). Licensed data —
local_data/ is gitignored; do not commit the output.
"""

from pathlib import Path

import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
MARKETS = ["USA", "CHN", "JPN", "GBR", "DEU", "FRA", "HKG", "KOR"]
START = "1990-01-01"

# One country at a time: each query is filtered (small) and prints progress, so
# nothing hangs on a full-table scan. The JKP primary-security screen
# (common / primary_sec / obs_main = 1) dedupes to one row per firm-month.
DECILE_SQL = """
with ranked as (
    select date, me, ret_exc_lead1m,
           ntile(10) over (partition by date order by ret_12_1) as decile
    from contrib_global_factor.global_factor
    where excntry = %(cntry)s
      and size_grp in ('mega', 'large')
      and common = 1 and primary_sec = 1 and obs_main = 1
      and ret_12_1 is not null
      and ret_exc_lead1m is not null
      and me is not null
      and date >= %(start)s
)
select date, decile,
       sum(me * ret_exc_lead1m) / sum(me) as vw_ret,
       count(*) as n
from ranked
group by date, decile
order by date, decile
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = create_data_loader("wrds")
    frames = []
    try:
        for cntry in MARKETS:
            print(f"  querying {cntry} ...", flush=True)
            try:
                df = w.raw_sql(DECILE_SQL, params={"cntry": cntry, "start": START})
            except Exception as exc:
                print(f"    [FAILED] {cntry}: {type(exc).__name__}: {exc}")
                continue
            if df.empty:
                print(f"    {cntry}: no rows (check the country code)")
                continue
            df.insert(0, "excntry", cntry)
            frames.append(df)
            print(f"    {cntry}: {len(df)} decile-months, "
                  f"{df['date'].min()} .. {df['date'].max()}")
    finally:
        w.close()

    if not frames:
        print("no data pulled")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT / "global_momentum_deciles.csv", index=False)
    print(f"\nsaved {len(out)} rows for {out['excntry'].nunique()} markets -> "
          "local_data/global_momentum_deciles.csv")


if __name__ == "__main__":
    main()
