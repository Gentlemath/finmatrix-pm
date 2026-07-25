"""Cache S&P 500 data for the PEAD (post-earnings-announcement drift) event study.

Run in YOUR terminal (needs your WRDS account + network). Licensed data —
local_data/ is gitignored; do not commit the output.

PEAD is an EVENT-TIME effect measured in trading days after the announcement, so
this pulls DAILY returns (not monthly): the drift now compresses into the first
days, which a monthly panel would miss. For firms in the cached S&P 500 universe:

  - CCM gvkey<->permno link                     -> ccm_link.csv
  - Compustat quarterly earnings + rdq           -> comp_earnings.csv  (SUE + event dates)
  - CRSP CIZ DAILY returns (permno/date/ret)     -> crsp_daily.csv     (LARGE: ~hundreds of MB)

Offline we compute SUE, align returns to event time relative to rdq, and measure
the announcement-window vs drift-window CARs by era and size.

Size/time note: the daily pull is the heavy part (~10-15M rows over 1985-2025).
It is chunked by year with progress. To shrink it, raise START or trim the
universe. Size groups for the large/small split come from the monthly mthcap in
crsp_monthly.csv, so daily only needs permno/date/ret.
"""

from pathlib import Path

import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
START_YEAR = 1985          # a few years before the sample so SUE has history
END_YEAR = 2026

DAILY_SQL = (
    "select permno, dlycaldt as date, dlyret as ret from crsp.dsf_v2 "
    "where permno in %(permnos)s and dlycaldt >= %(a)s and dlycaldt <= %(b)s "
    "order by permno, dlycaldt"
)


def main() -> None:
    cons = pd.read_csv(OUT / "sp500_constituents.csv")
    permnos = tuple(int(p) for p in cons["permno"].unique())

    w = create_data_loader("wrds")
    try:
        print("1/3 CCM link (gvkey <-> permno)...")
        link = w.get_ccm_link()
        link.to_csv(OUT / "ccm_link.csv", index=False)
        gvkeys = link.loc[link["permno"].isin(set(permnos)), "gvkey"].dropna().unique().tolist()
        print(f"    {len(link)} link rows; {len(gvkeys)} gvkeys map to our universe")

        print("2/3 Compustat quarterly earnings (comp.fundq) + rdq...")
        earn = w.get_compustat_quarterly(
            gvkeys=gvkeys,
            start=f"{START_YEAR}-01-01",
            items=("gvkey", "datadate", "rdq", "fyearq", "fqtr",
                   "epsfxq", "epspxq", "ibq", "cshoq", "atq"),
        )
        earn.to_csv(OUT / "comp_earnings.csv", index=False)
        print(f"    {len(earn)} quarterly rows")

        print("3/3 CIZ daily returns (crsp.dsf_v2), by year -- this is the big one...")
        frames = []
        for yr in range(START_YEAR, END_YEAR + 1):
            df = w.raw_sql(DAILY_SQL, params={
                "permnos": permnos, "a": f"{yr}-01-01", "b": f"{yr}-12-31"})
            if not df.empty:
                frames.append(df)
            print(f"    {yr}: {len(df)} rows", flush=True)
        daily = pd.concat(frames, ignore_index=True)
        daily.to_csv(OUT / "crsp_daily.csv", index=False)
        print(f"    {len(daily)} daily rows -> local_data/crsp_daily.csv")
    finally:
        w.close()


if __name__ == "__main__":
    main()
