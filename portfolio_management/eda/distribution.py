"""Return distribution analysis module."""

import pandas as pd


class DistributionAnalyzer:
    """Analyze return distributions and tail risk."""

    @staticmethod
    def describe_returns(returns: pd.DataFrame) -> pd.DataFrame:
        """
        Compute summary statistics for returns.

        Args:
            returns: DataFrame of returns.

        Returns:
            DataFrame with summary statistics.
        """
        stats = pd.DataFrame(index=returns.columns)
        stats['mean'] = returns.mean()
        stats['std'] = returns.std()
        stats['min'] = returns.min()
        stats['max'] = returns.max()
        stats['skew'] = returns.skew()
        stats['kurtosis'] = returns.kurtosis()
        return stats

    @staticmethod
    def value_at_risk(returns: pd.DataFrame, confidence: float = 0.95) -> pd.Series:
        """
        Compute Value at Risk (VaR) at given confidence level.

        Args:
            returns: DataFrame of returns.
            confidence: Confidence level (e.g., 0.95 for 95%).

        Returns:
            Series of VaR values by asset.
        """
        alpha = 1 - confidence
        return returns.quantile(alpha)

    @staticmethod
    def conditional_var(returns: pd.DataFrame, confidence: float = 0.95) -> pd.Series:
        """
        Compute Conditional Value at Risk (CVaR / Expected Shortfall).

        Args:
            returns: DataFrame of returns.
            confidence: Confidence level.

        Returns:
            Series of CVaR values by asset.
        """
        alpha = 1 - confidence
        var = returns.quantile(alpha)
        return returns[returns <= var].mean()

    @staticmethod
    def plot_distribution(returns: pd.DataFrame, bins: int = 50) -> None:
        """
        Plot return distributions.

        Args:
            returns: DataFrame of returns.
            bins: Number of histogram bins.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib required for plotting. Install with `pip install matplotlib`.")

        fig, axes = plt.subplots(len(returns.columns), 1, figsize=(10, 4 * len(returns.columns)))

        if len(returns.columns) == 1:
            axes = [axes]

        for ax, col in zip(axes, returns.columns):
            ax.hist(returns[col].dropna(), bins=bins, alpha=0.7, edgecolor='black')
            ax.set_title(f"Return Distribution: {col}")
            ax.set_xlabel("Return")
            ax.set_ylabel("Frequency")
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_distribution_overview(returns: pd.DataFrame, bins: int = 50) -> None:
        """
        Plot comprehensive distribution overview with histograms and Q-Q plots in subplots.

        Args:
            returns: DataFrame of returns.
            bins: Number of histogram bins.
        """
        try:
            import matplotlib.pyplot as plt
            from scipy import stats
        except ImportError:
            raise ImportError("matplotlib and scipy required for distribution plots.")

        # Set a clean style
        plt.style.use('default')
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'

        n_assets = len(returns.columns)
        fig, axes = plt.subplots(n_assets, 2, figsize=(14, 4 * n_assets))
        fig.suptitle('Return Distribution Analysis', fontsize=16, fontweight='bold', y=0.98)

        if n_assets == 1:
            axes = [axes]  # Make it 2D

        # Colors for assets
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, col in enumerate(returns.columns):
            color = colors[i % len(colors)]
            data = returns[col].dropna()

            # Histogram
            ax_hist = axes[i][0]
            ax_hist.hist(data, bins=bins, alpha=0.7, color=color, edgecolor='black', linewidth=0.5)
            ax_hist.set_title(
                f'{col} - Return Distribution',
                fontsize=14,
                fontweight='bold',
                pad=10)
            ax_hist.set_xlabel('Return', fontsize=12)
            ax_hist.set_ylabel('Frequency', fontsize=12)
            ax_hist.grid(True, alpha=0.3, linestyle='--')
            ax_hist.spines['top'].set_visible(False)
            ax_hist.spines['right'].set_visible(False)

            # Q-Q Plot
            ax_qq = axes[i][1]
            stats.probplot(data, dist="norm", plot=ax_qq)
            ax_qq.set_title(f'{col} - Q-Q Plot', fontsize=14, fontweight='bold', pad=10)
            ax_qq.grid(True, alpha=0.3, linestyle='--')
            ax_qq.spines['top'].set_visible(False)
            ax_qq.spines['right'].set_visible(False)

        plt.tight_layout()
        plt.subplots_adjust(top=0.92, hspace=0.3, wspace=0.2)
        plt.show()
