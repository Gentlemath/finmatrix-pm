"""Tests for time-series (trend-following) momentum (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.strategy import (
    TREND_SPEEDS,
    TimeSeriesMomentum,
    lookback_by_group,
    speed_group,
    trend_signal_table,
)
from portfolio_management.strategy.performance import apply_costs, turnover


def _months(n, start="2015-01-31"):
    return pd.date_range(start, periods=n, freq="ME")


def _weeks(n, start="2015-01-02"):
    return pd.date_range(start, periods=n, freq="W-FRI")


class TestSignalDirection:
    def test_long_uptrend_short_downtrend(self):
        # one asset trends up, one trends down; both should be profitable because
        # the strategy goes long the riser and short the faller.
        idx = _months(30)
        up = pd.Series(0.02, index=idx)
        down = pd.Series(-0.02, index=idx)
        returns = pd.DataFrame({"UP": up, "DOWN": down})
        # scale=False so a constant-return (zero-vol) series is not dropped
        out = TimeSeriesMomentum(lookback=12, scale=False).backtest(returns)
        assert out["strategy"].dropna().mean() > 0
        # DOWN is held short: its (negative-weight x negative-return) contribution is positive
        assert out["short"].dropna().mean() > 0

    def test_long_or_flat_drops_shorts(self):
        idx = _months(30)
        returns = pd.DataFrame({"UP": pd.Series(0.02, index=idx),
                                "DOWN": pd.Series(-0.02, index=idx)})
        _, w = TimeSeriesMomentum(lookback=12, scale=False, long_short=False).backtest(
            returns, return_weights=True)
        # no short weights anywhere; DOWN never gets a negative position
        assert (w.fillna(0.0) >= 0).all().all()
        assert (w.get("DOWN", pd.Series(0.0)).fillna(0.0) == 0).all()

    def test_signal_flips_after_trend_reverses(self):
        # up for 15 months then down for 15: direction should flip from +1 to -1
        idx = _months(30)
        r = pd.Series([0.03] * 15 + [-0.03] * 15, index=idx)
        sign = trend_signal_table(pd.DataFrame({"A": r}), lookback=12)["A"]
        assert sign.dropna().iloc[0] == 1.0        # first valid signal: uptrend
        assert sign.dropna().iloc[-1] == -1.0      # after the reversal: downtrend


class TestVolScaling:
    def test_low_vol_asset_gets_larger_weight(self):
        # two up-trending assets with the same sign but very different volatility;
        # inverse-vol sizing must give the calmer asset the bigger position.
        rng = np.random.default_rng(0)
        idx = _months(60)
        calm = 0.01 + rng.normal(0, 0.005, 60)     # low vol, positive drift
        wild = 0.01 + rng.normal(0, 0.05, 60)      # high vol, positive drift
        returns = pd.DataFrame({"CALM": calm, "WILD": wild}, index=idx)
        _, w = TimeSeriesMomentum(lookback=12, vol_window=24, scale=True).backtest(
            returns, return_weights=True)
        last = w.dropna().iloc[-1]
        assert abs(last["CALM"]) > abs(last["WILD"])

    def test_unscaled_weights_are_equal_magnitude(self):
        rng = np.random.default_rng(1)
        idx = _months(40)
        returns = pd.DataFrame(
            {c: 0.01 + rng.normal(0, v, 40) for c, v in [("A", 0.01), ("B", 0.05)]},
            index=idx)
        _, w = TimeSeriesMomentum(lookback=12, scale=False).backtest(
            returns, return_weights=True)
        row = w.dropna().iloc[-1].abs()
        assert row.max() == pytest.approx(row.min())   # equal gross weight per asset


class TestMixedFrequencyVol:
    """Volatility estimated on a higher-frequency panel, trading still monthly."""

    def test_same_panel_reproduces_single_frequency_result(self):
        rng = np.random.default_rng(7)
        idx = _months(60)
        returns = pd.DataFrame(
            {c: 0.01 + rng.normal(0, v, 60) for c, v in [("A", 0.02), ("B", 0.04)]},
            index=idx)
        tsm = TimeSeriesMomentum(lookback=12, vol_window=24, scale=True)
        base = tsm.backtest(returns, periods_per_year=12)
        same = tsm.backtest(returns, periods_per_year=12,
                            vol_returns=returns, vol_periods_per_year=12)
        pd.testing.assert_frame_equal(base, same)

    def test_weekly_vol_is_used_and_changes_sizing(self):
        rng = np.random.default_rng(8)
        m_idx = _months(48)
        w_idx = _weeks(48 * 5)
        monthly = pd.DataFrame(
            {c: 0.01 + rng.normal(0, 0.02, 48) for c in ("A", "B")}, index=m_idx)
        # B is far more volatile at weekly frequency than the monthly panel shows
        weekly = pd.DataFrame(
            {"A": rng.normal(0, 0.005, 48 * 5), "B": rng.normal(0, 0.05, 48 * 5)},
            index=w_idx)
        _, w = TimeSeriesMomentum(lookback=12, vol_window=26, scale=True).backtest(
            monthly, periods_per_year=12, return_weights=True,
            vol_returns=weekly, vol_periods_per_year=52)
        last = w.dropna().iloc[-1].abs()
        assert last["A"] > last["B"]        # weekly vol drives the sizing

    def test_alignment_has_no_lookahead(self):
        """A volatility spike after a formation date must not affect that date."""
        m_idx = _months(40)
        w_idx = _weeks(40 * 5)
        monthly = pd.DataFrame({"A": 0.01, "B": 0.01}, index=m_idx)

        # NB: constant returns would give zero volatility and be filtered out by
        # the `vol > 0` eligibility check, so the calm panel needs real dispersion.
        rng = np.random.default_rng(11)
        calm = pd.DataFrame(
            {"A": rng.normal(0, 0.005, len(w_idx)),
             "B": rng.normal(0, 0.005, len(w_idx))}, index=w_idx)
        spiked = calm.copy()
        cut = m_idx[30]                                  # a formation date
        after = spiked.index > cut
        spiked.loc[after, "B"] = rng.normal(0, 0.20, after.sum())   # spike AFTER only

        kw = dict(periods_per_year=12, return_weights=True,
                  vol_periods_per_year=52)
        tsm = TimeSeriesMomentum(lookback=12, vol_window=26, scale=True)
        _, w_calm = tsm.backtest(monthly, vol_returns=calm, **kw)
        _, w_spike = tsm.backtest(monthly, vol_returns=spiked, **kw)

        # weights formed at or before `cut` must be identical in both worlds
        upto = w_calm.index[w_calm.index <= cut]
        pd.testing.assert_frame_equal(w_calm.loc[upto], w_spike.loc[upto])
        # and the spike must actually bite afterwards (otherwise the test is vacuous)
        assert w_spike.iloc[-1].abs()["B"] < w_calm.iloc[-1].abs()["B"]

    def test_vol_periods_per_year_required(self):
        idx = _months(30)
        returns = pd.DataFrame({"A": 0.01, "B": -0.01}, index=idx)
        with pytest.raises(ValueError, match="vol_periods_per_year"):
            TimeSeriesMomentum(lookback=12).backtest(returns, vol_returns=returns)


class TestMechanics:
    def test_no_lookahead_alignment(self):
        # deterministic: constant +1% asset, always long, unscaled equal weight.
        # with one asset the weight is 1.0, so strategy return == the held return.
        idx = _months(20)
        returns = pd.DataFrame({"A": pd.Series(0.01, index=idx)})
        out = TimeSeriesMomentum(lookback=12, scale=False).backtest(returns)
        assert np.allclose(out["strategy"].dropna(), 0.01)
        # first holding month is the 14th row (needs 12 for signal, held next month)
        assert out.index[0] == idx[12]

    def test_weights_support_cost_and_turnover(self):
        rng = np.random.default_rng(2)
        idx = _months(48)
        returns = pd.DataFrame(
            {c: rng.normal(0.01, 0.04, 48) for c in ["A", "B", "C"]}, index=idx)
        res, w = TimeSeriesMomentum(lookback=12).backtest(returns, return_weights=True)
        net = apply_costs(res["strategy"], w, cost=0.001)
        assert (net <= res["strategy"] + 1e-12).all()          # costs never help
        assert turnover(w)["avg_one_way"] >= 0

    def test_empty_when_history_too_short(self):
        idx = _months(6)
        returns = pd.DataFrame({"A": pd.Series(0.01, index=idx)})
        out = TimeSeriesMomentum(lookback=12).backtest(returns)
        assert out.empty


class TestValidation:
    @pytest.mark.parametrize("kwargs", [
        {"lookback": 0}, {"gap": -1}, {"vol_window": 1}, {"target_vol": 0.0},
    ])
    def test_bad_params_raise(self, kwargs):
        with pytest.raises(ValueError):
            TimeSeriesMomentum(**kwargs)


class TestMultiSpeed:
    """Per-asset lookback: financials trend slowly, commodities fast."""

    def _panel(self, n=80):
        idx = _months(n)
        rng = np.random.default_rng(3)
        # SLOW persists for many months; FAST flips every few months
        slow = np.where(np.arange(n) % 48 < 24, 0.02, -0.02)
        fast = np.where(np.arange(n) % 8 < 4, 0.05, -0.05)
        return pd.DataFrame({"SLOW": slow + rng.normal(0, 0.002, n),
                             "FAST": fast + rng.normal(0, 0.002, n)}, index=idx)

    def test_dict_lookback_uses_per_asset_window(self):
        r = self._panel()
        sig = TimeSeriesMomentum(lookback={"SLOW": 12, "FAST": 3}).compute_signal(r)
        # each column must match its own single-window computation
        for col, lb in (("SLOW", 12), ("FAST", 3)):
            want = TimeSeriesMomentum(lookback=lb).compute_signal(r[[col]])[col]
            pd.testing.assert_series_equal(sig[col], want, check_names=False)

    def test_asset_missing_from_dict_is_excluded_not_defaulted(self):
        r = self._panel()
        tsm = TimeSeriesMomentum(lookback={"SLOW": 12}, scale=False)
        sig = tsm.compute_signal(r)
        assert sig["FAST"].isna().all()          # never silently traded
        _, w = tsm.backtest(r, return_weights=True)
        assert "FAST" not in w.columns or w["FAST"].abs().sum() == 0

    def test_matching_speed_to_persistence_beats_mismatching(self):
        r = self._panel()
        kw = dict(scale=False, long_short=True)
        good = TimeSeriesMomentum(lookback={"SLOW": 12, "FAST": 3}, **kw)
        bad = TimeSeriesMomentum(lookback={"SLOW": 3, "FAST": 12}, **kw)
        g = good.backtest(r)["strategy"].mean()
        b = bad.backtest(r)["strategy"].mean()
        assert g > b                              # the falsification direction

    def test_lookback_by_group(self):
        groups = {"BUND": "bond", "SPX": "equity", "WTI": "energy"}
        lb = lookback_by_group(groups, {"bond": 12, "equity": 12, "energy": 6})
        assert lb == {"BUND": 12, "SPX": 12, "WTI": 6}

    def test_lookback_by_group_default_and_strictness(self):
        groups = {"BUND": "bond", "COCOA": "ag"}
        assert lookback_by_group(groups, {"bond": 12}, default=6)["COCOA"] == 6
        with pytest.raises(ValueError, match="no speed"):
            lookback_by_group(groups, {"bond": 12})

    @pytest.mark.parametrize("bad", [{}, {"A": 0}, {"A": 1.5}, {"A": -3}])
    def test_bad_dict_lookback_raises(self, bad):
        with pytest.raises(ValueError):
            TimeSeriesMomentum(lookback=bad)


class TestThreeSpeedGrouping:
    """The measured grouping splits metals by monetary vs industrial."""

    def test_trend_speeds_constant(self):
        assert set(TREND_SPEEDS) == {"slow", "mid", "fast"}
        # slow > mid > fast, or the grouping labels have drifted from the data
        assert TREND_SPEEDS["slow"] > TREND_SPEEDS["mid"] > TREND_SPEEDS["fast"]

    def test_precious_metals_group_slow_not_fast(self):
        """Gold with copper would be the easy mistake; they trend differently."""
        cls = {"BUND": "bond", "GOLD": "metal", "COPPER": "metal",
               "DAX": "equity", "WTI": "energy"}
        precious = {"GOLD"}

        def grp(a):
            if cls[a] == "bond" or a in precious:
                return "slow"
            return "mid" if cls[a] in ("equity", "fx") else "fast"

        lb = lookback_by_group({a: grp(a) for a in cls}, TREND_SPEEDS)
        assert lb["GOLD"] == lb["BUND"] == TREND_SPEEDS["slow"]
        assert lb["COPPER"] == lb["WTI"] == TREND_SPEEDS["fast"]
        assert lb["GOLD"] != lb["COPPER"]        # the whole point


class TestSpeedGroup:
    """The recommended asset -> speed-group mapping."""

    @pytest.mark.parametrize("asset,cls,want", [
        ("BUND", "bond", "slow"), ("US10Y", "bond", "slow"),
        ("GOLD", "metal", "slow"), ("SILVER", "metal", "slow"),
        ("GLD", "metal", "slow"),               # the ETF name too
        ("COPPER", "metal", "fast"), ("ZINC", "metal", "fast"),
        ("DAX", "equity", "mid"), ("USDINDEX", "fx", "mid"),
        ("BRENT", "energy", "fast"), ("COCOA", "ag", "fast"),
        ("SOMETHING", "unknown", "fast"),       # unrecognised -> commodity default
    ])
    def test_grouping(self, asset, cls, want):
        assert speed_group(asset, cls) == want

    def test_precious_and_industrial_metals_differ(self):
        """The load-bearing distinction: same asset class, opposite speeds."""
        assert speed_group("GOLD", "metal") != speed_group("COPPER", "metal")

    def test_case_insensitive_on_asset_name(self):
        assert speed_group("gold", "metal") == "slow"

    def test_composes_with_lookback_by_group(self):
        cls = {"BUND": "bond", "GOLD": "metal", "COPPER": "metal", "DAX": "equity"}
        groups = {a: speed_group(a, c) for a, c in cls.items()}
        lb = lookback_by_group(groups, TREND_SPEEDS)
        assert lb["BUND"] == lb["GOLD"] == TREND_SPEEDS["slow"]
        assert lb["COPPER"] == TREND_SPEEDS["fast"]
        assert lb["DAX"] == TREND_SPEEDS["mid"]
