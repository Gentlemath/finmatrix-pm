"""Price and return visualization module."""

import numpy as np
import pandas as pd


class PlotAnalyzer:
    """Analyze and plot price and return series."""

    @staticmethod
    def compute_returns(prices: pd.DataFrame, method: str = "log") -> pd.DataFrame:
        """
        Compute returns from price series.

        Args:
            prices: DataFrame with price data (columns = securities).
            method: 'log' for log returns, 'simple' for simple returns.

        Returns:
            DataFrame of returns.
        """
        if method == "log":
            return np.log(prices / prices.shift(1))
        elif method == "simple":
            return prices.pct_change()
        else:
            raise ValueError(f"Unknown method: {method}")

    @staticmethod
    def cumulative_returns(returns: pd.DataFrame) -> pd.DataFrame:
        """
        Compute cumulative returns (growth of $1).

        Args:
            returns: DataFrame of returns.

        Returns:
            DataFrame of cumulative returns.
        """
        return (1 + returns).cumprod() - 1

    @staticmethod
    def plot_prices(prices: pd.DataFrame, title: str = "Price Series") -> None:
        """
        Plot price series.

        Args:
            prices: DataFrame with price data.
            title: Plot title.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib required for plotting. Install with `pip install matplotlib`.")

        fig, ax = plt.subplots(figsize=(12, 6))
        for col in prices.columns:
            ax.plot(prices.index, prices[col], label=col, linewidth=2)

        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_returns(returns: pd.DataFrame, title: str = "Returns Series") -> None:
        """
        Plot returns series.

        Args:
            returns: DataFrame of returns.
            title: Plot title.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib required for plotting. Install with `pip install matplotlib`.")

        fig, ax = plt.subplots(figsize=(12, 6))
        for col in returns.columns:
            ax.plot(returns.index, returns[col], label=col, linewidth=1.5, alpha=0.8)

        ax.set_xlabel("Date")
        ax.set_ylabel("Return")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_overview(prices: pd.DataFrame, returns: pd.DataFrame,
                      title: str = "Portfolio Overview") -> None:
        """
        Plot comprehensive overview with prices, returns, and cumulative returns in subplots.

        Args:
            prices: DataFrame with price data.
            returns: DataFrame of returns.
            title: Overall figure title.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib required for plotting. Install with `pip install matplotlib`.")

        # Set a clean style
        plt.style.use('default')
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'

        # Create subplots
        fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)

        # Colors for multiple assets
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        # Plot 1: Prices
        ax = axes[0]
        for i, col in enumerate(prices.columns):
            color = colors[i % len(colors)]
            ax.plot(prices.index, prices[col], label=col, color=color, linewidth=2, alpha=0.9)
        ax.set_ylabel('Price', fontsize=12, fontweight='bold')
        ax.set_title('Price Series', fontsize=14, fontweight='bold', pad=10)
        ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Plot 2: Returns
        ax = axes[1]
        for i, col in enumerate(returns.columns):
            color = colors[i % len(colors)]
            ax.plot(returns.index, returns[col], label=col, color=color, linewidth=1.5, alpha=0.8)
        ax.set_ylabel('Return', fontsize=12, fontweight='bold')
        ax.set_title('Return Series', fontsize=14, fontweight='bold', pad=10)
        ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=0.8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Plot 3: Cumulative Returns
        ax = axes[2]
        cum_returns = PlotAnalyzer.cumulative_returns(returns)
        for i, col in enumerate(cum_returns.columns):
            color = colors[i % len(colors)]
            ax.plot(cum_returns.index, cum_returns[col], label=col, color=color, linewidth=2)
        ax.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cumulative Return', fontsize=12, fontweight='bold')
        ax.set_title('Cumulative Returns', fontsize=14, fontweight='bold', pad=10)
        ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=0.8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Format x-axis dates
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.subplots_adjust(top=0.92, hspace=0.15)
        plt.show()
