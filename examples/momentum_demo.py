"""Survivorship-bias-free S&P 500 momentum backtest using WRDS/CRSP.

Run in YOUR terminal (needs your WRDS account + network):

    python examples/momentum_demo.py

Why WRDS instead of yfinance: yfinance only knows *today's* index members and
drops delisted stocks entirely, which biases a momentum backtest upward. CRSP
(CIZ) provides point-in-time S&P 500 membership (crsp.msp500list_v2) and returns
that already include the delisting return (crsp.msf_v2), so the universe at each
date is the real one. get_sp500_universe() assembles the panels in one call.

The scorecard compares the strategy to a cap-weighted S&P 500 benchmark, uses
EXCESS returns for the long-only Sharpe (risk-free from FRED if available), and
reports turnover -- so beta isn't mistaken for alpha.
"""

import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.strategy import (
    MomentumStrategy,
    apply_costs,
    cap_weighted_return,
    capm,
    performance_summary,
    turnover,
)

START = "2010-01-01"
END = "2025-12-31"


def risk_free_monthly(index) -> pd.Series:
    """Monthly risk-free rate from FRED 3-month T-bill (0.0 if unavailable)."""
    try:
        fred = create_data_loader("fred")
        tb = fred.get_series("TB3MS", start_date=str(index.min().date()))  # annual %, monthly
        tb.index = pd.to_datetime(tb.index)
        monthly = (tb / 100.0) / 12.0
        return monthly.reindex(index, method="ffill").fillna(0.0)
    except Exception as exc:
        print(f"  (risk-free unavailable: {type(exc).__name__}; using rf=0)")
        return pd.Series(0.0, index=index)


def _print(label, stats):
    print(f"\n{label}")
    for key, value in stats.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")


def main() -> None:
    loader = create_data_loader("wrds")
    try:
        print("Loading S&P 500 universe (CIZ: msp500list_v2 + msf_v2)...")
        returns, membership, caps = loader.get_sp500_universe(start=START, end=END)
        print(f"  {returns.shape[1]} securities, {len(returns)} months")

        # Configurable: n_quantiles (10=deciles, 5=quintiles), long_short, weighting.
        strat = MomentumStrategy(
            lookback=11, gap=1, n_quantiles=10, long_short=True, weighting="value"
        )
        result, weights = strat.backtest(
            returns, membership=membership, market_caps=caps, return_weights=True
        )
        strat_ret = result["strategy"]
        benchmark = cap_weighted_return(returns, caps, membership)  # cap-weighted S&P 500

        # Long-short is self-financing (rf=0); a long-only book needs the real rf.
        rf = pd.Series(0.0, index=strat_ret.index) if strat.long_short \
            else risk_free_monthly(strat_ret.index)

        weighting = "value-weighted" if strat.weighting == "value" else "equal-weighted"
        mode = "long-short" if strat.long_short else "long-only top decile"
        print(f"\n=== Momentum backtest ({weighting} {mode}) ===")
        print(result.tail())

        _print("Strategy (gross):", performance_summary(strat_ret, rf=rf))
        _print("Benchmark (cap-weighted S&P 500):", performance_summary(benchmark))
        _print("Strategy vs benchmark (CAPM):", capm(strat_ret, benchmark, rf=rf))
        _print("Turnover:", turnover(weights))

        # Net of transaction costs -- decisive for a high-turnover strategy.
        print("\n=== Net of transaction costs (per-side bps) ===")
        for bps in (0, 5, 10, 20):
            net = apply_costs(strat_ret, weights, cost=bps / 10000.0)
            stats = performance_summary(net, rf=rf)
            print(f"  {bps:>3} bps: ann_return {stats['ann_return']:+.4f}  "
                  f"sharpe {stats['sharpe']:.3f}  cumulative {stats['cumulative']:+.4f}")
    finally:
        loader.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()
