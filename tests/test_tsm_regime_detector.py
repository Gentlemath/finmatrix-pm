"""Tests for the rule-based RegimeDetector."""

import pandas as pd
import pytest

from portfolio_management.tsm import RegimeDetector


class TestValidation:
    def test_empty_series_raises(self):
        with pytest.raises(ValueError):
            RegimeDetector().detect_regimes(pd.Series([], dtype=float))

    def test_multi_column_frame_raises(self, returns_frame):
        with pytest.raises(ValueError):
            RegimeDetector().detect_regimes(returns_frame)

    def test_non_series_input_raises(self):
        with pytest.raises(TypeError):
            RegimeDetector().detect_regimes([1, 2, 3])

    def test_single_column_frame_is_accepted(self, returns_frame):
        result = RegimeDetector().detect_regimes(returns_frame[["AAA"]])
        assert isinstance(result, pd.DataFrame)


class TestDetectRegimes:
    def test_output_columns(self, regime_series):
        result = RegimeDetector().detect_regimes(regime_series)
        assert list(result.columns) == [
            "rolling_volatility",
            "threshold",
            "regime",
            "regime_change",
        ]

    def test_regime_is_binary(self, regime_series):
        result = RegimeDetector().detect_regimes(regime_series)
        assert set(result["regime"].unique()) <= {0, 1}

    def test_detects_injected_high_vol_regime(self, regime_series):
        detector = RegimeDetector(window=20, threshold=1.0, min_duration=5)
        result = detector.detect_regimes(regime_series)
        # The injected high-vol block should trigger at least one high-vol period
        # and at least one regime change.
        assert (result["regime"] == 1).any()
        assert result["regime_change"].sum() >= 1

    def test_compute_rolling_volatility_length(self, regime_series):
        vol = RegimeDetector(window=30).compute_rolling_volatility(regime_series)
        assert len(vol) == len(regime_series)
        assert vol.iloc[:29].isna().all()  # first window-1 values undefined


class TestSmoothing:
    def test_min_duration_removes_short_runs(self, rng):
        # Alternating 0/1 noise with a large min_duration should collapse to a
        # single stable regime after smoothing.
        detector = RegimeDetector(window=5, threshold=0.5, min_duration=50)
        idx = pd.date_range("2022-01-01", periods=300, freq="B")
        series = pd.Series(rng.normal(size=300), index=idx)
        result = detector.detect_regimes(series)
        # Very few regime changes should survive aggressive smoothing.
        assert result["regime_change"].sum() <= 5
