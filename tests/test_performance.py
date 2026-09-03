"""Tests for strategy performance analytics (synthetic data)."""

import numpy as np
import pandas as pd

import pytest

from portfolio_management.strategy import (
    apply_costs,
    cap_weighted_return,
    capm,
    max_drawdown,
    performance_summary,
    transaction_costs,
    turnover,
    volatility_target,
)


def months(n, start="2020-01-31"):
    return pd.date_range(start, periods=n, freq="ME")


class TestMaxDrawdown:
    def test_known_drawdown(self):
        r = pd.Series([0.10, -0.50, 0.10], index=months(3))
        # cum: 1.10, 0.55, 0.605; peak 1.10 -> worst = 0.55/1.10 - 1 = -0.5
        assert max_drawdown(r) == pytest.approx(-0.5)

    def test_monotone_up_has_no_drawdown(self):
        r = pd.Series([0.01] * 6, index=months(6))
        assert max_drawdown(r) == pytest.approx(0.0)


class TestPerformanceSummary:
    def test_keys_and_cumulative(self):
        r = pd.Series([0.02, -0.01, 0.03, 0.00, 0.01, -0.02], index=months(6))
        s = performance_summary(r)
        assert {"ann_return", "ann_vol", "sharpe", "max_drawdown", "cumulative"} <= set(s)
        assert s["cumulative"] == pytest.approx((1 + r).prod() - 1)

    def test_risk_free_lowers_sharpe(self):
        r = pd.Series([0.03, -0.01, 0.02, 0.04, -0.02, 0.01], index=months(6))
        s0 = performance_summary(r, rf=0.0)["sharpe"]
        s_rf = performance_summary(r, rf=0.005)["sharpe"]  # positive rf
        assert s_rf < s0  # excess return is smaller, so Sharpe drops

    def test_empty_returns_nan(self):
        s = performance_summary(pd.Series([], dtype=float))
        assert s["periods"] == 0
        assert np.isnan(s["sharpe"])


class TestCapm:
    def test_beta_two_alpha_zero(self):
        bench = pd.Series([0.03, -0.01, 0.02, 0.05, -0.04, 0.01], index=months(6))
        strat = 2 * bench  # exactly twice the benchmark, no alpha
        out = capm(strat, bench, rf=0.0)
        assert out["beta"] == pytest.approx(2.0)
        assert out["alpha_annual"] == pytest.approx(0.0, abs=1e-9)
        assert out["r_squared"] == pytest.approx(1.0)


class TestTurnover:
    def test_full_rotation(self):
        w = pd.DataFrame(
            {"A": [0.5, np.nan, 0.5], "B": [0.5, np.nan, 0.5],
             "C": [np.nan, 0.5, np.nan], "D": [np.nan, 0.5, np.nan]},
            index=months(3),
        )
        # each rebalance fully swaps the book -> one-way turnover = 1.0
        assert turnover(w)["avg_one_way"] == pytest.approx(1.0)

    def test_no_change(self):
        w = pd.DataFrame({"A": [0.5, 0.5], "B": [0.5, 0.5]}, index=months(2))
        assert turnover(w)["avg_one_way"] == pytest.approx(0.0)


class TestTransactionCosts:
    def test_two_way_turnover_cost(self):
        # full rotation: sum|dw| = 2.0 per rebalance; first row establishes book (=1.0)
        w = pd.DataFrame(
            {"A": [0.5, 0.0, 0.5], "B": [0.5, 0.0, 0.5],
             "C": [0.0, 0.5, 0.0], "D": [0.0, 0.5, 0.0]},
            index=months(3),
        )
        costs = transaction_costs(w, cost=0.001)
        assert costs.iloc[0] == pytest.approx(0.001 * 1.0)   # establish: sum|w0| = 1.0
        assert costs.iloc[1] == pytest.approx(0.001 * 2.0)   # full swap: sum|dw| = 2.0

    def test_apply_costs_reduces_return(self):
        idx = months(3)
        gross = pd.Series([0.02, 0.02, 0.02], index=idx)
        w = pd.DataFrame({"A": [1.0, 0.0, 1.0], "B": [0.0, 1.0, 0.0]}, index=idx)
        net = apply_costs(gross, w, cost=0.001)
        assert (net <= gross + 1e-12).all()
        # rebalance 2 trades 2.0 in dollars -> cost 0.002 -> net = 0.018
        assert net.iloc[1] == pytest.approx(0.02 - 0.002)

    def test_zero_cost_is_identity(self):
        idx = months(2)
        gross = pd.Series([0.01, -0.01], index=idx)
        w = pd.DataFrame({"A": [1.0, 0.0], "B": [0.0, 1.0]}, index=idx)
        pd.testing.assert_series_equal(
            apply_costs(gross, w, cost=0.0), gross.rename("net")
        )


class TestCapWeightedReturn:
    def test_lagged_value_weights(self):
        idx = months(2)
        returns = pd.DataFrame({"A": [0.00, 0.10], "B": [0.00, 0.00]}, index=idx)
        caps = pd.DataFrame({"A": [100.0, 100.0], "B": [300.0, 300.0]}, index=idx)
        bench = cap_weighted_return(returns, caps)
        # first month has no prior caps -> NaN; second uses w=(0.25, 0.75)
        assert np.isnan(bench.iloc[0])
        assert bench.iloc[1] == pytest.approx(0.25 * 0.10 + 0.75 * 0.00)


class TestVolatilityTarget:
    """Constant-volatility sizing, with the leverage trade actually charged."""

    def _book(self, n=200, seed=0):
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2000-01-31", periods=n, freq="ME")
        # two assets, one calm stretch then a volatile one
        scale = np.where(np.arange(n) < n // 2, 0.01, 0.04)
        r = pd.DataFrame({"A": rng.normal(0.004, 1, n) * scale,
                          "B": rng.normal(0.004, 1, n) * scale}, index=idx)
        w = pd.DataFrame(0.5, index=idx, columns=["A", "B"])
        gross = (w * r).sum(axis=1)
        return gross, w, r

    def test_realised_vol_lands_near_target(self):
        gross, w, _ = self._book()
        net, lev, lw = volatility_target(gross, w, 0.10, window=24, cost=0.0)
        realised = net.std() * np.sqrt(12)
        assert 0.06 < realised < 0.16          # lagged estimate, so not exact

    def test_leverage_is_higher_when_volatility_is_lower(self):
        gross, w, _ = self._book()
        _, lev, _ = volatility_target(gross, w, 0.10, window=24, cost=0.0)
        first, second = lev.iloc[:len(lev) // 2], lev.iloc[len(lev) // 2:]
        assert first.mean() > second.mean()    # calm half gets more leverage

    def test_no_lookahead(self):
        """A shock after date t must not change leverage at or before t."""
        gross, w, _ = self._book()
        cut = gross.index[120]
        shocked = gross.copy()
        shocked.loc[shocked.index > cut] *= 8.0
        _, a, _ = volatility_target(gross, w, 0.10, window=24, cost=0.0)
        _, b, _ = volatility_target(shocked, w, 0.10, window=24, cost=0.0)
        upto = a.index[a.index <= cut]
        pd.testing.assert_series_equal(a.loc[upto], b.loc[upto])

    def test_leverage_change_is_charged(self):
        """Costing levered weights must exceed naively scaling a net series."""
        gross, w, _ = self._book()
        net, lev, lw = volatility_target(gross, w, 0.10, window=24, cost=0.0050)
        base = apply_costs(gross, w, cost=0.0050)
        naive = (base * lev).reindex(net.index)
        # the exact version charges the leverage trade, so it earns no more
        assert net.sum() <= naive.sum() + 1e-12

    def test_constant_scaling_leaves_sharpe_unchanged(self):
        """Contrast: a fixed multiple cannot change Sharpe; a varying one can."""
        gross, w, _ = self._book()
        base = apply_costs(gross, w, cost=0.0)
        a = performance_summary(base, periods_per_year=12)["sharpe"]
        b = performance_summary(base * 3.0, periods_per_year=12)["sharpe"]
        assert a == pytest.approx(b, rel=1e-9)

    def test_leverage_cap_respected(self):
        gross, w, _ = self._book()
        _, lev, _ = volatility_target(gross, w, 5.0, window=24,
                                      max_leverage=2.0, cost=0.0)
        assert lev.max() <= 2.0

    @pytest.mark.parametrize("kw", [{"target_vol": 0.0}, {"target_vol": -0.1},
                                    {"max_leverage": 0.0}])
    def test_bad_params_raise(self, kw):
        gross, w, _ = self._book()
        args = {"target_vol": 0.1, **kw}
        with pytest.raises(ValueError):
            volatility_target(gross, w, window=24, **args)
