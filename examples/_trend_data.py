"""Shared loading for the trend demos: pick whichever basket is cached.

Not a demo itself. The three trend demos all need the same thing — a monthly
returns panel, a daily (or weekly) panel for volatility, and each market's
asset class — so it lives here once.
"""

from pathlib import Path

import pandas as pd


def _data_dir() -> Path:
    """local_data/, resolved from the repo root rather than the caller's cwd.

    The demos should run the same from the repo root and from examples/.
    """
    for base in (Path.cwd(), *Path(__file__).resolve().parents):
        candidate = base / "local_data"
        if candidate.is_dir():
            return candidate
    return Path("local_data")


D = _data_dir()


def load_basket():
    """Return ``(monthly, high_freq, hf_periods_per_year, asset_class, name)``.

    Prefers the 35-market futures basket (1979-2026, the primary sample); falls
    back to the 10-ETF basket (2006-2026) if the futures pull has not been run.
    """
    fut_m, fut_d = D / "futures_returns_monthly_wrds.csv", D / "futures_returns_daily_wrds.csv"
    if fut_m.exists() and fut_d.exists():
        m = pd.read_csv(fut_m, index_col=0, parse_dates=True)
        d = pd.read_csv(fut_d, index_col=0, parse_dates=True)
        meta = pd.read_csv(D / "futures_basket_meta.csv")
        cls = dict(zip(meta["label"], meta["asset_class"]))
        return m, d[m.columns], 252, cls, "futures (35 markets)"

    etf_m = D / "etf_returns_monthly.csv"
    if etf_m.exists():
        m = pd.read_csv(etf_m, index_col=0, parse_dates=True)
        wk = D / "etf_returns_weekly.csv"
        hf = pd.read_csv(wk, index_col=0, parse_dates=True)[m.columns] if wk.exists() else None
        cls = {"SPY": "equity", "EFA": "equity", "EEM": "equity", "VNQ": "equity",
               "IEF": "bond", "TLT": "bond", "LQD": "bond", "UUP": "fx",
               "GLD": "metal", "DBC": "energy"}
        return m, hf, 52, cls, "ETF (10 markets)"

    raise SystemExit(
        "No cached basket found. Run one of:\n"
        "  python examples/cache_futures_data_wrds.py   (35 futures, needs WRDS)\n"
        "  python examples/cache_etf_data_av.py         (10 ETFs, needs an API key)")


def load_equity_benchmark():
    """Monthly SPY total returns, or None if not cached.

    The futures basket has no US equity index (the E-mini continuous series is
    absent from the CS0x family), so the equity benchmark has to come from the
    ETF pull regardless of which basket is being traded.
    """
    p = D / "etf_returns_monthly.csv"
    if not p.exists():
        return None
    etf = pd.read_csv(p, index_col=0, parse_dates=True)
    return etf["SPY"] if "SPY" in etf.columns else None
