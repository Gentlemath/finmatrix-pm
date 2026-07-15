"""Tests for PlotAnalyzer return computations and plot smoke tests."""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.eda import PlotAnalyzer


class TestComputeReturns:
    def test_simple_returns_match_pct_change(self, prices_frame):
        result = PlotAnalyzer.compute_returns(prices_frame, method="simple")
        pd.testing.assert_frame_equal(result, prices_frame.pct_change())

    def test_log_returns_match_log_price_ratio(self, prices_frame):
        result = PlotAnalyzer.compute_returns(prices_frame, method="log")
        expected = np.log(prices_frame / prices_frame.shift(1))
        pd.testing.assert_frame_equal(result, expected)

    def test_log_returns_first_row_is_nan(self, prices_frame):
        result = PlotAnalyzer.compute_returns(prices_frame, method="log")
        assert result.iloc[0].isna().all()

    def test_unknown_method_raises(self, prices_frame):
        with pytest.raises(ValueError, match="Unknown method"):
            PlotAnalyzer.compute_returns(prices_frame, method="bogus")


class TestCumulativeReturns:
    def test_growth_of_one(self):
        returns = pd.DataFrame({"x": [0.10, 0.10]})
        cum = PlotAnalyzer.cumulative_returns(returns)
        # (1.1 * 1.1) - 1 = 0.21
        assert cum["x"].iloc[-1] == pytest.approx(0.21)

    def test_zero_returns_give_zero_growth(self):
        returns = pd.DataFrame({"x": [0.0, 0.0, 0.0]})
        cum = PlotAnalyzer.cumulative_returns(returns)
        assert (cum["x"] == 0.0).all()


class TestPlotSmoke:
    """Plots use the Agg backend (see conftest); assert they run without error."""

    def test_plot_prices_runs(self, prices_frame):
        PlotAnalyzer.plot_prices(prices_frame)

    def test_plot_returns_runs(self, returns_frame):
        PlotAnalyzer.plot_returns(returns_frame)

    def test_plot_overview_runs(self, prices_frame, returns_frame):
        PlotAnalyzer.plot_overview(prices_frame, returns_frame)
