"""Cache the cross-asset ETF basket from Alpha Vantage (Territory 2 trend study).

Why not yfinance? Yahoo Finance is geo-blocked in mainland China (HTTP 403) and
rate-limits the university VPN's shared exit address (429), so
``cache_etf_data.py`` cannot run from this connection. Alpha Vantage is
reachable and its TIME_SERIES_MONTHLY_ADJUSTED endpoint is free.

Adjusted close includes dividends, which matters here: three of the ten holdings
are bond ETFs (IEF, TLT, LQD) whose coupons are most of their total return, and
the trend signal keys off the SIGN of trailing returns.

Frequency: pass "monthly" (default) or "weekly" as the first argument. Daily is
NOT available -- Alpha Vantage gates TIME_SERIES_DAILY_ADJUSTED behind a premium
plan, and free TIME_SERIES_DAILY returns only ~100 unadjusted rows. Weekly is
free, adjusted, and carries the full history (1,399 weeks vs 321 months).

Free tier: 25 requests/day. This makes exactly one request per ticker (10), and
prints per-ticker coverage so no separate verification pass is needed.

Writes period-end simple returns to local_data/etf_returns.csv (monthly) or
local_data/etf_returns_weekly.csv (weekly). Both are gitignored.
"""

import sys
import time
from pathlib import Path

import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
START = "2006-01-01"
PAUSE = 15          # seconds between calls; free tier throttles bursts
TICKERS = ["SPY", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP"]

FREQ = {
    "monthly": {"interval": "Monthly_Adjusted", "file": "etf_returns_monthly.csv",
                "periods_per_year": 12},
    "weekly": {"interval": "Weekly_Adjusted", "file": "etf_returns_weekly.csv",
               "periods_per_year": 52},
}


def adjusted_close(frame: pd.DataFrame) -> pd.Series:
    """Pull the dividend-adjusted close out of an Alpha Vantage frame."""
    matches = [c for c in frame.columns if "adjusted close" in c.lower()]
    if not matches:
        raise KeyError(f"no adjusted-close column in {list(frame.columns)}")
    series = frame[matches[0]].astype(float)
    series.index = pd.to_datetime(series.index)
    return series.sort_index()


def fetch(loader, ticker: str, interval: str, tries: int = 3) -> pd.Series:
    """Fetch one ticker, retrying through Alpha Vantage's throttle messages."""
    for attempt in range(1, tries + 1):
        try:
            return adjusted_close(loader.get_price(ticker, interval=interval))
        except Exception as exc:                       # noqa: BLE001
            throttled = "sparingly" in str(exc) or "frequency" in str(exc).lower()
            if not throttled or attempt == tries:
                raise
            wait = 60 * attempt
            print(f"  {ticker:5} throttled, retrying in {wait}s "
                  f"({attempt}/{tries - 1})", flush=True)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def main() -> None:
    freq = (sys.argv[1] if len(sys.argv) > 1 else "monthly").lower()
    if freq not in FREQ:
        raise SystemExit(f"frequency must be one of {list(FREQ)} (daily is premium-only)")
    cfg = FREQ[freq]
    print(f"{freq} ({cfg['interval']}), {len(TICKERS)} tickers, "
          f"~{PAUSE * (len(TICKERS) - 1) // 60} min\n")

    # Resume: keep whatever a previous run already saved and fetch only the rest,
    # so a throttled ticker does not cost a full re-pull of the daily quota.
    existing = pd.DataFrame()
    path = OUT / cfg["file"]
    if path.exists():
        existing = pd.read_csv(path, index_col=0, parse_dates=True)
        have = [t for t in TICKERS if t in existing.columns]
        if have:
            print(f"resuming: {len(have)} already cached ({', '.join(have)})\n")

    todo = [t for t in TICKERS if t not in existing.columns]
    if not todo:
        print("nothing to fetch; all tickers already cached.")
        return

    loader = create_data_loader("alpha_vantage")
    series, failed = {}, {}

    for i, ticker in enumerate(todo):
        try:
            series[ticker] = fetch(loader, ticker, cfg["interval"])
            print(f"  {ticker:5} ok", flush=True)
        except Exception as exc:                       # noqa: BLE001 - report, continue
            failed[ticker] = f"{type(exc).__name__}: {str(exc)[:150]}"
            print(f"  {ticker:5} FAILED  {failed[ticker]}", flush=True)
        if i < len(todo) - 1:
            time.sleep(PAUSE)

    if not series and existing.empty:
        raise SystemExit("\nNo tickers fetched. Is ALPHAVANTAGE_API_KEY set in .env?")

    prices = pd.DataFrame(series).sort_index().loc[START:] if series else pd.DataFrame()

    # Alpha Vantage's last row is the CURRENT, incomplete period - drop it so
    # every return covers a full month/week.
    today = pd.Timestamp.today()
    if len(prices):
        last = prices.index[-1]
        incomplete = ((last.year, last.month) == (today.year, today.month) if freq == "monthly"
                      else (today - last).days < 7)
        if incomplete:
            prices = prices.iloc[:-1]

    returns = prices.pct_change().dropna(how="all") if len(prices) else pd.DataFrame()
    if not existing.empty:
        returns = existing.join(returns, how="outer") if len(returns) else existing
    returns = returns[[t for t in TICKERS if t in returns.columns]].dropna(how="all")

    OUT.mkdir(exist_ok=True)
    returns.to_csv(OUT / cfg["file"])
    print(f"\nsaved {returns.shape[0]} {freq} periods x {returns.shape[1]} assets "
          f"-> {OUT / cfg['file']}")
    print(f"span: {returns.index.min():%Y-%m-%d} .. {returns.index.max():%Y-%m-%d}\n")

    print(f"{freq} observations per asset:")
    print(returns.notna().sum().sort_values().to_string())

    common = returns.dropna(how="any")
    if len(common):
        print(f"\nall-{returns.shape[1]}-assets common history starts "
              f"{common.index.min():%Y-%m-%d} ({len(common)} {freq} periods)")
    print(f"\nbacktest with: periods_per_year={cfg['periods_per_year']}")
    if failed:
        print("\nFAILED tickers (basket is incomplete):")
        for t, msg in failed.items():
            print(f"  {t}: {msg}")


if __name__ == "__main__":
    main()
