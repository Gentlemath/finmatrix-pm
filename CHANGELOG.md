# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-21

### Added
- **Packaging**: `pyproject.toml` makes the toolkit pip-installable
  (`pip install -e .`) with optional extras (`us`, `china`, `wrds`, `dev`, `all`).
- **`.env` auto-loading** via `python-dotenv` (`portfolio_management.config.load_env`,
  run on import), so credentials (API keys, tokens, `WRDS_USERNAME`) can live in a
  project `.env`; real environment variables take precedence.
- **Test suite**: pytest unit tests under `tests/` — network-free, synthetic data,
  deterministic seeds. Config lives in `pyproject.toml`; flake8 config in `setup.cfg`.
- **Loader normalization layer** (`dataloader/base.py`): a `BaseLoader` interface with
  a common `get_prices()` returning a canonical price panel (DatetimeIndex × symbols),
  plus helpers `pivot_to_panel` and `flatten_yfinance`.
- **WRDS loader** (`WRDSLoader`, CIZ-native): CRSP CIZ stock data
  (`get_crsp_monthly` / `get_crsp_daily` on `crsp.msf_v2` / `dsf_v2`, delisting already
  in `mthret`), point-in-time S&P 500 membership (`get_sp500_constituents`) and the
  one-call `get_sp500_universe()` returning ready returns/membership/market-cap panels;
  Compustat (`get_compustat_annual` / `get_compustat_quarterly`), CRSP-Compustat link
  (`get_ccm_link`); raw escape hatches (`raw_sql`, `get_table`, `list_tables`,
  `describe_table`) for other libraries (IBES/TAQ). Registered as the `"wrds"` source.
- **Strategy module** (`strategy/`): `MomentumStrategy`, a configurable cross-sectional
  momentum backtester (`n_quantiles`, `long_short`, `weighting`, `lookback`/`gap`;
  monthly rebalance, optional `return_weights`); `build_membership` / `panels_from_crsp`
  for point-in-time universe panels.
- **Performance analytics** (`strategy/performance.py`): `performance_summary`
  (annualized return/vol, excess-return Sharpe, max drawdown), `capm`
  (beta/alpha/R²/tracking error/information ratio), `turnover`, `cap_weighted_return`,
  and proportional transaction costs (`transaction_costs` / `apply_costs`) for
  net-of-cost returns.
- **Ready-made momentum data (WRDS JKP Global Factor Data)**: the
  `contrib_global_factor.global_factor` table is a firm-month characteristics panel
  that provides momentum signals directly (`ret_12_1`, `ret_6_1`, …) plus the
  forward return (`ret_exc_lead1m`) and market cap — no need to compute the signal.
  `examples/cache_global_momentum.py` builds per-country momentum-decile returns
  from it (in-database ranking; ~90 markets available), and
  `examples/plot_global_momentum.py` renders the yearly cross-market figures.
- **Example scripts**: `examples/wrds_demo.py`, `examples/momentum_demo.py`,
  `examples/cache_wrds_data.py`, `examples/cache_global_momentum.py`,
  `examples/plot_global_momentum.py`.

### Changed
- Renamed the package directory `src/` → `portfolio_management/`; the import path is
  now `portfolio_management.<module>`.
- Consolidated pytest configuration into `pyproject.toml` and removed `sys.path`
  manipulation from tests and example scripts (the package is importable once installed).
- Updated CI to install the package editable (`pip install -e ".[us,dev]"`) and run
  against the new paths.
- Simplified the log-return computation in `PlotAnalyzer.compute_returns`.
- Ignored packaging/build artifacts (`*.egg-info/`, `build/`, `dist/`) in `.gitignore`.

### Removed
- `requirements.txt` — dependencies are now declared in `pyproject.toml`
  (`[project.dependencies]` plus the `us`/`china`/`wrds`/`dev`/`all` extras).

## [0.1.0] - 2026-05-18

### Added
- **Data loading**: `create_data_loader()` factory over CSV, yfinance, Alpha Vantage,
  FRED, AKShare, BaoStock, and Tushare, with API keys read from environment variables.
- **Exploratory Data Analysis** (`eda/`): `PlotAnalyzer` (price/return/cumulative plots),
  `DistributionAnalyzer` (summary stats, VaR, CVaR, Q-Q plots), and `TimeSeriesAnalyzer`
  (ADF/KPSS stationarity, ACF/PACF significance testing).
- **Time Series Modeling** (`tsm/`): `GARCHPredictor`, `ARIMAGARCHPredictor`
  (AR-mean + GARCH), `MarkovSwitchingGARCHPredictor`, and a rule-based `RegimeDetector`.
- **Example scripts**: `examples/eda_demo.py`, `garch_demo.py`, `ms_garch_demo.py`,
  and `regime_change_demo.py`.
- **Infrastructure**: GitHub Actions CI (Python 3.9–3.11) and a comprehensive README.
