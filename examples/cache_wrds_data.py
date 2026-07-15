"""Cache the CRSP data we need into local_data/ (run once, on your machine).

Run in YOUR terminal (needs your WRDS account + network):

    python examples/cache_wrds_data.py

It writes two CSVs to local_data/ so the analysis can run offline afterwards:

    sp500_constituents.csv   point-in-time S&P 500 membership (crsp.msp500list_v2)
    crsp_monthly.csv         CIZ monthly returns (delisting already in mthret) + mthcap

CIZ integrates the delisting return into ``mthret``, so there is no separate
delisting file to fetch.

IMPORTANT: CRSP data is LICENSED. local_data/ is gitignored -- do NOT commit or
share these files.
"""

from pathlib import Path

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
START = "1990-01-01"   # long history so we can see momentum before and after 2009
END = "2025-12-31"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    wrds = create_data_loader("wrds")
    try:
        print("1/2 S&P 500 membership (crsp.msp500list_v2)...")
        constituents = wrds.get_sp500_constituents()
        constituents.to_csv(OUT / "sp500_constituents.csv", index=False)
        permnos = constituents["permno"].astype(int).unique().tolist()
        print(f"    {len(constituents)} spells, {len(permnos)} permnos")

        print("2/2 CIZ monthly returns (crsp.msf_v2, delisting-adjusted)...")
        monthly = wrds.get_crsp_monthly(permnos=permnos, start=START, end=END)
        monthly.to_csv(OUT / "crsp_monthly.csv", index=False)
        print(f"    {len(monthly)} monthly rows")

        print(f"\nSaved to {OUT.resolve()}")
    finally:
        wrds.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()
