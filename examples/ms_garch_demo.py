"""Compare standard GARCH and Markov-switching GARCH on S&P 500 returns."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

# Ensure src is on the import path when running from the repository root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tsm import GARCHPredictor, MarkovSwitchingGARCHPredictor


def load_returns(start: str = "2020-01-01", end: str = "2026-05-12") -> pd.Series:
    """Load daily S&P 500 percentage returns."""
    prices = yf.download("^GSPC", start=start, end=end, progress=False)[["Close"]]
    prices = prices.rename(columns={"Close": "SP500"})
    return prices["SP500"].pct_change().dropna() * 100


def fit_full_sample_models(returns: pd.Series) -> tuple[GARCHPredictor, MarkovSwitchingGARCHPredictor]:
    """Fit both models on the full sample."""
    garch = GARCHPredictor(p=1, q=1, mean_model="Constant")
    ms_garch = MarkovSwitchingGARCHPredictor(
        k_regimes=2,
        garch_order=(1, 1),
        mean_model="Constant",
        min_regime_observations=60,
    )

    print("\n=== Full-sample fit ===")
    garch_summary = garch.fit(returns)
    ms_summary = ms_garch.fit(returns)

    print(f"GARCH AIC: {garch_summary['aic']:.2f}")
    print(f"Markov regime-model AIC: {ms_summary['aic']:.2f}")
    print("Note: these AIC values come from different likelihoods and are not directly comparable.")
    print("\nEstimated transition matrix:")
    print(ms_garch.get_transition_matrix().round(4))

    return garch, ms_garch


def walk_forward_comparison(
    returns: pd.Series,
    evaluation_points: int = 12,
    training_window: int = 750,
    step: int = 5,
) -> pd.DataFrame:
    """
    Run a light walk-forward comparison on recent holdout dates.

    Absolute next-day return is used as a simple realized-volatility proxy. This
    keeps the demo readable; production evaluation should use a richer setup.
    """
    rows = []
    end_positions = range(
        len(returns) - evaluation_points * step - 1,
        len(returns) - 1,
        step,
    )

    print("\n=== Walk-forward comparison ===")
    for end_pos in end_positions:
        train = returns.iloc[max(0, end_pos - training_window):end_pos]
        target_date = returns.index[end_pos]
        realized_volatility = abs(float(returns.iloc[end_pos]))

        garch = GARCHPredictor(p=1, q=1, mean_model="Constant")
        ms_garch = MarkovSwitchingGARCHPredictor(
            k_regimes=2,
            garch_order=(1, 1),
            mean_model="Constant",
            min_regime_observations=60,
        )

        garch.fit(train)
        ms_garch.fit(train)

        rows.append(
            {
                "date": target_date,
                "realized_volatility": realized_volatility,
                "garch_forecast": float(garch.predict_return()["predicted_volatility"]),
                "ms_garch_forecast": float(ms_garch.predict_return()["predicted_volatility"]),
            }
        )

    results = pd.DataFrame(rows).set_index("date")
    results["garch_abs_error"] = (results["garch_forecast"] - results["realized_volatility"]).abs()
    results["ms_garch_abs_error"] = (results["ms_garch_forecast"] - results["realized_volatility"]).abs()
    results["garch_sq_error"] = (results["garch_forecast"] - results["realized_volatility"]) ** 2
    results["ms_garch_sq_error"] = (results["ms_garch_forecast"] - results["realized_volatility"]) ** 2

    print(results[["realized_volatility", "garch_forecast", "ms_garch_forecast"]].round(4))
    print("\nMean absolute error:")
    print(
        pd.Series(
            {
                "GARCH": results["garch_abs_error"].mean(),
                "MS-GARCH": results["ms_garch_abs_error"].mean(),
            }
        ).round(4)
    )
    print("\nRoot mean squared error:")
    print(
        pd.Series(
            {
                "GARCH": np.sqrt(results["garch_sq_error"].mean()),
                "MS-GARCH": np.sqrt(results["ms_garch_sq_error"].mean()),
            }
        ).round(4)
    )

    return results


def plot_results(
    returns: pd.Series,
    ms_garch: MarkovSwitchingGARCHPredictor,
    walk_forward_results: pd.DataFrame,
) -> None:
    """Plot regime probabilities and the holdout volatility comparison."""
    probabilities = ms_garch.get_regime_probabilities()

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)

    axes[0].plot(returns.index, returns.values, color="steelblue", linewidth=0.9)
    axes[0].set_title("S&P 500 Daily Returns")
    axes[0].set_ylabel("Return (%)")
    axes[0].grid(True, alpha=0.3)

    probabilities.plot(ax=axes[1], linewidth=1.2)
    axes[1].set_title("Smoothed Regime Probabilities")
    axes[1].set_ylabel("Probability")
    axes[1].set_ylim(0, 1)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(
        walk_forward_results.index,
        walk_forward_results["realized_volatility"],
        marker="o",
        label="Realized |return|",
    )
    axes[2].plot(
        walk_forward_results.index,
        walk_forward_results["garch_forecast"],
        marker="o",
        label="GARCH forecast",
    )
    axes[2].plot(
        walk_forward_results.index,
        walk_forward_results["ms_garch_forecast"],
        marker="o",
        label="MS-GARCH forecast",
    )
    axes[2].set_title("Recent Holdout Volatility Forecasts")
    axes[2].set_ylabel("Volatility")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    plt.tight_layout()
    plt.show()


def main() -> None:
    returns = load_returns()
    print(f"Loaded {len(returns)} daily returns from {returns.index.min().date()} to {returns.index.max().date()}")

    _, ms_garch = fit_full_sample_models(returns)
    walk_forward_results = walk_forward_comparison(returns)

    print("\n=== Next-day forecasts from full sample ===")
    print("MS-GARCH zero-mean forecast:")
    print(ms_garch.predict_return(method="zero").round(4))
    print("\nMS-GARCH regime-weighted mean forecast:")
    print(ms_garch.predict_return(method="regime_weighted").round(4))

    plot_results(returns, ms_garch, walk_forward_results)


if __name__ == "__main__":
    main()
