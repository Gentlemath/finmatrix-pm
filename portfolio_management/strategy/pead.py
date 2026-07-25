"""Post-earnings-announcement-drift (PEAD) event study.

Two data-source-agnostic building blocks, both unit-tested on synthetic data:

- ``standardized_unexpected_earnings`` — SUE via the seasonal-random-walk model:
  the year-over-year change in a fiscal quarter's earnings, scaled by the
  trailing standard deviation of that change.
- ``event_car`` — align daily returns to *event time* (trading days relative to
  an event date) and compute the announcement-window and drift-window
  cumulative abnormal returns. Event day 0 is the first trading day on/after the
  event; abnormal return is (optionally) the daily cross-sectional mean removed.

The offline data assembly (CCM gvkey->permno mapping, era/size grouping) lives
in ``examples/pead_event_study.py``; this module is pure and testable.
"""

from typing import Tuple

import numpy as np
import pandas as pd


def standardized_unexpected_earnings(
    earnings: pd.DataFrame,
    eps_col: str = "epsfxq",
    id_col: str = "gvkey",
    season_col: str = "fqtr",
    order_col: str = "datadate",
    window: int = 8,
    min_periods: int = 6,
) -> pd.DataFrame:
    """Add a ``sue`` column (seasonal-random-walk standardized unexpected earnings).

    ``sue = (eps_q - eps_{q-4}) / rolling_std(eps_q - eps_{q-4})`` — the seasonal
    (same fiscal quarter, prior year) earnings change divided by the trailing
    standard deviation of that change. Rows with insufficient history are NaN.
    """
    df = earnings.sort_values([id_col, order_col]).copy()
    # year-over-year change within the same fiscal quarter (seasonal difference)
    d_eps = df.groupby([id_col, season_col])[eps_col].diff()
    df["_d_eps"] = d_eps
    df = df.sort_values([id_col, order_col])
    df["_std"] = df.groupby(id_col)["_d_eps"].transform(
        lambda s: s.rolling(window, min_periods=min_periods).std()
    )
    sue = df["_d_eps"] / df["_std"].replace(0.0, np.nan)
    df["sue"] = sue.replace([np.inf, -np.inf], np.nan)
    return df.drop(columns=["_d_eps", "_std"])


def analyst_sue(
    actuals: pd.DataFrame,
    consensus: pd.DataFrame,
    id_col: str = "ticker",
    actual_period_col: str = "pends",
    ann_col: str = "anndats",
    actual_col: str = "value",
    cons_period_col: str = "fpedats",
    stat_col: str = "statpers",
    est_col: str = "medest",
    disp_col: str = "stdev",
) -> pd.DataFrame:
    """Analyst-based SUE = (actual - consensus estimate) / cross-analyst dispersion.

    For each realized quarterly EPS (``id_col``, ``actual_period_col``,
    ``ann_col``, ``actual_col``), take the *last* consensus snapshot
    (``stat_col``) strictly before the announcement that forecasts the same
    fiscal period (``cons_period_col`` == ``actual_period_col``) — i.e. the
    market's freshest expectation with no look-ahead. SUE divides the surprise
    (actual - ``est_col``) by the dispersion of analyst estimates (``disp_col``);
    zero/NaN dispersion (all-agree or single-analyst) yields NaN.

    Returns one row per matched announcement (``id_col``, ``actual_period_col``,
    ``ann_col``, ``actual_col``, ``est_col``, ``disp_col``, ``sue``).
    """
    a = actuals[[id_col, actual_period_col, ann_col, actual_col]].dropna(
        subset=[actual_col, ann_col]).copy()
    a[ann_col] = pd.to_datetime(a[ann_col])
    a[actual_period_col] = pd.to_datetime(a[actual_period_col])

    c = consensus[[id_col, cons_period_col, stat_col, est_col, disp_col]].copy()
    c[stat_col] = pd.to_datetime(c[stat_col])
    c[cons_period_col] = pd.to_datetime(c[cons_period_col])

    m = a.merge(c, left_on=[id_col, actual_period_col],
                right_on=[id_col, cons_period_col], how="inner")
    m = m[m[stat_col] < m[ann_col]]                       # pre-announcement snapshots only
    # latest snapshot per announcement (sort ascending, keep the last)
    m = m.sort_values(stat_col).groupby(
        [id_col, actual_period_col], as_index=False).tail(1)

    surprise = m[actual_col] - m[est_col]
    m["sue"] = surprise / m[disp_col].replace(0.0, np.nan)
    m["sue"] = m["sue"].replace([np.inf, -np.inf], np.nan)
    keep = [id_col, actual_period_col, ann_col, actual_col, est_col, disp_col, "sue"]
    return m[keep].reset_index(drop=True)


def event_car(
    daily: pd.DataFrame,
    events: pd.DataFrame,
    id_col: str = "permno",
    date_col: str = "date",
    ret_col: str = "ret",
    event_id_col: str = "permno",
    event_date_col: str = "rdq",
    ann_window: Tuple[int, int] = (0, 1),
    drift_window: Tuple[int, int] = (2, 63),
    benchmark_col: str = None,
    market_adjust: bool = True,
) -> pd.DataFrame:
    """Announcement- and drift-window cumulative abnormal returns, in event time.

    Args:
        daily: long daily returns (``id_col``, ``date_col``, ``ret_col``).
        events: one row per event (``event_id_col``, ``event_date_col``).
        ann_window / drift_window: inclusive event-day ranges. Event day 0 is the
            first trading day on/after the event date.
        benchmark_col: if given, abnormal return = ``ret_col - benchmark_col``
            (supply a per-row characteristic-matched benchmark, e.g. a size or
            size x book-to-market portfolio return). Takes precedence over
            ``market_adjust``.
        market_adjust: if no ``benchmark_col``, subtract the equal-weighted
            cross-sectional mean return each day (a simple market adjustment).

    Returns:
        A copy of ``events`` with ``ann_car`` and ``drift_car`` columns (NaN when
        there are too few trading days after the event).
    """
    d = daily.dropna(subset=[ret_col]).copy()
    d[date_col] = pd.to_datetime(d[date_col])
    if benchmark_col is not None:
        d["_abn"] = d[ret_col] - d[benchmark_col]
    elif market_adjust:
        d["_abn"] = d[ret_col] - d.groupby(date_col)[ret_col].transform("mean")
    else:
        d["_abn"] = d[ret_col]
    d = d.sort_values([id_col, date_col])

    # per-id: sorted event dates + cumulative abnormal return (leading 0)
    dates, cum = {}, {}
    for pid, g in d.groupby(id_col):
        dates[pid] = g[date_col].values
        cum[pid] = np.concatenate([[0.0], np.cumsum(g["_abn"].to_numpy())])

    a0, a1 = ann_window[0], ann_window[1] + 1
    r0, r1 = drift_window[0], drift_window[1] + 1

    def _car(pid, ev):
        arr = dates.get(pid)
        if arr is None:
            return (np.nan, np.nan)
        c = cum[pid]

        # searchsorted(side="left") = number of dates strictly < ev = index of
        # the first trading day on/after the event date (event day 0).
        p0 = int(np.searchsorted(arr, np.datetime64(ev), side="left"))
        if p0 >= len(arr) or p0 + r1 >= len(c):
            return (np.nan, np.nan)
        return (c[p0 + a1] - c[p0 + a0], c[p0 + r1] - c[p0 + r0])

    out = events.copy()
    ev_dates = pd.to_datetime(out[event_date_col])
    cars = [_car(int(p), e) for p, e in zip(out[event_id_col], ev_dates)]
    out["ann_car"] = [c[0] for c in cars]
    out["drift_car"] = [c[1] for c in cars]
    return out
