"""Tests for TimeSeriesAnalyzer stationarity and autocorrelation diagnostics."""

import numpy as np
import pandas as pd

from portfolio_management.eda import TimeSeriesAnalyzer


class TestStationarity:
    def test_result_keys(self, returns_series):
        result = TimeSeriesAnalyzer.test_stationarity(returns_series)
        for key in ("adf_statistic", "adf_pvalue", "kpss_statistic", "kpss_pvalue"):
            assert key in result

    def test_white_noise_is_stationary(self, returns_series):
        # ADF H0 = unit root; a low p-value rejects it -> stationary.
        result = TimeSeriesAnalyzer.test_stationarity(returns_series)
        assert result["adf_pvalue"] < 0.05

    def test_random_walk_is_non_stationary(self, rng, dates):
        walk = pd.Series(np.cumsum(rng.normal(size=len(dates))), index=dates)
        result = TimeSeriesAnalyzer.test_stationarity(walk)
        # A random walk should not reject the unit-root null.
        assert result["adf_pvalue"] > 0.05


class TestAutocorrelation:
    def test_result_keys(self, returns_series):
        result = TimeSeriesAnalyzer.test_autocorrelation(returns_series, lags=20)
        for key in ("acf_significant_lags", "pacf_significant_lags", "critical_value", "alpha"):
            assert key in result

    def test_detects_ar1_dependence(self, rng, dates):
        # Build a strong AR(1): x_t = 0.7 x_{t-1} + eps.
        n = len(dates)
        eps = rng.normal(size=n)
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = 0.7 * x[t - 1] + eps[t]
        series = pd.Series(x, index=dates)
        result = TimeSeriesAnalyzer.test_autocorrelation(series, lags=20)
        # Lag 1 must be flagged significant for both ACF and PACF.
        assert 1 in result["acf_significant_lags"]
        assert 1 in result["pacf_significant_lags"]

    def test_stricter_alpha_gives_larger_critical_value(self, returns_series):
        loose = TimeSeriesAnalyzer.test_autocorrelation(returns_series, lags=20, alpha=0.05)
        strict = TimeSeriesAnalyzer.test_autocorrelation(returns_series, lags=20, alpha=0.01)
        assert strict["critical_value"] > loose["critical_value"]
