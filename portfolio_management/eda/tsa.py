# This is for time series analysis of returns.
# Mainly for stationarity tests, autocorrelation, and seasonality analysis.

import warnings

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import matplotlib.pyplot as plt


class TimeSeriesAnalyzer:
    """Analyze time series properties of return data."""

    @staticmethod
    def test_stationarity(series: pd.Series) -> dict:
        """Perform ADF and KPSS tests for stationarity."""
        adf_result = adfuller(
            series.dropna())  # Augmented Dickey-Fuuller test for unit root (H0: non-stationary)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', InterpolationWarning)
            # Test for stationarity around a constant( H0: stationary)
            kpss_result = kpss(series.dropna(), regression='c')

        kpss_note = None
        for warning_item in caught:
            if issubclass(warning_item.category, InterpolationWarning):
                kpss_note = (
                    "KPSS warning: statistic outside p-value table range; "
                    "actual p-value is greater than returned value."
                )
                break

        result = {
            'adf_statistic': adf_result[0],
            'adf_pvalue': adf_result[1],
            'kpss_statistic': kpss_result[0],
            'kpss_pvalue': kpss_result[1],
        }
        if kpss_note:
            result['kpss_note'] = kpss_note

        return result

    @staticmethod
    def test_autocorrelation(series: pd.Series, lags: int = 40, alpha: float = 0.05) -> dict:
        """
        Test for significant autocorrelation at each lag.

        Args:
            series: Time series data.
            lags: Number of lags to test.
            alpha: Significance level.

        Returns:
            Dictionary with significant lags for ACF and PACF.
        """
        from scipy import stats

        data = series.dropna()
        n = len(data)

        # Compute ACF and PACF
        acf_vals = acf(data, nlags=lags, fft=True)
        pacf_vals = pacf(data, nlags=lags)

        # Standard error approximation for significance
        # standard error for autocorrelation coefficients under null hypothesis of
        # no autocorrelation
        se = 1 / np.sqrt(n)

        # Critical value for two-tailed test
        critical_value = stats.norm.ppf(1 - alpha / 2) * se

        # Find significant lags (excluding lag 0)
        acf_significant = [
            lag for lag in range(
                1, len(acf_vals)) if abs(
                acf_vals[lag]) > critical_value]
        pacf_significant = [
            lag for lag in range(
                1, len(pacf_vals)) if abs(
                pacf_vals[lag]) > critical_value]

        return {
            'acf_significant_lags': acf_significant,
            'pacf_significant_lags': pacf_significant,
            'critical_value': critical_value,
            'alpha': alpha
        }

    @staticmethod
    def plot_acf_pacf(series: pd.Series, lags: int = 40) -> None:
        """Plot ACF and PACF for the series."""
        fig, axes = plt.subplots(1, 2, figsize=(15, 5))
        plot_acf(series.dropna(), lags=lags, ax=axes[0])
        plot_pacf(series.dropna(), lags=lags, ax=axes[1])
        axes[0].set_title('Autocorrelation Function (ACF)')
        axes[1].set_title('Partial Autocorrelation Function (PACF)')
        plt.tight_layout()
        plt.show()
