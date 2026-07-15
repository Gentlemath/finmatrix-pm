"""Tests for the GARCH-family predictors in portfolio_management.tsm.prediction.

Models are fit on synthetic percent-scale returns. Fits are small and fast; no
network access is involved.
"""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.tsm import (
    ARIMAGARCHPredictor,
    GARCHPredictor,
    MarkovSwitchingGARCHPredictor,
)


class TestGARCHPredictor:
    def test_fit_returns_summary(self, returns_series):
        model = GARCHPredictor(p=1, q=1)
        summary = model.fit(returns_series)
        assert {"aic", "bic", "log_likelihood"} <= set(summary)
        assert np.isfinite(summary["aic"])

    def test_fit_populates_state(self, returns_series):
        model = GARCHPredictor()
        model.fit(returns_series)
        assert model.fitted_model is not None
        assert model.conditional_volatility is not None
        assert (model.conditional_volatility > 0).all()

    def test_predict_volatility_positive(self, returns_series):
        model = GARCHPredictor()
        model.fit(returns_series)
        vol = model.predict_volatility(horizon=5)
        assert len(vol) == 5
        assert (vol > 0).all()

    def test_predict_return_keys_and_ci_ordering(self, returns_series):
        model = GARCHPredictor()
        model.fit(returns_series)
        pred = model.predict_return(horizon=1)
        assert {
            "predicted_return",
            "predicted_volatility",
            "confidence_interval_95_lower",
            "confidence_interval_95_upper",
        } <= set(pred.index)
        assert pred["confidence_interval_95_lower"] <= pred["confidence_interval_95_upper"]
        assert pred["predicted_volatility"] > 0

    def test_predict_return_unknown_method_raises(self, returns_series):
        model = GARCHPredictor()
        model.fit(returns_series)
        with pytest.raises(ValueError, match="Unknown method"):
            model.predict_return(method="nonsense")

    def test_evaluate_model_keys(self, returns_series):
        model = GARCHPredictor()
        model.fit(returns_series)
        evaluation = model.evaluate_model()
        assert "ljung_box_pvalue" in evaluation
        assert "in_sample_aic" in evaluation

    def test_methods_require_fit(self):
        model = GARCHPredictor()
        with pytest.raises(ValueError):
            model.predict_volatility()
        with pytest.raises(ValueError):
            model.predict_return()
        with pytest.raises(ValueError):
            model.get_parameters()
        with pytest.raises(ValueError):
            model.evaluate_model()

    def test_summary_before_fit_is_message(self):
        assert GARCHPredictor().get_model_summary() == "Model not fitted yet."


class TestARIMAGARCHPredictor:
    def test_fit_returns_summary(self, returns_series):
        model = ARIMAGARCHPredictor(arima_order=(1, 0, 1), garch_order=(1, 1))
        summary = model.fit(returns_series)
        assert {"aic", "bic", "log_likelihood"} <= set(summary)

    def test_predict_return_ci_ordering(self, returns_series):
        model = ARIMAGARCHPredictor()
        model.fit(returns_series)
        pred = model.predict_return(horizon=1)
        assert pred["confidence_interval_95_lower"] <= pred["confidence_interval_95_upper"]
        assert pred["predicted_volatility"] > 0

    def test_predict_requires_fit(self):
        with pytest.raises(ValueError):
            ARIMAGARCHPredictor().predict_return()


class TestMarkovSwitchingGARCHPredictor:
    def test_init_validation(self):
        with pytest.raises(ValueError):
            MarkovSwitchingGARCHPredictor(k_regimes=1)
        with pytest.raises(ValueError):
            MarkovSwitchingGARCHPredictor(regime_probability_threshold=0.0)
        with pytest.raises(ValueError):
            MarkovSwitchingGARCHPredictor(min_regime_observations=0)

    def test_fit_returns_summary(self, regime_series):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        summary = model.fit(regime_series)
        assert summary["regime_count"] == 2
        assert {"aic", "bic", "log_likelihood"} <= set(summary)
        assert len(model.regime_models) == 2

    def test_transition_matrix_rows_sum_to_one(self, regime_series):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        model.fit(regime_series)
        matrix = model.get_transition_matrix()
        assert matrix.shape == (2, 2)
        row_sums = matrix.to_numpy().sum(axis=0)
        # statsmodels transition columns are the "from" regime; each sums to 1.
        assert np.allclose(row_sums, 1.0, atol=1e-6)

    def test_predict_volatility_positive(self, regime_series):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        model.fit(regime_series)
        vol = model.predict_volatility(horizon=3)
        assert len(vol) == 3
        assert (vol > 0).all()

    def test_predict_return_methods(self, regime_series):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        model.fit(regime_series)
        for method in ("zero", "regime_weighted"):
            pred = model.predict_return(horizon=1, method=method)
            assert pred["confidence_interval_95_lower"] <= pred["confidence_interval_95_upper"]

    def test_predict_requires_fit(self):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        with pytest.raises(ValueError):
            model.predict_volatility()
        with pytest.raises(ValueError):
            model.get_transition_matrix()

    def test_fit_rejects_empty_series(self):
        model = MarkovSwitchingGARCHPredictor(k_regimes=2)
        with pytest.raises(ValueError):
            model.fit(pd.Series([], dtype=float))
