"""Example GARCH modeling script for volatility prediction."""

import matplotlib.pyplot as plt
import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.tsm import ARIMAGARCHPredictor, GARCHPredictor


def main() -> None:
    # Load S&P 500 data through the yfinance data loader
    print("Loading S&P 500 data...")
    loader = create_data_loader("yfinance")
    prices = loader.get_prices("^GSPC", start="2020-01-01", end="2026-05-12")
    prices.columns = ["SP500"]  # canonical panel: one column per symbol

    # Calculate returns
    returns = (prices.pct_change().dropna() * 100)  # Convert to percentage

    print(f"Loaded {len(returns)} daily returns")
    print(f"Sample returns: {returns.head()}")

    # Fit GARCH(1,1) model
    print("\nFitting GARCH(1,1) model...")
    garch = GARCHPredictor(p=1, q=1, mean_model='Constant')
    garch_summary = garch.fit(returns['SP500'])

    print("GARCH Model Summary:")
    print(f"AIC: {garch_summary['aic']:.2f}")
    print(f"BIC: {garch_summary['bic']:.2f}")
    print(f"Log Likelihood: {garch_summary['log_likelihood']:.2f}")
    print(f"Convergence: {'Yes' if garch_summary['convergence'] == 0 else 'No'}")

    # Fit ARIMA-GARCH model
    print("\nFitting ARIMA-GARCH model...")
    arima_garch = ARIMAGARCHPredictor(arima_order=(1, 0, 1), garch_order=(1, 1))
    arima_garch_summary = arima_garch.fit(returns['SP500'])

    print("ARIMA-GARCH Model Summary:")
    print(f"AIC: {arima_garch_summary['aic']:.2f}")
    print(f"BIC: {arima_garch_summary['bic']:.2f}")
    print(f"Log Likelihood: {arima_garch_summary['log_likelihood']:.2f}")

    # Get model parameters
    params = garch.get_parameters()
    print("\nGARCH Parameters:")
    print(params)

    params_arima_garch = arima_garch.get_parameters()
    print("\nARIMA-GARCH Parameters:")
    print(params_arima_garch)

    # Predict next day volatility and return
    print("\nPredicting next day...")
    garch_prediction = garch.predict_return(horizon=1, method='historical')
    arima_garch_prediction = arima_garch.predict_return(horizon=1)

    comparison = pd.DataFrame(
        {
            "GARCH": garch_prediction,
            "ARIMA-GARCH": arima_garch_prediction,
        }
    )
    print(comparison.round(4))

    # Evaluate model
    evaluation = garch.evaluate_model()
    print("GARCH Evaluation:")
    print(f"Standardized Residuals Mean: {evaluation['std_resid_mean']:.4f}")
    print(f"Standardized Residuals Std: {evaluation['std_resid_std']:.4f}")
    print(f"Standardized Residuals Skew: {evaluation['std_resid_skew']:.4f}")
    print(f"Standardized Residuals Kurtosis: {evaluation['std_resid_kurtosis']:.4f}")
    if evaluation['ljung_box_pvalue'] is not None:
        print(
            f"Ljung-Box p-value (autocorrelation in squared residuals): "
            f"{evaluation['ljung_box_pvalue']:.4f}")

    evaluation_arima_garch = arima_garch.evaluate_model()
    print("\nARIMA-GARCH Evaluation:")
    print(f"Standardized Residuals Mean: {evaluation_arima_garch['std_resid_mean']:.4f}")
    print(f"Standardized Residuals Std: {evaluation_arima_garch['std_resid_std']:.4f}")
    print(f"Standardized Residuals Skew: {evaluation_arima_garch['std_resid_skew']:.4f}")
    print(f"Standardized Residuals Kurtosis: {evaluation_arima_garch['std_resid_kurtosis']:.4f}")
    if evaluation_arima_garch['ljung_box_pvalue'] is not None:
        print(
            f"Ljung-Box p-value (autocorrelation in squared residuals): "
            f"{evaluation_arima_garch['ljung_box_pvalue']:.4f}")

    # Plot conditional volatility comparison
    print("\nPlotting conditional volatility comparison...")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        garch.conditional_volatility.index,
        garch.conditional_volatility.values,
        label="GARCH",
        linewidth=1.5,
    )
    ax.plot(
        arima_garch.fitted_model.conditional_volatility.index,
        arima_garch.fitted_model.conditional_volatility.values,
        label="ARIMA-GARCH",
        linewidth=1.5,
    )
    ax.set_title("Conditional Volatility Comparison")
    ax.set_xlabel("Date")
    ax.set_ylabel("Volatility")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
