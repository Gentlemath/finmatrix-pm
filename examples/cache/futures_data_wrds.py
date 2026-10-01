"""Cache the cross-asset FUTURES basket from WRDS Datastream (tr_ds_fut).

Run in YOUR terminal (needs your WRDS account). Licensed data — local_data/ is
gitignored; do not commit the output.

All the Datastream-specific knowledge (the stacked-long table layout, the
absence of back-adjustment, the CS0x roll encoding, the basket itself) lives in
``portfolio_management.dataloader.ds_futures`` so that it has exactly one home.
Read that module's docstring before changing anything here.

Writes daily AND monthly returns: daily feeds the mixed-frequency volatility
estimate in TimeSeriesMomentum, monthly is the rebalance clock.
"""

from pathlib import Path

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_futures import (
    BASKET, build_panels, effective_breadth)

OUT = Path("local_data")


def main() -> None:
    # autoconnect=False skips the wrds package's very slow load_library_list()
    # metadata query; raw_sql does not need it.
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        daily, monthly, meta = build_panels(loader, BASKET)
    finally:
        loader.close()

    OUT.mkdir(exist_ok=True)
    daily.to_csv(OUT / "futures_returns_daily_wrds.csv")
    monthly.to_csv(OUT / "futures_returns_monthly_wrds.csv")
    meta.to_csv(OUT / "futures_basket_meta.csv", index=False)

    print(f"\ndaily   {daily.shape[0]:>6} days   x {daily.shape[1]} markets"
          f" -> {OUT / 'futures_returns_daily_wrds.csv'}")
    print(f"monthly {monthly.shape[0]:>6} months x {monthly.shape[1]} markets"
          f" -> {OUT / 'futures_returns_monthly_wrds.csv'}")
    print(f"span: {monthly.index.min():%Y-%m} .. {monthly.index.max():%Y-%m}")

    cleaned = int(meta["bad_zero"].sum() + meta["bad_spike"].sum())
    if cleaned:
        print(f"cleaned {cleaned} bad price(s) across "
              f"{int((meta[['bad_zero', 'bad_spike']].sum(axis=1) > 0).sum())} markets")

    n, corr, breadth = effective_breadth(monthly.loc[:, monthly.notna().sum() >= 60])
    print(f"\nbreadth: {n} markets, mean |pairwise corr| {corr:.2f}, "
          f"effective breadth {breadth:.1f}   (10-ETF basket: 3.4)")


if __name__ == "__main__":
    main()
