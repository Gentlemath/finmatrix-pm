import pandas as pd
from typing import Optional, Union


class RegimeDetector:
    """Detect volatility regime changes from a time series of returns."""

    def __init__(
            self,
            window: int = 30,
            threshold: float = 1.5,
            min_duration: int = 10,
            baseline_window: Optional[int] = None):
        """
        Initialize the regime detector.

        Args:
            window: Rolling window size for volatility calculation.
            threshold: Number of baseline standard deviations above which
                volatility is considered high.
            min_duration: Minimum number of consecutive periods required to
                keep a regime state.
            baseline_window: Window size to compute a baseline volatility level.
                Defaults to 4x window.
        """
        self.window = window
        self.threshold = threshold
        self.min_duration = min_duration
        self.baseline_window = baseline_window or max(window * 4, window + 1)

    @staticmethod
    def _validate_input(returns: Union[pd.Series, pd.DataFrame]) -> pd.Series:
        if isinstance(returns, pd.DataFrame):
            if returns.shape[1] != 1:
                raise ValueError("Input DataFrame must contain exactly one column.")
            returns = returns.iloc[:, 0]

        if not isinstance(returns, pd.Series):
            raise TypeError("Input must be a pandas Series or a single-column DataFrame.")

        returns = returns.dropna()
        if returns.empty:
            raise ValueError("Input return series must contain at least one non-null value.")

        return returns

    def compute_rolling_volatility(self,
                                   returns: Union[pd.Series,
                                                  pd.DataFrame],
                                   window: Optional[int] = None) -> pd.Series:
        """Compute rolling volatility for the input returns."""
        returns = self._validate_input(returns)
        window = window or self.window
        return returns.rolling(window=window).std()

    def _smooth_regimes(self, regimes: pd.Series, min_duration: Optional[int] = None) -> pd.Series:
        if min_duration is None:
            min_duration = self.min_duration
        if min_duration <= 1:
            return regimes.astype(int)

        group_id = regimes.ne(regimes.shift(1)).cumsum()
        run_lengths = regimes.groupby(group_id).transform("size")
        smoothed = regimes.where(run_lengths >= min_duration)
        smoothed = smoothed.ffill().fillna(0).astype(int)
        return smoothed

    def detect_regimes(
        self,
        returns: Union[pd.Series, pd.DataFrame],
        window: Optional[int] = None,
        threshold: Optional[float] = None,
        min_duration: Optional[int] = None,
        baseline_window: Optional[int] = None,
    ) -> pd.DataFrame:
        """Detect volatility regimes and regime change points."""
        returns = self._validate_input(returns)
        window = window or self.window
        threshold = threshold or self.threshold
        min_duration = min_duration if min_duration is not None else self.min_duration
        baseline_window = baseline_window or self.baseline_window

        rolling_vol = returns.rolling(window=window).std()
        baseline_vol = rolling_vol.rolling(window=baseline_window, min_periods=1).mean()
        baseline_std = rolling_vol.rolling(window=baseline_window, min_periods=1).std()
        threshold_level = baseline_vol + threshold * baseline_std

        regime = (rolling_vol > threshold_level).astype(int)
        regime = self._smooth_regimes(regime, min_duration=min_duration)
        regime_change = regime.ne(regime.shift(1)) & rolling_vol.notna()

        return pd.DataFrame(
            {
                "rolling_volatility": rolling_vol,
                "threshold": threshold_level,
                "regime": regime,
                "regime_change": regime_change,
            }
        )

    def plot_regime_changes(
        self,
        returns: Union[pd.Series, pd.DataFrame],
        window: Optional[int] = None,
        threshold: Optional[float] = None,
        min_duration: Optional[int] = None,
        baseline_window: Optional[int] = None,
    ) -> None:
        """Plot detected volatility regimes alongside the return series."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib required for plotting. Install with `pip install matplotlib`.")

        returns = self._validate_input(returns)
        detection = self.detect_regimes(
            returns,
            window=window,
            threshold=threshold,
            min_duration=min_duration,
            baseline_window=baseline_window,
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

        ax1.plot(
            returns.index,
            returns.values,
            label=returns.name or "Returns",
            color="blue",
            linewidth=1)
        ax1.set_ylabel("Returns")
        ax1.set_title("Returns and Detected Volatility Regimes")
        ax1.grid(True, alpha=0.3)

        ax2.plot(
            detection.index,
            detection["rolling_volatility"],
            label="Rolling Volatility",
            color="orange",
            linewidth=1.5)
        ax2.plot(
            detection.index,
            detection["threshold"],
            label="Threshold",
            color="red",
            linestyle="--",
            linewidth=1)

        high_regime = detection["regime"] == 1
        ax2.fill_between(
            detection.index,
            0,
            detection["rolling_volatility"].where(high_regime),
            color="red",
            alpha=0.2,
            label="High Volatility Regime",
        )

        ax2.set_ylabel("Volatility")
        ax2.legend(loc="upper left")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()
