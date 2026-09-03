# Portfolio Management

A comprehensive portfolio management system for financial data exploration, analysis, and modeling. Built for learning and practical development in quantitative finance.

## Project Structure

```
portfolio_management/          # The installable Python package (import name)
  ├── __init__.py              # Exports; loads a local .env on import
  ├── config.py                # .env loading (python-dotenv)
  ├── dataloader/              # Data loading from multiple sources
  │   ├── data_loader.py       # Loaders: yfinance, Alpha Vantage, FRED, AKShare, BaoStock, Tushare
  │   ├── wrds_loader.py       # WRDS / CRSP CIZ loader (CRSP, Compustat, CCM, S&P 500 universe)
  │   ├── base.py              # BaseLoader + canonical price-panel normalization
  │   └── __init__.py
  ├── eda/                     # Exploratory Data Analysis
  │   ├── plots.py             # Price, return, and cumulative return visualization
  │   ├── distribution.py      # Return distribution analysis (VaR, CVaR, Q-Q)
  │   └── tsa.py               # Stationarity (ADF/KPSS), ACF/PACF testing
  ├── tsm/                     # Time Series Modeling
  │   ├── prediction.py        # GARCH, AR-GARCH, and Markov-switching GARCH predictors
  │   └── regime_detector.py   # Rule-based volatility regime detection
  └── strategy/                # Portfolio strategies / backtesting
      ├── momentum.py          # Configurable cross-sectional momentum strategy
      ├── trend.py             # Time-series trend momentum; per-class speeds
      ├── pead.py              # Post-earnings-announcement drift event study
      ├── universe.py          # Point-in-time membership + panel builders
      └── performance.py       # Return stats, CAPM, turnover, costs, vol targeting
examples/                      # eda / garch / ms_garch / regime_change / wrds /
                               #   momentum / trend x3 / pead demos + cache_* pulls
tools/                         # one-off WRDS exploration and diagnostics
tests/                         # Unit tests (pytest; network-free, synthetic data)
docs/
  ├── momentum-research-log.md # Findings from the momentum backtests
  ├── trend-research-log.md    # Findings from the cross-asset trend backtests
  ├── cta-primer.md            # Managed-futures / CTA background for the next build
  ├── pead-research-log.md     # Findings from the PEAD event study
  ├── strategy-research.md     # Survey: which published edges survive net of costs
  └── strategy-research-2.md   # Survey: structural, cross-asset, vol, microstructure
local_data/                    # Local (gitignored) data — e.g. cached CRSP pulls
pyproject.toml                 # Packaging, dependencies/extras, pytest config
setup.cfg                      # flake8 configuration
CHANGELOG.md
.github/workflows/ci.yml       # GitHub Actions CI
```

## Getting Started

### Installation

Install the package in editable mode so `import portfolio_management` works from
anywhere in the environment:

```bash
pip install -e .            # core (data-analysis + modeling) dependencies
pip install -e ".[us]"      # add US data providers (yfinance, Alpha Vantage, FRED)
pip install -e ".[china]"   # add China data providers (AKShare, BaoStock, Tushare)
pip install -e ".[dev]"     # add test/lint tooling (pytest, flake8)
pip install -e ".[all]"     # everything
```

Data-provider SDKs are optional extras because the loaders import them lazily —
you only need the extras for the sources you actually use. The demos in
`examples/` use `[us]` (yfinance).

### Version Control

This project uses Git for version management:

```bash
git log          # View commit history
git status       # Check current status
git add .        # Stage changes
git commit -m "message"  # Commit changes
```

## Data Loading

### Supported Data Sources

- **yfinance** — Historical prices + basic fundamentals
- **Alpha Vantage** — Global equity prices, fundamentals, symbol search
- **FRED** — US macroeconomic indicators
- **AKShare** — China market data
- **BaoStock** — China A-share backup data
- **Tushare** — China equity fundamentals
- **WRDS** — Academic research data (CRSP, Compustat, CRSP-Compustat Merged; raw SQL for IBES/TAQ/etc.)

### Configuration

Set API keys for providers that require them:

```bash
export ALPHAVANTAGE_API_KEY="your_api_key"
export FRED_API_KEY="your_api_key"
export TUSHARE_TOKEN="your_token"
```

### Data Loader Examples

```python
from portfolio_management.dataloader import create_data_loader

# CSV data
csv_loader = create_data_loader("csv", data_dir="local_data")
df = csv_loader.load_csv("portfolio.csv")

# yfinance: price data
yf_loader = create_data_loader("yfinance")
prices = yf_loader.history("AAPL", start="2024-01-01", end="2025-01-01")
info = yf_loader.get_simple_fundamentals("AAPL")

# Alpha Vantage: global equities + fundamentals
av_loader = create_data_loader("alpha_vantage")
price_data = av_loader.get_price("MSFT", interval="Daily")
fundamentals = av_loader.get_fundamentals("MSFT")

# FRED: macroeconomic data
fred_loader = create_data_loader("fred")
gdp = fred_loader.get_series("GDP", start_date="2020-01-01")

# WRDS: academic research data (requires a WRDS account; pip install -e ".[wrds]")
# CRSP CIZ-native (crsp.msf_v2 / crsp.msp500list_v2); mthret includes delisting.
wrds_loader = create_data_loader("wrds")            # WRDS_USERNAME env or username=...
crsp = wrds_loader.get_crsp_monthly(permnos=[14593], start="2020-01-01", end="2020-12-31")
funda = wrds_loader.get_compustat_annual(tickers=["AAPL"])
ibes = wrds_loader.raw_sql("select * from ibes.detu_epsus limit 100")  # escape hatch
wrds_loader.close()
```

### Canonical price panel

Price-capable loaders (`yfinance` and `wrds`) share a `get_prices()` method that
returns a **canonical price panel** — a `DataFrame` indexed by date with one
column per symbol. This is the exact shape the EDA and TSM modules consume, so
data from different sources is interchangeable (yfinance returns adjusted close;
WRDS returns a split/dividend-adjusted total-return index):

```python
prices = create_data_loader("yfinance").get_prices(["AAPL", "MSFT"],
                                                    start="2024-01-01", end="2025-01-01")
returns = PlotAnalyzer.compute_returns(prices, method="log")   # plugs straight in
```

> **WRDS note:** the loader speaks the CRSP **CIZ** format natively (`crsp.msf_v2`,
> `crsp.msp500list_v2`); the legacy SIZ tables were frozen by CRSP in 2024. The
> CIZ monthly + membership schema was validated live; table/column names are
> editable via the `CIZ_*` constants, and every method has a `raw_sql()` fallback.

## Exploratory Data Analysis (EDA)

### Overview

The EDA module provides tools for initial data exploration and understanding of financial time series.

### EDA Components

**PlotAnalyzer**
- Price series visualization
- Return series visualization
- Cumulative return plotting
- Multi-asset overview plots with subplots

**DistributionAnalyzer**
- Return distribution statistics (mean, std, skew, kurtosis)
- Value at Risk (VaR) and Conditional VaR
- Return distribution histograms
- Q-Q plots for normality assessment

**TimeSeriesAnalyzer**
- Stationarity tests: ADF and KPSS
- Autocorrelation (ACF) and Partial Autocorrelation (PACF) plots
- Significance testing for autocorrelation at individual lags
- Warning handling for edge cases

### Running the EDA Demo

```bash
cd examples
python eda_demo.py
```

The demo performs:

1. **Data Loading**: Real S&P 500 price data (via yfinance)
2. **Price Overview**: Plots prices, returns, and cumulative returns
3. **Return Statistics**: Computes mean, volatility, skew, kurtosis
4. **Distribution Analysis**: Histograms and Q-Q plots
5. **Stationarity Testing**: ADF-KPSS tests with interpretation
6. **Autocorrelation Analysis**: ACF/PACF with significance testing at α=0.01


## Time Series Modeling (TSM)

### Overview

The TSM module provides advanced time series models for volatility and return prediction.

### TSM Components

**GARCHPredictor**
- Fit GARCH(p,q) models for volatility modeling
- Predict next-day volatility and returns
- Model evaluation with standardized residuals and Ljung-Box tests
- Conditional volatility plotting

**ARIMAGARCHPredictor**
- AR-mean + GARCH model for joint mean/volatility dynamics
- Note: this is an AR-GARCH model, not a full ARIMA(p, d, q)-GARCH — the mean
  equation has autoregressive terms but no moving-average innovation terms.
  See the class docstring for the exact fitted structure.

**MarkovSwitchingGARCHPredictor**
- Two-stage regime-aware volatility model
- Fits latent volatility regimes (statsmodels `MarkovRegression`), then a
  separate GARCH per regime
- Produces transition-probability-weighted volatility and return forecasts

**RegimeDetector** (`portfolio_management/tsm/regime_detector.py`)
- Rule-based (non-model) volatility-regime detector
- Rolling volatility vs. a baseline threshold, with run-length smoothing
- Flags regime-change points and plots detected regimes

### Running the TSM Demos

```bash
cd examples
python garch_demo.py          # GARCH / AR-GARCH
python ms_garch_demo.py       # standard vs. Markov-switching GARCH
python regime_change_demo.py  # rule-based regime detection
```

### Running the GARCH Demo

```bash
cd examples
python garch_demo.py
```

The demo performs:

1. **Data Loading**: S&P 500 price data (via yfinance)
2. **Return Calculation**: Daily percentage returns
3. **GARCH Fitting**: GARCH(1,1) model estimation
4. **Parameter Analysis**: Model coefficients and diagnostics
5. **Volatility Prediction**: Next-day volatility forecast
6. **Model Evaluation**: Residual analysis and goodness-of-fit tests
7. **Visualization**: Conditional volatility plot


## Key Insights from EDA

### Stationarity
- Financial log-returns are typically stationary but with time-varying properties
- Use ADF and KPSS tests to confirm
- Non-stationarity → difference the series or use I(1) models

### Autocorrelation
- Short-term AR patterns may indicate mean reversion or microstructure effects
- Lag significance depends on data frequency and sample size
- Use stricter critical values (α=0.01) to filter noise and multiple testing artifacts

### Distribution
- Financial returns typically exhibit fat tails and negative skew
- Normal distribution assumption often violated
- Q-Q plots reveal deviations from normality

## Development & Testing

### Run Tests

```bash
pytest tests/ --maxfail=1 --disable-warnings -q
```

### Code Quality

```bash
flake8 portfolio_management/ tests/ examples/
python -m py_compile portfolio_management/**/*.py
```

### CI/CD

Automated testing runs on:
- Python 3.9, 3.10, 3.11
- On push and pull requests to `main` and `develop` branches

See `.github/workflows/ci.yml` for details.

## Strategy / Backtesting

### MomentumStrategy

Cross-sectional momentum with a **survivorship-bias-free** universe when fed
CRSP data via WRDS. Everything is configurable:

- `n_quantiles` — 10 for deciles, 5 for quintiles
- `long_short` — `True` for long-winners/short-losers, `False` for long-only top bucket
- `weighting` — `"equal"` or `"value"` (market-cap)
- `lookback` / `gap` — signal window and skip month (default 11-month return, skip 1)

```python
from portfolio_management.dataloader import create_data_loader
from portfolio_management.strategy import MomentumStrategy

wrds = create_data_loader("wrds")
# One call: point-in-time membership + delisting-adjusted CIZ returns -> panels.
returns, membership, caps = wrds.get_sp500_universe(start="2005-01-01", end="2023-12-31")

strat = MomentumStrategy(n_quantiles=10, long_short=True, weighting="value")
result, weights = strat.backtest(returns, membership=membership,
                                 market_caps=caps, return_weights=True)
```

### TimeSeriesMomentum (trend-following)

Where `MomentumStrategy` ranks assets *against each other*, `TimeSeriesMomentum`
judges each asset **against its own past** — long if its own trailing return is
positive, short if negative. That absolute signal is why trend-following can be
long everything in a bull market and short everything in a crash, and it is the
canonical managed-futures construction (Moskowitz, Ooi & Pedersen 2012).

- `lookback` / `gap` — trailing signal window and skip (default 12 months, no skip)
- `scale` — `True` sizes positions by inverse ex-ante volatility to `target_vol`;
  `False` uses the bare sign, isolating the trend signal from the volatility-timing
  effect
- `long_short` — `False` gives long-or-flat (no shorts)
- `vol_window` / `target_vol` — ex-ante volatility estimate and per-asset risk target

```python
from portfolio_management.strategy import TimeSeriesMomentum

tsm = TimeSeriesMomentum(lookback=12, scale=True, long_short=True)
result, weights = tsm.backtest(returns, periods_per_year=12, return_weights=True)
```

The backtester rebuilds eligibility every date, so a **ragged panel is fine** — an
asset joins the book as soon as it has enough history, and the weights are
normalized over the assets actually available that period.

**Speed varies by asset class.** The horizon over which trends persist is not
the same across markets — measured on 35 futures (1979–2026) and cross-checked
on a 10-ETF basket, three groups fall out, and the grouping is *not* the obvious
financials-vs-commodities split:

| Group | Lookback | Markets |
|---|---|---|
| slow | 18m | bonds, **precious** metals |
| mid | 9m | equity indices, FX |
| fast | 3m | energy, **industrial** metals, agriculture |

```python
from portfolio_management.strategy import (
    TREND_SPEEDS, TimeSeriesMomentum, lookback_by_group, speed_group)

groups = {a: speed_group(a, asset_class[a]) for a in returns.columns}
lb = lookback_by_group(groups, TREND_SPEEDS)          # asset -> lookback
res, w = TimeSeriesMomentum(lookback=lb).backtest(returns, ...)
```

Gold optimises at 12m and copper at 3m, so the precious/industrial split inside
"metals" is the part that matters. Reversing the grouping halves the Sharpe,
which is the evidence that it is a real ordering rather than a fitted one.

**Portfolio volatility targeting.** Per-asset risk sizing leaves the book's own
volatility wherever the correlations put it, and `/n` means it *falls* as markets
are added. `volatility_target` rescales to a constant target using a lagged
estimate, charging the leverage trade:

```python
from portfolio_management.strategy import volatility_target

net, leverage, levered_weights = volatility_target(gross, w, target_vol=0.15)
```

**Mixed-frequency volatility.** The rebalance clock and the risk clock need not
match. A 36-month `vol_window` carries three-year-old information; pass a
higher-frequency panel to sharpen sizing without adding any turnover:

```python
res, w = TimeSeriesMomentum(lookback=12, vol_window=52).backtest(
    monthly_returns, periods_per_year=12,
    vol_returns=weekly_returns, vol_periods_per_year=52)   # trade monthly, size weekly
```

`vol_window` is then counted in periods of `vol_returns`. The alignment uses only
weekly observations dated on or before each monthly formation date, so it
introduces no look-ahead.

Data: `examples/cache_futures_data_wrds.py` builds the 35-market futures basket
(1979–2026, needs WRDS), or `examples/cache_etf_data_av.py [monthly|weekly]`
builds a 10-ETF proxy. Then three demos, each making one point:

```bash
python examples/trend_demo.py            # the construction, and what each choice is worth
python examples/trend_speed_demo.py      # why speed grouping matters + the falsification test
python examples/trend_portfolio_demo.py  # volatility targeting and marginal contribution
```

See
[`docs/trend-research-log.md`](docs/trend-research-log.md) for the results —
including why volatility frequency matters, and why long/short and long-or-flat
are different products rather than better and worse.

### PEAD event study

`strategy/pead.py` measures post-earnings-announcement drift in event time, and is
data-source agnostic like the rest of the toolkit:

- `standardized_unexpected_earnings` — seasonal-random-walk SUE from Compustat
- `analyst_sue` — IBES analyst SUE, (actual − consensus median) / dispersion, from
  the last pre-announcement consensus
- `event_car` — announcement- vs drift-window CARs, with either a market adjustment
  or a supplied `benchmark_col` for characteristic-matched abnormal returns

```python
from portfolio_management.strategy import (
    analyst_sue, event_car, standardized_unexpected_earnings)

sue = standardized_unexpected_earnings(earnings)          # or analyst_sue(actuals, consensus)
cars = event_car(daily, events, windows={"announce": (0, 1), "drift": (2, 63)})
```

See `examples/pead_event_study.py` and `examples/pead_analyst_study.py`, and
[`docs/pead-research-log.md`](docs/pead-research-log.md) for what the drift decay
actually looks like across eras.

### Performance analytics

`strategy/performance.py` scores a return series honestly — so market beta isn't
mistaken for alpha:

```python
from portfolio_management.strategy import (
    performance_summary, capm, turnover, cap_weighted_return)

benchmark = cap_weighted_return(returns, caps, membership)   # cap-weighted S&P 500
performance_summary(result["strategy"], rf=0.0)              # excess Sharpe, max drawdown
capm(result["strategy"], benchmark, rf=0.0)                  # beta, alpha, info ratio
turnover(weights)                                            # one-way turnover

from portfolio_management.strategy import apply_costs
net = apply_costs(result["strategy"], weights, cost=0.0010)  # subtract 10 bps/trade
performance_summary(net, rf=0.0)                             # net of transaction costs
```

For a high-turnover strategy, costs are decisive — `apply_costs` charges
`cost × Σ|Δw|` (dollars traded, both sides) at each rebalance, so you can sweep
cost levels and see where the edge disappears.

Use `rf=0` for a self-financing long-short book; pass a real risk-free rate for a
long-only book (otherwise its Sharpe is inflated by the risk-free rate).

**Why WRDS, not yfinance:** yfinance only knows *today's* index members and drops
delisted stocks, which biases momentum backtests upward. CRSP provides
point-in-time S&P 500 membership (`crsp.msp500list_v2`) and returns that already
include the delisting return (`crsp.msf_v2`), removing both leaks. The strategy
itself is data-source agnostic — it operates on panels, so it is fully
unit-tested on synthetic data.

For what the backtests reveal about momentum across eras (regime dependence, the
2009 crash, long-only ≈ market + a fading tilt, cost sensitivity), see
[`docs/momentum-research-log.md`](docs/momentum-research-log.md).

## Roadmap

The toolkit now spans **data → EDA → time-series modeling → strategy/backtesting**,
with a survivorship-bias-free WRDS/CRSP data path. Delivered so far: multi-source
data loading, EDA, GARCH-family + regime models, three strategy families
(cross-sectional momentum, cross-asset trend-following, PEAD event study), and
honest performance analytics (excess Sharpe, CAPM, turnover, transaction costs).

Candidate directions next:

- **Carry, cross-asset**: the other durable premium in `docs/strategy-research-2.md`
  (§2.2); equity dividend-yield carry is doable with current data
- **Portfolio optimization**: mean-variance, risk parity, allocation
- **A shared backtest engine**: `MomentumStrategy` and `TimeSeriesMomentum` already
  duplicate panel/eligibility/weighting logic worth factoring out
- **Momentum crash control**: Daniel–Moskowitz volatility-scaling (tames the 2009 −65% year)
- **Factor analysis**: PCA and factor models across multiple assets
- **Extended modeling / ML**: VAR, more regime variants, predictive models

Research logs record what the backtests actually taught us:
[`momentum`](docs/momentum-research-log.md),
[`trend`](docs/trend-research-log.md),
[`PEAD`](docs/pead-research-log.md).
The two survey documents ([`strategy-research.md`](docs/strategy-research.md),
[`strategy-research-2.md`](docs/strategy-research-2.md)) record which published
edges survive net of costs, and are what motivated the trend-following build.
[`cta-primer.md`](docs/cta-primer.md) covers how managed-futures funds actually
implement this — the continuous-contract problem, portfolio-level volatility
targeting, and where our version differs from industry practice.

## References

- [Statsmodels Time Series Documentation](https://www.statsmodels.org/stable/tsa.html)
- [yfinance Documentation](https://yfinance.readthedocs.io/)
- [Financial Time Series Analysis Best Practices](https://en.wikipedia.org/wiki/Time_series)
