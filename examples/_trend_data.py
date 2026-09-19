"""Shared loading for the trend demos: which dataset, and how much of it.

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


#: (monthly, daily, meta, label) per dataset version. v1 is the original
#: 35-market basket read from Datastream's own continuous series; v2 is the
#: 51-market rebuild, half of it constructed from contract-level data. Both stay
#: on disk: the ONLY way to attribute a result difference to the data rather
#: than to a code change is to run the same code over both.
DATASETS = {
    1: ("futures_returns_monthly_wrds.csv", "futures_returns_daily_wrds.csv",
        "futures_basket_meta.csv", "futures v1"),
    2: ("futures_returns_monthly_v2.csv", "futures_returns_daily_v2.csv",
        "futures_basket_meta_v2.csv", "futures v2"),
}

#: v2 loses 21 of its 51 markets when the CME feed stops on 2026-04-03, so the
#: last five months are a different, much less US-weighted basket. Analyses that
#: compare markets should end here rather than average across the change.
V2_COMPLETE_THROUGH = "2026-03"


def load_basket(version=None, through=None, start=None):
    """Return ``(monthly, high_freq, hf_periods_per_year, asset_class, name)``.

    Args:
        version: 1, 2, or None to take whichever is cached, newest first. Pass
            it explicitly in anything whose result is being recorded -- ``name``
            carries the version so a table can never become anonymous.
        through: last period to keep, ``"YYYY-MM"``. Defaults to
            :data:`V2_COMPLETE_THROUGH` for v2 because of the 2026-04 cliff;
            pass ``"all"`` to keep every month.
        start: first period to keep, ``"YYYY-MM"``. Mainly for putting the two
            datasets on one window -- v2 begins in 1973 and v1 in 1979, so a
            comparison across them has to be cut somewhere. Markets left with no
            data after the cut are dropped, and ``name`` records the window so a
            printed table cannot be mistaken for the full sample.
    """
    order = [version] if version is not None else [2, 1]
    for v in order:
        mf, df, metaf, name = DATASETS[v]
        if not ((D / mf).exists() and (D / df).exists()):
            continue
        m = pd.read_csv(D / mf, index_col=0, parse_dates=True)
        d = pd.read_csv(D / df, index_col=0, parse_dates=True)
        meta = pd.read_csv(D / metaf)
        cls = dict(zip(meta["label"], meta["asset_class"]))
        # The count goes in the label from the DATA, never hard-coded: the v2
        # basket has already changed size once (palladium removed on liquidity)
        # and a stale label on a printed table is how a result gets misfiled.
        name = (f"{name} ({m.shape[1]} markets, "
                f"{m.index.min():%Y}-{m.index.max():%Y})")
        cut = through if through is not None else (
            V2_COMPLETE_THROUGH if v == 2 else "all")
        if cut != "all":
            m = m[m.index <= pd.Period(cut, "M").end_time]
            d = d[d.index <= pd.Period(cut, "M").end_time]
            name = f"{name} through {cut}"
        if start:
            t0 = pd.Period(start, "M").start_time
            m, d = m[m.index >= t0], d[d.index >= t0]
            m = m.loc[:, m.notna().any()]
            name = f"{name} from {start} ({m.shape[1]} markets)"
        return m, d[m.columns], 252, cls, name
    if version is not None:
        raise SystemExit(
            f"dataset v{version} not cached. Run:\n"
            f"  python examples/cache_futures_data{'_v2' if version == 2 else ''}"
            f"_wrds.py")

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
        "  python examples/cache_futures_data_v2_wrds.py  (51 futures, needs WRDS)\n"
        "  python examples/cache_futures_data_wrds.py     (35 futures, needs WRDS)\n"
        "  python examples/cache_etf_data_av.py           (10 ETFs, needs an API key)")


def add_dataset_arg(parser):
    """Give a demo ``--dataset {1,2}`` and ``--through``.

    The demos are deliberately NOT forked per dataset. Forking them would make
    every v1-vs-v2 difference ambiguous between a data change and a code change,
    which is the one comparison keeping v1 on disk is for.
    """
    parser.add_argument("--dataset", type=int, choices=(1, 2), default=None,
                        help="futures basket version (default: newest cached)")
    parser.add_argument("--through", default=None,
                        help="last month to keep, YYYY-MM, or 'all'")
    parser.add_argument("--start", "--from", dest="start", default=None,
                        help="first month to keep, YYYY-MM (v2 starts 1973, "
                             "v1 1979, so cross-dataset runs need this)")
    return parser


#: Rough average cash rate over 2006-2026, the ETF benchmark's span. Only the
#: ETF needs one; every other source here is already an excess return.
ETF_RF_ANNUAL = 0.018


def load_equity_benchmark(monthly=None):
    """Return ``(series, rf_annual)`` for a US equity benchmark, or ``(None, 0)``.

    The second element is what must be SUBTRACTED before computing a Sharpe.
    It is not a property of the market -- it is a property of the SERIES, and
    the three sources here differ:

    ==========================  ====================  ==========  ====
    source                      what it measures      span        rf
    ==========================  ====================  ==========  ====
    CRSP/Fama-French ``mktrf``  US market, EXCESS     1926-2026   0
    v2 panel ``SP500``          futures, EXCESS       1982-2026   0
    ``etf_returns_monthly``     SPY ETF, TOTAL        2006-2026   1.8%
    ==========================  ====================  ==========  ====

    Only the ETF includes the cash return, so only the ETF has it removed.
    Subtracting a constant from the other two would charge them for interest
    they never earned -- which is exactly what trend_portfolio_demo.py did to
    the futures series, costing its Sharpe 0.11 (0.56 reported as 0.45) with no
    visible symptom. Returning rf alongside the series is what makes that
    mistake unavailable rather than merely discouraged.

    Preference order is span, and mktrf wins by decades: it covers the futures
    panel from its 1973 start, where the futures S&P begins only in 1982 and the
    ETF in 2006. It is also independent of the futures dataset, which matters
    for a regression whose whole point is to compare the two.

    Run examples/cache_equity_benchmark_wrds.py to create the mktrf file.
    """
    p = D / "equity_benchmark_monthly.csv"
    if p.exists():
        b = pd.read_csv(p, index_col=0, parse_dates=True)
        if "mktrf" in b.columns:
            s = b["mktrf"].dropna()
            # "mktrf" is Fama-French's name for the value-weighted return on all
            # listed US stocks minus the one-month Treasury bill. Relabelled
            # because the demos print this name and it has to read as English.
            s.name = "US equity"
            return s, 0.0
    if monthly is not None and "SP500" in monthly.columns:
        return monthly["SP500"], 0.0
    p = D / "etf_returns_monthly.csv"
    if not p.exists():
        return None, 0.0
    etf = pd.read_csv(p, index_col=0, parse_dates=True)
    if "SPY" not in etf.columns:
        return None, 0.0
    return etf["SPY"], ETF_RF_ANNUAL
