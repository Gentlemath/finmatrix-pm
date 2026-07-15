"""Time series modeling and prediction module."""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Union


class GARCHPredictor:
    """GARCH model for volatility and return prediction."""

    def __init__(self, p: int = 1, q: int = 1, mean_model: str = 'Constant'):
        """
        Initialize GARCH predictor.

        Args:
            p: GARCH order (volatility lags)
            q: ARCH order (squared residual lags)
            mean_model: Mean model type ('Constant', 'AR', 'Zero')
        """
        self.p = p
        self.q = q
        self.mean_model = mean_model
        self.model = None
        self.fitted_model = None
        self.residuals = None
        self.conditional_volatility = None

    def fit(self, returns: pd.Series, update_freq: int = 1) -> Dict[str, float]:
        """
        Fit GARCH model to returns data.

        Args:
            returns: Time series of returns
            update_freq: Frequency of parameter updates

        Returns:
            Dictionary with model summary statistics
        """
        try:
            from arch import arch_model
        except ImportError:
            raise ImportError(
                "arch library required for GARCH modeling. Install with `pip install arch`.")

        # Create the model
        self.model = arch_model(
            returns,
            mean=self.mean_model,
            vol='Garch',
            p=self.p,
            q=self.q,
        )

        # Fit with optional update frequency
        self.fitted_model = self.model.fit(disp='off', update_freq=update_freq)

        # Store residuals and conditional volatility
        self.residuals = self.fitted_model.resid
        self.conditional_volatility = self.fitted_model.conditional_volatility

        # Return summary statistics
        summary = {
            'aic': self.fitted_model.aic,
            'bic': self.fitted_model.bic,
            'log_likelihood': self.fitted_model.loglikelihood,
            'convergence': getattr(self.fitted_model, 'convergence_flag', None),
            'iterations': getattr(self.fitted_model, 'iterations', None)
        }

        return summary

    def predict_volatility(self, horizon: int = 1) -> pd.Series:
        """
        Predict future conditional volatility.

        Args:
            horizon: Number of periods ahead to forecast

        Returns:
            Series of predicted volatilities
        """
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before prediction.")

        # return forcast.mean, forcast.variance, and forcast.residual_variance
        forecast = self.fitted_model.forecast(horizon=horizon)
        return forecast.variance.iloc[-1]  # last row of variance forecast for the horizon

    def predict_return(self, horizon: int = 1, method: str = 'zero') -> pd.Series:
        """
        Predict future returns using GARCH volatility.

        Args:
            horizon: Number of periods ahead to forecast
            method: Prediction method ('zero' for mean return, 'historical' for historical mean)

        Returns:
            Series of predicted returns with confidence intervals
        """
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before prediction.")

        # Get volatility forecast
        vol_forecast = self.predict_volatility(horizon)

        # Get mean forecast based on method
        if method == 'zero':
            mean_forecast = 0.0
        elif method == 'historical':
            # Use the mean from the fitted model
            mean_forecast = self.fitted_model.params.get('mu', 0.0)
        else:
            raise ValueError(f"Unknown method: {method}")

        # For simplicity, return point forecast (mean) and volatility
        # In practice, you might want to return distribution parameters
        predictions = pd.Series({
            'predicted_return': mean_forecast,
            'predicted_volatility': np.sqrt(vol_forecast.iloc[0]),
            'confidence_interval_95_lower': mean_forecast - 1.96 * np.sqrt(vol_forecast.iloc[0]),
            'confidence_interval_95_upper': mean_forecast + 1.96 * np.sqrt(vol_forecast.iloc[0])
        })

        return predictions

    def get_model_summary(self) -> str:
        """Get detailed model summary."""
        if self.fitted_model is None:
            return "Model not fitted yet."

        return str(self.fitted_model.summary())

    def get_parameters(self) -> pd.Series:
        """Get fitted model parameters."""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before getting parameters.")

        return self.fitted_model.params

    def plot_volatility(self) -> None:
        """Plot conditional volatility."""
        if self.conditional_volatility is None:
            raise ValueError("Model must be fitted before plotting.")

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("matplotlib required for plotting.")

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(self.conditional_volatility.index, self.conditional_volatility.values,
                label='Conditional Volatility', color='red', linewidth=1.5)
        ax.set_title('GARCH Conditional Volatility')
        ax.set_xlabel('Date')
        ax.set_ylabel('Volatility')
        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()
        plt.show()

    def evaluate_model(self, test_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """
        Evaluate model performance.

        Args:
            test_returns: Optional test set for out-of-sample evaluation

        Returns:
            Dictionary with evaluation metrics
        """
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before evaluation.")

        evaluation = {}

        # In-sample evaluation
        evaluation['in_sample_log_likelihood'] = self.fitted_model.loglikelihood
        evaluation['in_sample_aic'] = self.fitted_model.aic
        evaluation['in_sample_bic'] = self.fitted_model.bic

        # Standardized residuals should be approximately white noise
        std_resid = self.fitted_model.resid / self.fitted_model.conditional_volatility
        evaluation['std_resid_mean'] = std_resid.mean()
        evaluation['std_resid_std'] = std_resid.std()
        evaluation['std_resid_skew'] = std_resid.skew()
        evaluation['std_resid_kurtosis'] = std_resid.kurtosis()

        # Ljung-Box test for autocorrelation in squared residuals
        try:
            from statsmodels.stats.diagnostic import acorr_ljungbox
            lb_test = acorr_ljungbox(std_resid**2, lags=[10], return_df=True)
            evaluation['ljung_box_pvalue'] = lb_test['lb_pvalue'].iloc[0]
        except ImportError:
            evaluation['ljung_box_pvalue'] = None

        return evaluation


class ARIMAGARCHPredictor:
    """
    AR-style mean model with GARCH volatility for return prediction.

    Despite the class name, the current implementation is not a full
    ARIMA(p, d, q)-GARCH model. It uses ``arch_model(..., mean="ARX")``, so the
    ``p`` value supplies autoregressive lags, while ``q`` is not used as a true
    moving-average term. The fitted structure is closer to:

        return_t = const + phi_1 * return_{t-1} + epsilon_t
        epsilon_t = sigma_t * z_t
        sigma_t^2 = omega + alpha_1 * epsilon_{t-1}^2 + beta_1 * sigma_{t-1}^2

    A true ARMA/ARIMA-GARCH model would also include lagged innovation terms
    such as ``theta_1 * epsilon_{t-1}`` in the mean equation.
    """

    def __init__(self, arima_order: Tuple[int, int, int] = (
            1, 0, 1), garch_order: Tuple[int, int] = (1, 1)):
        """
        Initialize ARIMA-GARCH predictor.

        Args:
            arima_order: (p, d, q) for ARIMA mean model
            garch_order: (p, q) for GARCH volatility model
        """
        self.arima_order = arima_order
        self.garch_order = garch_order
        self.model = None
        self.fitted_model = None

    def fit(self, returns: pd.Series) -> Dict[str, float]:
        """Fit ARIMA-GARCH model."""
        try:
            from arch import arch_model
        except ImportError:
            raise ImportError("arch library required for ARIMA-GARCH modeling.")

        p, d, q = self.arima_order
        vol_p, vol_q = self.garch_order

        self.model = arch_model(
            returns,
            mean='ARX' if p > 0 or q > 0 else 'Constant',
            lags=p if p > 0 else None,
            vol='Garch',
            p=vol_p,
            q=vol_q,
            power=2.0 if d == 0 else 1.0  # Power for integrated models
        )

        self.fitted_model = self.model.fit(disp='off')

        return {
            'aic': self.fitted_model.aic,
            'bic': self.fitted_model.bic,
            'log_likelihood': self.fitted_model.loglikelihood
        }

    def predict_return(self, horizon: int = 1) -> pd.Series:
        """Predict future returns."""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before prediction.")

        forecast = self.fitted_model.forecast(horizon=horizon)

        # Get mean forecast
        mean_forecast = forecast.mean.iloc[-1].iloc[0]

        # Get volatility forecast
        vol_forecast = np.sqrt(forecast.variance.iloc[-1].iloc[0])

        predictions = pd.Series({
            'predicted_return': mean_forecast,
            'predicted_volatility': vol_forecast,
            'confidence_interval_95_lower': mean_forecast - 1.96 * vol_forecast,
            'confidence_interval_95_upper': mean_forecast + 1.96 * vol_forecast
        })

        return predictions

    def get_model_summary(self) -> str:
        """Get detailed model summary."""
        if self.fitted_model is None:
            return "Model not fitted yet."

        return str(self.fitted_model.summary())

    def get_parameters(self) -> pd.Series:
        """Get fitted model parameters."""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before getting parameters.")

        return self.fitted_model.params

    def plot_volatility(self) -> None:
        """Plot conditional volatility."""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before plotting.")

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("matplotlib required for plotting.")

        conditional_volatility = self.fitted_model.conditional_volatility

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(conditional_volatility.index, conditional_volatility.values,
                label='Conditional Volatility', color='blue', linewidth=1.5)
        ax.set_title('ARIMA-GARCH Conditional Volatility')
        ax.set_xlabel('Date')
        ax.set_ylabel('Volatility')
        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()
        plt.show()

    def evaluate_model(self, test_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """Evaluate model performance."""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before evaluation.")

        evaluation = {}

        # In-sample evaluation
        evaluation['in_sample_log_likelihood'] = self.fitted_model.loglikelihood
        evaluation['in_sample_aic'] = self.fitted_model.aic
        evaluation['in_sample_bic'] = self.fitted_model.bic

        # Standardized residuals should be approximately white noise
        std_resid = (self.fitted_model.resid / self.fitted_model.conditional_volatility).dropna()
        evaluation['std_resid_mean'] = std_resid.mean()
        evaluation['std_resid_std'] = std_resid.std()
        evaluation['std_resid_skew'] = std_resid.skew()
        evaluation['std_resid_kurtosis'] = std_resid.kurtosis()

        # Ljung-Box test for autocorrelation in squared residuals
        try:
            from statsmodels.stats.diagnostic import acorr_ljungbox
            lb_test = acorr_ljungbox(std_resid**2, lags=[10], return_df=True)
            evaluation['ljung_box_pvalue'] = lb_test['lb_pvalue'].iloc[0]
        except ImportError:
            evaluation['ljung_box_pvalue'] = None

        return evaluation


class MarkovSwitchingGARCHPredictor:
    """Two-stage Markov-switching GARCH model for regime-aware volatility prediction."""

    def __init__(
        self,
        k_regimes: int = 2,
        garch_order: Tuple[int, int] = (1, 1),
        mean_model: str = "Constant",
        regime_probability_threshold: float = 0.5,
        min_regime_observations: int = 30,
    ):
        """
        Initialize Markov-switching GARCH predictor.

        Args:
            k_regimes: Number of latent volatility regimes.
            garch_order: (p, q) order for each regime-specific GARCH model.
            mean_model: Mean model passed to ``arch_model``.
            regime_probability_threshold: Minimum smoothed regime probability used
                when assigning observations to a regime-specific GARCH fit.
            min_regime_observations: Minimum observations required for each
                regime-specific GARCH fit.
        """
        if k_regimes < 2:
            raise ValueError("k_regimes must be at least 2.")
        if not 0.0 < regime_probability_threshold <= 1.0:
            raise ValueError("regime_probability_threshold must be in (0, 1].")
        if min_regime_observations < 1:
            raise ValueError("min_regime_observations must be positive.")

        self.k_regimes = k_regimes
        self.garch_order = garch_order
        self.mean_model = mean_model
        self.regime_probability_threshold = regime_probability_threshold
        self.min_regime_observations = min_regime_observations

        self.returns = None
        self.markov_model = None
        self.fitted_markov_model = None
        self.regime_models = {}
        self.regime_assignments = None
        self.regime_probabilities = None

    @staticmethod
    def _validate_returns(returns: Union[pd.Series, pd.DataFrame]) -> pd.Series:
        if isinstance(returns, pd.DataFrame):
            if returns.shape[1] != 1:
                raise ValueError("Input DataFrame must contain exactly one column.")
            returns = returns.iloc[:, 0]

        if not isinstance(returns, pd.Series):
            raise TypeError("returns must be a pandas Series or single-column DataFrame.")

        returns = returns.dropna()
        if returns.empty:
            raise ValueError("returns must contain at least one non-null value.")

        return returns.astype(float)

    def fit(self, returns: Union[pd.Series, pd.DataFrame], maxiter: int = 100) -> Dict[str, float]:
        """
        Fit Markov switching regimes and a GARCH model for each regime.

        The regime model is estimated first with switching variance, then each
        GARCH model is fitted on observations most associated with that regime.
        """
        try:
            from arch import arch_model
        except ImportError:
            raise ImportError(
                "arch library required for GARCH modeling. Install with `pip install arch`.")

        try:
            from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
        except ImportError:
            raise ImportError("statsmodels required for Markov switching estimation.")

        self.returns = self._validate_returns(returns)
        if len(self.returns) < self.min_regime_observations:
            raise ValueError(
                "returns must contain at least min_regime_observations observations."
            )

        self.markov_model = MarkovRegression(
            self.returns,
            k_regimes=self.k_regimes,
            trend="c",
            switching_variance=True,
        )
        self.fitted_markov_model = self.markov_model.fit(disp=False, maxiter=maxiter)

        probabilities = self.fitted_markov_model.smoothed_marginal_probabilities
        if not isinstance(probabilities, pd.DataFrame):
            probabilities = pd.DataFrame(probabilities, index=self.returns.index)
        probabilities.columns = range(self.k_regimes)

        self.regime_probabilities = probabilities
        self.regime_assignments = probabilities.idxmax(axis=1).astype(int)
        self.regime_models = {}

        vol_p, vol_q = self.garch_order
        for regime in range(self.k_regimes):
            selected = probabilities[regime] >= self.regime_probability_threshold
            regime_returns = self.returns[selected]

            if len(regime_returns) < self.min_regime_observations:
                top_index = probabilities[regime].nlargest(self.min_regime_observations).index
                regime_returns = self.returns.loc[top_index].sort_index()

            model = arch_model(
                regime_returns,
                mean=self.mean_model,
                vol="Garch",
                p=vol_p,
                q=vol_q,
            )
            self.regime_models[regime] = model.fit(disp="off")

        return {
            "aic": self.fitted_markov_model.aic,
            "bic": self.fitted_markov_model.bic,
            "log_likelihood": self.fitted_markov_model.llf,
            "regime_count": self.k_regimes,
        }

    def get_regime_probabilities(self, smoothed: bool = True) -> pd.DataFrame:
        """Return filtered or smoothed regime probabilities."""
        if self.fitted_markov_model is None:
            raise ValueError("Model must be fitted before getting regime probabilities.")

        probabilities = (
            self.fitted_markov_model.smoothed_marginal_probabilities
            if smoothed
            else self.fitted_markov_model.filtered_marginal_probabilities
        )
        if isinstance(probabilities, pd.DataFrame):
            return probabilities.copy()

        return pd.DataFrame(probabilities, index=self.returns.index)

    def get_transition_matrix(self) -> pd.DataFrame:
        """Return estimated regime transition probabilities."""
        if self.fitted_markov_model is None:
            raise ValueError("Model must be fitted before getting transition probabilities.")

        transition = self.markov_model.regime_transition_matrix(self.fitted_markov_model.params)
        matrix = transition[:, :, -1] if transition.ndim == 3 else transition
        return pd.DataFrame(matrix, index=range(self.k_regimes), columns=range(self.k_regimes))

    def predict_volatility(self, horizon: int = 1) -> pd.Series:
        """Predict future volatility using regime-probability-weighted GARCH forecasts."""
        if self.fitted_markov_model is None or not self.regime_models:
            raise ValueError("Model must be fitted before prediction.")
        if horizon < 1:
            raise ValueError("horizon must be at least 1.")

        transition = self.get_transition_matrix().to_numpy()
        filtered_probabilities = self.get_regime_probabilities(smoothed=False)
        current_probabilities = filtered_probabilities.iloc[-1].to_numpy(dtype=float)

        regime_variances = []
        for regime in range(self.k_regimes):
            forecast = self.regime_models[regime].forecast(horizon=horizon)
            regime_variances.append(forecast.variance.iloc[-1].to_numpy(dtype=float))
        regime_variances = np.vstack(regime_variances)

        weighted_variances = []
        next_probabilities = current_probabilities
        for step in range(horizon):
            next_probabilities = transition @ next_probabilities
            weighted_variances.append(float(next_probabilities @ regime_variances[:, step]))

        return pd.Series(
            np.sqrt(weighted_variances),
            index=[f"h.{step}" for step in range(1, horizon + 1)],
            name="predicted_volatility",
        )

    def predict_return(self, horizon: int = 1, method: str = "zero") -> pd.Series:
        """Predict next-period return and confidence interval."""
        if self.fitted_markov_model is None:
            raise ValueError("Model must be fitted before prediction.")

        volatility = self.predict_volatility(horizon=horizon).iloc[0]

        if method == "zero":
            mean_forecast = 0.0
        elif method == "regime_weighted":
            transition = self.get_transition_matrix().to_numpy()
            current_probabilities = self.get_regime_probabilities(
                smoothed=False).iloc[-1].to_numpy(dtype=float)
            next_probabilities = transition @ current_probabilities
            regime_means = np.array([self.regime_models[regime].params.get("mu", 0.0)
                                     for regime in range(self.k_regimes)])
            mean_forecast = float(next_probabilities @ regime_means)
        else:
            raise ValueError(f"Unknown method: {method}")

        return pd.Series(
            {
                "predicted_return": mean_forecast,
                "predicted_volatility": volatility,
                "confidence_interval_95_lower": mean_forecast - 1.96 * volatility,
                "confidence_interval_95_upper": mean_forecast + 1.96 * volatility,
            }
        )

    def get_model_summary(self) -> str:
        """Get the Markov switching model summary."""
        if self.fitted_markov_model is None:
            return "Model not fitted yet."

        return str(self.fitted_markov_model.summary())
