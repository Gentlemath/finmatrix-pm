"""Tests for the momentum strategy and universe helpers (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.strategy import (
    MomentumStrategy,
    build_membership,
    panels_from_crsp,
)


def constant_returns(values, n_months=12, start="2015-01-31"):
    """Panel where each stock earns a fixed monthly return (deterministic)."""
    idx = pd.date_range(start, periods=n_months, freq="ME")
    return pd.DataFrame({k: [v] * n_months for k, v in values.items()}, index=idx)


# Stock A always best, D always worst -> stable momentum ordering A > B > C > D.
RETS = {"A": 0.10, "B": 0.05, "C": 0.00, "D": -0.05}


class TestValidation:
    def test_bad_params_raise(self):
        with pytest.raises(ValueError):
            MomentumStrategy(lookback=0)
        with pytest.raises(ValueError):
            MomentumStrategy(gap=-1)
        with pytest.raises(ValueError):
            MomentumStrategy(n_quantiles=1)
        with pytest.raises(ValueError):
            MomentumStrategy(weighting="bogus")

    def test_value_weighting_requires_caps(self):
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2, weighting="value")
        with pytest.raises(ValueError, match="market_caps"):
            strat.backtest(constant_returns(RETS))


class TestSignal:
    def test_ranks_stocks_in_return_order(self):
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2)
        signal = strat.compute_signal(constant_returns(RETS))
        last = signal.dropna().iloc[-1]
        assert last["A"] > last["B"] > last["C"] > last["D"]


class TestBacktest:
    def test_long_short_equal_weight(self):
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2, weighting="equal")
        result = strat.backtest(constant_returns(RETS))
        row = result.dropna(subset=["strategy"]).iloc[-1]
        # winners {A,B}=0.075, losers {C,D}=-0.025, long-short = 0.10
        assert row["long"] == pytest.approx(0.075)
        assert row["short"] == pytest.approx(-0.025)
        assert row["strategy"] == pytest.approx(0.10)

    def test_long_only(self):
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2, long_short=False)
        result = strat.backtest(constant_returns(RETS))
        row = result.dropna(subset=["strategy"]).iloc[-1]
        assert row["strategy"] == pytest.approx(0.075)  # top leg only
        assert np.isnan(row["short"])

    def test_value_weighting(self):
        returns = constant_returns(RETS)
        caps = constant_returns({"A": 100.0, "B": 300.0, "C": 100.0, "D": 100.0})
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2, weighting="value")
        result = strat.backtest(returns, market_caps=caps)
        row = result.dropna(subset=["strategy"]).iloc[-1]
        # long leg {A,B}: (100*0.10 + 300*0.05) / 400 = 0.0625
        assert row["long"] == pytest.approx(0.0625)

    def test_membership_excludes_ineligible(self):
        returns = constant_returns(RETS)
        membership = pd.DataFrame(True, index=returns.index, columns=returns.columns)
        membership["A"] = False  # drop the top stock from the universe
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2)
        result = strat.backtest(returns, membership=membership)
        row = result.dropna(subset=["strategy"]).iloc[-1]
        # With A excluded, the sole winner is B -> long leg = 0.05
        assert row["long"] == pytest.approx(0.05)

    def test_return_indexed_by_realized_month(self):
        # A is always the winner (all positive), B always the loser (all
        # negative), and A's return VARIES month to month -- so a one-month
        # misalignment would change the recorded value. The long-only leg at
        # holding date d must equal A's realized return in month d.
        idx = pd.date_range("2015-01-31", periods=8, freq="ME")
        a = [0.03, 0.05, 0.02, 0.06, 0.01, 0.04, 0.07, 0.02]
        returns = pd.DataFrame({"A": a, "B": [-x for x in a]}, index=idx)
        strat = MomentumStrategy(lookback=2, gap=1, n_quantiles=2, long_short=False)
        result = strat.backtest(returns)
        assert len(result) > 0
        for d in result.index:
            assert result.loc[d, "long"] == pytest.approx(returns.loc[d, "A"])

    def test_return_weights(self):
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2)
        result, weights = strat.backtest(constant_returns(RETS), return_weights=True)
        assert isinstance(weights, pd.DataFrame)
        # long-short net weights sum to ~0 each rebalance (dollar-neutral)
        row_sums = weights.fillna(0.0).sum(axis=1)
        assert np.allclose(row_sums.dropna(), 0.0, atol=1e-9)
        # winners carry positive weight, losers negative
        last = weights.dropna(how="all").iloc[-1]
        assert last.get("A", 0) > 0 and last.get("D", 0) < 0

    def test_no_lookahead(self):
        # A spike in the final month must not change any earlier holding return.
        returns = constant_returns(RETS, n_months=12)
        spiked = returns.copy()
        spiked.iloc[-1, spiked.columns.get_loc("A")] = 5.0  # absurd last-month return
        strat = MomentumStrategy(lookback=3, gap=1, n_quantiles=2)
        base = strat.backtest(returns)
        with_spike = strat.backtest(spiked)
        # Rows before the last holding month must be identical.
        common = base.index.intersection(with_spike.index)[:-1]
        pd.testing.assert_frame_equal(base.loc[common], with_spike.loc[common])


class TestUniverse:
    def test_build_membership_windows(self):
        constituents = pd.DataFrame(
            {
                "permno": [10, 20],
                "start": ["2015-01-01", "2015-03-01"],
                "ending": ["2015-04-30", None],  # 20 is still a member (open end)
            }
        )
        dates = pd.date_range("2015-01-31", periods=6, freq="ME")
        membership = build_membership(constituents, dates)
        assert membership.loc["2015-02-28", 10]        # 10 in during Feb
        assert not membership.loc["2015-05-31", 10]     # 10 left after April
        assert not membership.loc["2015-01-31", 20]     # 20 not yet in
        assert membership.loc["2015-06-30", 20]         # open-ended -> still in

    def test_panels_from_crsp(self):
        monthly = pd.DataFrame(
            {
                "permno": [10, 10, 20, 20],
                "date": pd.to_datetime(
                    ["2015-01-31", "2015-02-28", "2015-01-31", "2015-02-28"]
                ),
                "ret": [0.01, 0.02, -0.01, 0.03],
                "prc": [10.0, 10.0, 20.0, 20.0],
                "shrout": [100, 100, 50, 50],
            }
        )
        constituents = pd.DataFrame(
            {"permno": [10, 20], "start": ["2015-01-01", "2015-01-01"], "ending": [None, None]}
        )
        returns, membership, caps = panels_from_crsp(monthly, constituents)
        assert list(returns.columns) == ["10", "20"]
        assert returns.loc["2015-02-28", "10"] == pytest.approx(0.02)
        assert caps.loc["2015-01-31", "20"] == pytest.approx(20.0 * 50)
        assert membership.loc["2015-01-31", "10"]
