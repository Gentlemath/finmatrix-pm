"""Cache the cross-asset ETF basket from WRDS / CRSP (CIZ).

Run in YOUR terminal (needs your WRDS account). Licensed data — local_data/ is
gitignored; do not commit the output.

Why CRSP rather than yfinance or Alpha Vantage: ``mthret`` is a true total return
with distributions already folded in, so there is no dividend-adjustment
guesswork. That matters here because three holdings are bond ETFs (IEF, TLT, LQD)
whose coupons are most of their return, and the trend signal keys off the SIGN of
trailing returns.

Writes to local_data/etf_returns_monthly_wrds.csv — deliberately NOT the same file
as the Alpha Vantage pull, so the two can be compared. If the Alpha Vantage file
is present this script reports the discrepancy per asset, which is a free
data-quality check on both sources.

Caveat this script checks rather than assumes: CRSP's stock file may not carry
every ETF (DBC and UUP are commodity pools structured as partnerships, not
registered funds), and tickers get REUSED, so "GLD" can resolve to a delisted
1980s company as well as the gold ETF. Candidate permnos are printed and
disambiguated by requiring the security to still be trading recently.
"""

from pathlib import Path

import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
FILE = "etf_returns_monthly_wrds.csv"
COMPARE = "etf_returns_monthly.csv"          # the Alpha Vantage pull, if present
START = "2006-01-01"
STILL_TRADING_AFTER = "2020-01-01"           # disambiguates reused tickers
TICKERS = ["SPY", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]


def resolve_permnos(loader, tickers) -> dict:
    """Map each ticker to one permno, printing every candidate.

    Tickers are reused across securities, so a ticker can match several permnos.
    We keep those still trading after ``STILL_TRADING_AFTER`` and, among them,
    the one with the longest history.
    """
    sql = """
        select permno, ticker,
               min(mthcaldt) as first_dt,
               max(mthcaldt) as last_dt,
               count(*)      as n_months
        from crsp.msf_v2
        where upper(ticker) in %(tickers)s
        group by permno, ticker
        order by ticker, first_dt
    """
    cand = loader.raw_sql(sql, params={"tickers": tuple(t.upper() for t in tickers)})
    if cand.empty:
        raise SystemExit("No permno matched any ticker — does CRSP cover these ETFs?")

    cand["ticker"] = cand["ticker"].str.upper()
    cand["last_dt"] = pd.to_datetime(cand["last_dt"])
    cand["first_dt"] = pd.to_datetime(cand["first_dt"])

    chosen = {}
    print("candidate permnos (* = chosen):")
    for tkr in tickers:
        rows = cand[cand["ticker"] == tkr]
        if rows.empty:
            print(f"  {tkr:5} NOT IN CRSP")
            continue
        live = rows[rows["last_dt"] >= pd.Timestamp(STILL_TRADING_AFTER)]
        pick = (live if not live.empty else rows).sort_values("n_months").iloc[-1]
        chosen[tkr] = int(pick["permno"])
        for _, r in rows.iterrows():
            mark = "*" if int(r["permno"]) == chosen[tkr] else " "
            print(f"  {mark} {tkr:5} permno {int(r['permno']):>7}  "
                  f"{r['first_dt']:%Y-%m} .. {r['last_dt']:%Y-%m}  "
                  f"{int(r['n_months']):>4} months")
    return chosen


def main() -> None:
    # autoconnect=False skips the wrds package's very slow load_library_list()
    # metadata query; raw_sql and the CIZ helpers do not need it.
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        chosen = resolve_permnos(loader, TICKERS)
        missing = [t for t in TICKERS if t not in chosen]
        if missing:
            print(f"\nnot found in CRSP: {missing}")

        print(f"\npulling CIZ monthly for {len(chosen)} permnos from {START} ...")
        raw = loader.get_crsp_monthly(permnos=list(chosen.values()), start=START)
    finally:
        loader.close()

    by_permno = {v: k for k, v in chosen.items()}
    raw["ticker"] = raw["permno"].map(by_permno)
    panel = raw.pivot_table(index="mthcaldt", columns="ticker", values="mthret")
    panel = panel[[t for t in TICKERS if t in panel.columns]].sort_index()
    panel.index.name = "date"

    OUT.mkdir(exist_ok=True)
    panel.to_csv(OUT / FILE)
    print(f"\nsaved {panel.shape[0]} months x {panel.shape[1]} assets -> {OUT / FILE}")
    print(f"span: {panel.index.min():%Y-%m} .. {panel.index.max():%Y-%m}\n")
    print("months of history per asset:")
    print(panel.notna().sum().sort_values().to_string())

    # free data-quality check against the Alpha Vantage pull
    alt_path = OUT / COMPARE
    if alt_path.exists():
        alt = pd.read_csv(alt_path, index_col=0, parse_dates=True)
        both = [c for c in panel.columns if c in alt.columns]
        if both:
            print(f"\nvs {COMPARE} (Alpha Vantage) on overlapping months:")
            print(f"  {'asset':<7}{'n':>6}{'corr':>8}{'mean diff bp':>14}{'max |diff| bp':>15}")
            a = panel[both].copy()
            a.index = a.index.to_period("M")
            b = alt[both].copy()
            b.index = b.index.to_period("M")
            for c in both:
                j = pd.concat([a[c], b[c]], axis=1, join="inner").dropna()
                if len(j) < 12:
                    continue
                d = (j.iloc[:, 0] - j.iloc[:, 1]) * 1e4
                print(f"  {c:<7}{len(j):>6}{j.iloc[:, 0].corr(j.iloc[:, 1]):>8.4f}"
                      f"{d.mean():>14.1f}{d.abs().max():>15.1f}")
            print("  (corr should be ~1.000; large diffs mean one source is "
                  "mis-adjusting dividends)")


if __name__ == "__main__":
    main()
