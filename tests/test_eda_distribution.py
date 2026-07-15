"""Tests for DistributionAnalyzer statistics and tail-risk measures."""

import pandas as pd
import pytest

from portfolio_management.eda import DistributionAnalyzer


class TestDescribeReturns:
    def test_shape_and_columns(self, returns_frame):
        stats = DistributionAnalyzer.describe_returns(returns_frame)
        assert list(stats.index) == list(returns_frame.columns)
        assert set(stats.columns) == {"mean", "std", "min", "max", "skew", "kurtosis"}

    def test_values_match_pandas(self, returns_frame):
        stats = DistributionAnalyzer.describe_returns(returns_frame)
        assert stats["mean"]["AAA"] == pytest.approx(returns_frame["AAA"].mean())
        assert stats["std"]["BBB"] == pytest.approx(returns_frame["BBB"].std())


class TestValueAtRisk:
    def test_var_is_quantile(self, returns_frame):
        var = DistributionAnalyzer.value_at_risk(returns_frame, confidence=0.95)
        expected = returns_frame.quantile(0.05)
        # check_names=False: the VaR Series is named by the float 1-confidence,
        # which differs from 0.05 only by floating-point representation.
        pd.testing.assert_series_equal(var, expected, check_names=False)

    def test_higher_confidence_gives_more_extreme_var(self, returns_frame):
        var95 = DistributionAnalyzer.value_at_risk(returns_frame, confidence=0.95)
        var99 = DistributionAnalyzer.value_at_risk(returns_frame, confidence=0.99)
        # A higher confidence level pushes VaR further into the left tail.
        assert (var99 <= var95).all()


class TestConditionalVar:
    def test_cvar_not_greater_than_var(self, returns_frame):
        var = DistributionAnalyzer.value_at_risk(returns_frame, confidence=0.95)
        cvar = DistributionAnalyzer.conditional_var(returns_frame, confidence=0.95)
        # Expected shortfall is the mean of the tail beyond VaR, so <= VaR.
        assert (cvar <= var + 1e-9).all()


class TestPlotSmoke:
    def test_plot_distribution_runs(self, returns_frame):
        DistributionAnalyzer.plot_distribution(returns_frame)

    def test_plot_distribution_overview_runs(self, returns_frame):
        DistributionAnalyzer.plot_distribution_overview(returns_frame)

    def test_plot_single_asset_runs(self, returns_frame):
        DistributionAnalyzer.plot_distribution_overview(returns_frame[["AAA"]])
