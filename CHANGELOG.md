# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Time-series (trend-following) momentum** (`strategy/trend.py`):
  `TimeSeriesMomentum`, a cross-asset trend backtester distinct from the
  cross-sectional `MomentumStrategy` — each asset is positioned on the sign of
  its *own* trailing return, with inverse-volatility sizing (`scale`, which also
  isolates the signal from the vol-timing effect) and long/short or long-or-flat
  modes. Returns a per-period series plus a weights panel that feeds the existing
  `performance`/cost helpers. Plus `trend_signal_table`.
- **Per-asset trend speeds.** `lookback` now accepts a dict (asset → periods) as
  well as an int, because the horizon over which trends persist is not the same
  across markets. `speed_group`, `TREND_SPEEDS` and `lookback_by_group` encode
  the grouping measured on 35 futures (1979–2026) and cross-checked on a 10-ETF
  basket: slow 18m for bonds and **precious** metals, mid 9m for equity indices
  and FX, fast 3m for energy, **industrial** metals and agriculture. The
  precious/industrial split inside "metals" is the load-bearing part — gold
  optimises at 12m against copper's 3m. Reversing the grouping halves the Sharpe,
  which is the evidence it is an ordering rather than a fit.
- **Mixed-frequency volatility** in `TimeSeriesMomentum.backtest`: optional
  `vol_returns` / `vol_periods_per_year` estimate risk on a higher-frequency
  panel (e.g. daily) while still rebalancing on the low-frequency clock, so
  sizing sharpens with no extra turnover. The alignment uses only observations
  dated on or before each formation date, regression-tested for look-ahead.
- **Portfolio volatility targeting** (`performance.volatility_target`): rescales
  a strategy to a constant ex-ante volatility using a lagged estimate and a
  leverage cap. Costs the *levered* weights, so the leverage trade itself is
  charged rather than ignored — the naive `net × leverage` misses it. Needed
  because weights of `sign × (target/vol) / n` make portfolio volatility fall as
  markets are added, which is a construction artifact rather than a property of
  the strategy.
- **Datastream futures loader** (`dataloader/ds_futures.py`): the 35-market
  cross-asset basket plus `resolve_series`, `fetch_series`, `clean_prices`,
  `mask_roll_returns`, `to_monthly` and `effective_breadth`. The module docstring
  records the three table facts that silently corrupt the data if ignored — the
  stacked-long `_name_` layout, the absence of back-adjustment (a directional
  −0.55%/roll on the Bund) and non-unique `dsmnem` with wildly varying coverage
  across roll variants. `examples/cache_futures_data_wrds.py` writes daily and
  monthly panels.
- **Trend demos**, one point each: `examples/trend_demo.py` (the construction and
  what each design choice is worth), `examples/trend_speed_demo.py` (why speeds
  differ by class, with the falsification test and a per-asset overfitting
  check), `examples/trend_portfolio_demo.py` (volatility targeting and marginal
  contribution to an equity portfolio, levered vs not).
- **PEAD event study** (`strategy/pead.py`): `standardized_unexpected_earnings`
  (seasonal-random-walk SUE), `analyst_sue` (IBES analyst SUE from the last
  pre-announcement consensus) and `event_car` (announcement- vs drift-window CARs
  with a market or characteristic-matched benchmark) — data-source-agnostic and
  unit-tested. Plus `examples/pead_event_study.py`,
  `examples/pead_analyst_study.py`, and `cache_pead_data_wrds.py` /
  `cache_ibes_data_wrds.py` to fetch inputs.
- **Research logs and background**: `docs/trend-research-log.md` (the speed
  grouping and its falsification, out-of-sample and walk-forward tests, cost and
  frequency sensitivity, and an explicit multiple-testing count),
  `docs/pead-research-log.md`, `docs/cta-primer.md` (how managed-futures funds
  actually implement this), and the two strategy surveys
  `docs/strategy-research.md` / `docs/strategy-research-2.md` that motivated the
  build.
- **Data-pull scripts**: `examples/cache_futures_data_wrds.py` (Datastream
  futures), `examples/cache_etf_data.py` (ETF basket from CRSP via WRDS) and
  `examples/cache_etf_data_av.py` (Alpha Vantage variant — monthly or weekly
  adjusted, resumes a partial run, retries through throttles — for networks
  where Yahoo Finance is unreachable).
- **`tools/`**: one-off WRDS exploration and diagnostics kept out of `examples/`
  — `select_ds_futures.py` (catalogue browser), `sample_ds_futures.py`
  (single-series dump for eyeballing rolls), `explore_wrds_futures.py` (library
  discovery) and `compare_ds_roll_methods.py`, which is the reproducible evidence
  for choosing the CS00 roll convention.

### Changed

- README documents `trend.py`, `pead.py`, the per-class speeds, volatility
  targeting and the research logs; the project-structure block was stale as of
  the PEAD commit.
- `AlphaVantageLoader.get_price` only passes `outputsize` to endpoints that
  accept it, so the `*_Adjusted` intervals (e.g. `"Monthly_Adjusted"`) work.

## [0.2.0] - 2026-07-21

> Script names below are as they were at release. Several were later renamed to
> the `cache_<what>_data_<source>.py` convention: `cache_wrds_data.py` →
> `cache_sp500_mr_data_wrds.py`, `cache_global_momentum.py` →
> `cache_global_momentum_data_wrds.py`, `cache_pead_data.py` →
> `cache_pead_data_wrds.py`, `cache_ibes_data.py` → `cache_ibes_data_wrds.py`.

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
