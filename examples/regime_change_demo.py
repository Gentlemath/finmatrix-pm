import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.tsm import RegimeDetector as rd


def sp500_example(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Load the S&P 500 price series via the yfinance data loader."""
    loader = create_data_loader("yfinance")
    prices = loader.get_prices("^GSPC", start=start, end=end)
    prices.columns = ["SP500"]  # canonical panel: one column per symbol
    return prices


def main() -> None:
    start = pd.Timestamp("2020-05-12")
    end = pd.Timestamp("2026-05-12")
    prices = sp500_example(start, end)
    returns = (prices.pct_change().dropna() * 100)  # Convert to percentage

    print("=== Price summary ===")
    print(prices.tail())
    print("\n=== Return summary ===")
    print(returns.describe())

    # Visual exploration
    print("\n=== Plotting return and rolling volatility overview ===")
    detector = rd()
    detector.plot_regime_changes(returns["SP500"], window=30)


if __name__ == "__main__":
    main()
