"""Cache IBES analyst EPS data for the analyst-based SUE upgrade (PEAD).

Run in YOUR terminal (needs your WRDS account + network). Licensed data —
local_data/ is gitignored; do not commit the output.

For firms in the cached S&P 500 universe (via the IBES<->CRSP link):
  - ibcrsphist link             -> ibes_link.csv       (ibes ticker <-> permno, valid dates)
  - actu_epsus (actuals)        -> ibes_actuals.csv    (actual quarterly EPS + anndats)
  - statsumu_epsus (consensus)  -> ibes_consensus.csv  (median/mean/stdev by statpers/fpedats)

Offline we build SUE = (actual - consensus median) / dispersion, taken from the
last consensus BEFORE the announcement (anndats), then map ticker->permno.
"""

from pathlib import Path

import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
START = "1984-01-01"

# ibcrsphist (WRDS ICLINK) columns are standard: ticker/permno/sdate/edate/score.
LINK_SQL = "select ticker, permno, sdate, edate, score from wrdsapps_link_crsp_ibes.ibcrsphist"
ACTUALS_SQL = (
    "select ticker, pends, anndats, value from ibes.actu_epsus "
    "where ticker in %(t)s and measure='EPS' and pdicity='QTR' and usfirm=1 "
    "and anndats >= %(s)s order by ticker, pends"
)
CONSENSUS_SQL = (
    "select ticker, statpers, fpedats, medest, meanest, stdev, numest "
    "from ibes.statsumu_epsus "
    "where ticker in %(t)s and measure='EPS' and fiscalp='QTR' and fpi='6' "
    "and usfirm=1 and statpers >= %(s)s order by ticker, fpedats, statpers"
)


def main() -> None:
    permnos = set(pd.read_csv(OUT / "sp500_constituents.csv")["permno"].astype(int))
    w = create_data_loader("wrds")
    try:
        print("1/3 IBES<->CRSP link (ibcrsphist)...")
        link = w.raw_sql(LINK_SQL)
        link = link[link["permno"].isin(permnos)]
        link.to_csv(OUT / "ibes_link.csv", index=False)
        tickers = tuple(sorted(link["ticker"].dropna().unique()))
        print(f"    {len(tickers)} IBES tickers map to our universe")

        print("2/3 IBES actuals (actu_epsus, quarterly EPS)...")
        actu = w.raw_sql(ACTUALS_SQL, params={"t": tickers, "s": START})
        actu.to_csv(OUT / "ibes_actuals.csv", index=False)
        print(f"    {len(actu)} actual rows")

        print("3/3 IBES consensus (statsumu_epsus, 1-qtr-ahead EPS)...")
        cons = w.raw_sql(CONSENSUS_SQL, params={"t": tickers, "s": START})
        cons.to_csv(OUT / "ibes_consensus.csv", index=False)
        print(f"    {len(cons)} consensus rows")
    finally:
        w.close()


if __name__ == "__main__":
    main()
