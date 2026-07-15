"""Example exploratory data analysis script for portfolio management."""

import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.eda import DistributionAnalyzer, PlotAnalyzer, TimeSeriesAnalyzer


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
    returns = PlotAnalyzer.compute_returns(prices, method="simple")

    print("=== Price summary ===")
    print(prices.tail())
    print("\n=== Return summary ===")
    print(returns.describe())

    # Visual exploration
    PlotAnalyzer.plot_overview(prices, returns, title="S&P 500 Portfolio Overview")

    # Distribution exploration
    print("\n=== Return distribution statistics ===")
    print(DistributionAnalyzer.describe_returns(returns))

    DistributionAnalyzer.plot_distribution_overview(returns, bins=40)

    # Time series analysis
    print("\n=== Stationarity tests ===")
    tsa = TimeSeriesAnalyzer()
    stationarity_results = tsa.test_stationarity(returns["SP500"])

    print(stationarity_results)
    if stationarity_results.get('kpss_note'):
        print(f"Note: {stationarity_results['kpss_note']}")

    print("\nInterpretation:")
    print("- ADF very low p-value suggests non-stationarity is rejected.")
    print("- KPSS p-value at or above 0.1 suggests stationarity is not rejected.")
    print("- Together, these results tell us if the return series is likely stationary.")

    print("\n=== ACF and PACF plots of log returns ===")
    tsa.plot_acf_pacf(returns["SP500"], lags=30)

    # Test for significant autocorrelation
    autocorr_results = tsa.test_autocorrelation(returns["SP500"], lags=30, alpha=0.01)
    print(
        f"\nSignificant ACF lags (alpha={autocorr_results['alpha']}): "
        f"{autocorr_results['acf_significant_lags']}")
    print(
        f"Significant PACF lags (alpha={autocorr_results['alpha']}): "
        f"{autocorr_results['pacf_significant_lags']}")

    print("\n=== ACF and PACF plots of absolute log returns ===")
    tsa.plot_acf_pacf(returns["SP500"].abs(), lags=30)

    autocorr_abs_results = tsa.test_autocorrelation(returns["SP500"].abs(), lags=30)
    print(
        f"\nSignificant ACF lags for absolute returns "
        f"(alpha={autocorr_abs_results['alpha']}): "
        f"{autocorr_abs_results['acf_significant_lags']}")
    print(
        f"Significant PACF lags for absolute returns "
        f"(alpha={autocorr_abs_results['alpha']}): "
        f"{autocorr_abs_results['pacf_significant_lags']}")


if __name__ == "__main__":
    main()
