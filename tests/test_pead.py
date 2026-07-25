"""Tests for the PEAD event-study building blocks (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.strategy import (
    analyst_sue,
    event_car,
    standardized_unexpected_earnings,
)


def _earnings(gvkey, q1_eps, other=5.0, years=(2010, 2011, 2012, 2013, 2014)):
    """Quarterly earnings; q1 EPS follows q1_eps by year, other quarters flat."""
    rows = []
    for i, yr in enumerate(years):
        for q in (1, 2, 3, 4):
            rows.append({
                "gvkey": gvkey,
                "datadate": pd.Timestamp(f"{yr}-{3*q:02d}-28"),
                "fqtr": q,
                "epsfxq": q1_eps[i] if q == 1 else other,
            })
    return pd.DataFrame(rows)


class TestSUE:
    def test_sign_follows_earnings_growth(self):
        rising = _earnings(1, [1, 2, 3, 4, 5])     # q1 EPS grows each year
        falling = _earnings(2, [5, 4, 3, 2, 1])
        out_r = standardized_unexpected_earnings(rising, window=6, min_periods=2)
        out_f = standardized_unexpected_earnings(falling, window=6, min_periods=2)
        # look at the last q1 (year-over-year change is clearly +/-)
        last_r = out_r[out_r["fqtr"] == 1].dropna(subset=["sue"]).iloc[-1]
        last_f = out_f[out_f["fqtr"] == 1].dropna(subset=["sue"]).iloc[-1]
        assert last_r["sue"] > 0
        assert last_f["sue"] < 0

    def test_purely_seasonal_firm_has_no_surprise(self):
        # identical earnings every year (strong within-year seasonality, no growth)
        # -> year-over-year change is 0 -> SUE is 0 or NaN, never large.
        seasonal = pd.DataFrame([
            {"gvkey": 9, "datadate": pd.Timestamp(f"{yr}-{3*q:02d}-28"),
             "fqtr": q, "epsfxq": float(q)}          # q1=1,q2=2,q3=3,q4=4 every year
            for yr in range(2010, 2016) for q in (1, 2, 3, 4)
        ])
        out = standardized_unexpected_earnings(seasonal, window=6, min_periods=2)
        finite = out["sue"].dropna()
        assert (finite.abs() < 1e-9).all()          # seasonal differencing removes it

    def test_first_year_is_nan(self):
        out = standardized_unexpected_earnings(_earnings(1, [1, 2, 3, 4, 5]),
                                               window=6, min_periods=2)
        assert out[out["datadate"].dt.year == 2010]["sue"].isna().all()


class TestAnalystSUE:
    def _cons(self, ticker, period, snaps):
        """snaps: list of (statpers, medest, stdev)."""
        return pd.DataFrame([
            {"ticker": ticker, "fpedats": pd.Timestamp(period),
             "statpers": pd.Timestamp(sp), "medest": est, "stdev": sd}
            for sp, est, sd in snaps
        ])

    def test_surprise_sign(self):
        actuals = pd.DataFrame([
            {"ticker": "AAA", "pends": "2020-03-31", "anndats": "2020-04-20", "value": 1.20},
            {"ticker": "BBB", "pends": "2020-03-31", "anndats": "2020-04-20", "value": 0.80},
        ])
        cons = pd.concat([
            self._cons("AAA", "2020-03-31", [("2020-04-10", 1.00, 0.10)]),  # beat
            self._cons("BBB", "2020-03-31", [("2020-04-10", 1.00, 0.10)]),  # miss
        ], ignore_index=True)
        out = analyst_sue(actuals, cons).set_index("ticker")
        assert out.loc["AAA", "sue"] == pytest.approx((1.20 - 1.00) / 0.10)   # +2
        assert out.loc["BBB", "sue"] == pytest.approx((0.80 - 1.00) / 0.10)   # -2

    def test_uses_latest_pre_announcement_snapshot(self):
        # a stale estimate and a fresh one, both before the announcement:
        # the fresh (latest statpers) one must be the one used.
        actuals = pd.DataFrame([
            {"ticker": "AAA", "pends": "2020-03-31", "anndats": "2020-04-20", "value": 1.00},
        ])
        cons = self._cons("AAA", "2020-03-31", [
            ("2020-02-01", 0.50, 0.10),   # stale
            ("2020-04-15", 0.90, 0.10),   # fresh -> should win
        ])
        out = analyst_sue(actuals, cons)
        assert out["sue"].iloc[0] == pytest.approx((1.00 - 0.90) / 0.10)

    def test_ignores_snapshots_after_announcement(self):
        # a post-announcement snapshot (look-ahead) must be excluded.
        actuals = pd.DataFrame([
            {"ticker": "AAA", "pends": "2020-03-31", "anndats": "2020-04-20", "value": 1.00},
        ])
        cons = self._cons("AAA", "2020-03-31", [
            ("2020-04-10", 0.80, 0.10),   # last valid pre-announcement estimate
            ("2020-04-25", 1.00, 0.10),   # after anndats -> ignored
        ])
        out = analyst_sue(actuals, cons)
        assert out["sue"].iloc[0] == pytest.approx((1.00 - 0.80) / 0.10)

    def test_zero_dispersion_is_nan(self):
        actuals = pd.DataFrame([
            {"ticker": "AAA", "pends": "2020-03-31", "anndats": "2020-04-20", "value": 1.10},
        ])
        cons = self._cons("AAA", "2020-03-31", [("2020-04-10", 1.00, 0.0)])
        out = analyst_sue(actuals, cons)
        assert np.isnan(out["sue"].iloc[0])


class TestEventCar:
    def test_window_sums_no_adjust(self):
        dates = pd.bdate_range("2020-01-01", periods=70)
        daily = pd.DataFrame({"permno": 1, "date": dates, "ret": 0.01})
        events = pd.DataFrame({"permno": [1], "rdq": [dates[0]]})
        out = event_car(daily, events, market_adjust=False)  # ann (0,1), drift (2,63)
        assert out["ann_car"].iloc[0] == pytest.approx(0.02)      # 2 days
        assert out["drift_car"].iloc[0] == pytest.approx(0.62)    # 62 days

    def test_event_day0_is_first_trading_day_on_or_after(self):
        dates = pd.bdate_range("2020-01-02", periods=6)   # skips the weekend
        daily = pd.DataFrame({"permno": 1, "date": dates,
                              "ret": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]})
        # rdq on Saturday 2020-01-04 -> day 0 is Monday 2020-01-06 (index 2)
        events = pd.DataFrame({"permno": [1], "rdq": [pd.Timestamp("2020-01-04")]})
        out = event_car(daily, events, market_adjust=False,
                        ann_window=(0, 1), drift_window=(2, 3))
        assert out["ann_car"].iloc[0] == pytest.approx(0.3 + 0.4)
        assert out["drift_car"].iloc[0] == pytest.approx(0.5 + 0.6)

    def test_market_adjust_removes_cross_sectional_mean(self):
        dates = pd.bdate_range("2020-01-01", periods=6)
        d1 = pd.DataFrame({"permno": 1, "date": dates, "ret": 0.03})
        d2 = pd.DataFrame({"permno": 2, "date": dates, "ret": 0.01})
        daily = pd.concat([d1, d2], ignore_index=True)     # daily mean = 0.02
        events = pd.DataFrame({"permno": [1, 2], "rdq": [dates[0], dates[0]]})
        out = event_car(daily, events, ann_window=(0, 1), drift_window=(2, 3)).set_index("permno")
        assert out.loc[1, "ann_car"] == pytest.approx(0.02)    # (0.03-0.02)*2
        assert out.loc[2, "ann_car"] == pytest.approx(-0.02)

    def test_benchmark_col_is_subtracted(self):
        # characteristic-adjusted: abnormal = ret - supplied benchmark
        dates = pd.bdate_range("2020-01-01", periods=6)
        daily = pd.DataFrame({"permno": 1, "date": dates,
                              "ret": 0.05, "bench": 0.04})   # abn = 0.01/day
        events = pd.DataFrame({"permno": [1], "rdq": [dates[0]]})
        out = event_car(daily, events, benchmark_col="bench",
                        ann_window=(0, 1), drift_window=(2, 3))
        assert out["ann_car"].iloc[0] == pytest.approx(0.02)    # 2 days * 0.01
        assert out["drift_car"].iloc[0] == pytest.approx(0.02)

    def test_insufficient_history_is_nan(self):
        dates = pd.bdate_range("2020-01-01", periods=10)
        daily = pd.DataFrame({"permno": 1, "date": dates, "ret": 0.01})
        events = pd.DataFrame({"permno": [1], "rdq": [dates[8]]})  # not enough days after
        out = event_car(daily, events, market_adjust=False)
        assert np.isnan(out["drift_car"].iloc[0])
