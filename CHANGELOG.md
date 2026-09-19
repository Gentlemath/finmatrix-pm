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
  optimises at 12m against copper's 3m. Reversing the grouping costs 31–49% of
  the Sharpe depending on dataset and window, which is the evidence it is an
  ordering rather than a fit. (An earlier version of this line said "halves",
  true only of v1's full sample.)
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
  `cache_ibes_analyst_EPS_data_wrds.py` to fetch inputs.
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
- **`tools/`**: WRDS exploration and diagnostics kept out of `examples/`.
  `survey_ds_classes.py` searches the CONTRACT table and so sees live classes
  that the series table hides; `find_ds_series_by_name.py` is its complement over
  continuous series. `check_listing.py` asks which exchange a market is and
  whether that listing trades; `rank_market_liquidity.py` ranks absolute volume
  and open interest. `build_contract_series.py`, `diagnose_contract_coverage.py`
  and `verify_basket_candidates.py` check a candidate before it enters the
  basket. `explore_wrds_futures.py` reports what a subscription covers, and
  `compare_ds_roll_methods.py` is the reproducible evidence for the CS00 roll
  convention.

- **Contract-level futures construction** (`dataloader/ds_contracts.py`) and the
  **v2 basket**: 50 markets across 7 classes from 1973-01, against v1's 35 across
  6 from 1979-01, with 23 series built from individual contracts rather than read
  from Datastream's continuous series. Effective breadth 9.1 against 8.0 and mean
  pairwise correlation *down* 0.24 → 0.23, so the additions diversify. Building
  was not optional: Datastream's continuous series no longer carry CME Group, and
  the live classes have no continuous series at all. `pick_held` chooses the
  contract by open interest inside a six-month window; `contract_returns` takes
  returns within one contract so the roll gap — term structure, not a return —
  never enters. `examples/cache_futures_data_v2_wrds.py` writes the panels and
  resumes per market. Two silent defects found on the way: missing `lasttrddate`
  truncated wheat and lean hogs by thirty years, and uncleaned prices left three
  ×10,000 spikes that put gasoline's annualised volatility at 8033%.
- **The speed grouping is data, not code.** `GROUPING_V1` and `GROUPING_V2` are
  dicts passed to `speed_group(..., grouping=)`, so a re-learned grouping and the
  reversed one used to falsify it are alternative *values* rather than branches.
  `GROUPING_V2` adds livestock (absent from v1) and moves platinum to slow.
- **A proper equity benchmark** (`examples/cache_equity_benchmark_wrds.py`):
  CRSP index returns joined to Fama-French, giving the US market excess return
  from 1926 where the SPY ETF began in 2006 and the S&P futures in 1982. The
  loader returns `(series, rf_annual)` so the cash convention travels with the
  series it belongs to.
- **Three studies**: `trend_grouping_study.py` (class portfolios with error
  bars), `trend_walkforward_study.py` (re-learn every window, trade the next,
  stitch the disjoint test blocks) and `trend_subset_test.py` (random subsets of
  v2 against v1). `docs/trend-research-log-v2.md` records the results.
- **`--dataset`, `--through` and `--start`** on every trend demo and study, so v1
  and v2 run through one code path — the only way to attribute a difference to
  the data rather than to a code change.

### Changed

- README documents `trend.py`, `pead.py`, the per-class speeds, volatility
  targeting and the research logs; the project-structure block was stale as of
  the PEAD commit.
- `AlphaVantageLoader.get_price` only passes `outputsize` to endpoints that
  accept it, so the `*_Adjusted` intervals (e.g. `"Monthly_Adjusted"`) work.

### Fixed

- **The equity benchmark had cash subtracted twice.** `trend_portfolio_demo.py`
  removed a flat 1.8%/yr from whatever benchmark it was given, correct for the
  SPY ETF (a total return) and wrong for the S&P *futures* series, which is
  already an excess return. It understated the equity Sharpe by 0.11 with no
  visible symptom. The risk-free rate is now a property of the series.
- **Its two comparison blocks sat on different periods.** Each dropped months
  where its own trend leg was missing, and the vol-targeted leg starts a year
  later, so the "100% equity" row — which contains no trend leg at all — read
  0.56 in one block and 0.57 in the other. Both now share one window.
- **`trend_speed_demo.py` narrated a run it had not done**, asserting that
  reversal halves the Sharpe and worsens drawdown. "Halves" held only on v1's
  full sample (−49%); elsewhere the cost is 31–36%. "Worsens drawdown" holds on
  v2 (−4.4% → −7.7%) but fails on v1, where reversal *improves* it (−9.1% →
  −6.0%) — the direction is not stable, so the text no longer asserts one. It is
  computed from the run in front of it, and says plainly when the grouping fails
  to beat uniform 12m, which on the 50-market basket it does.

## [0.2.0] - 2026-07-21

> Script names below are as they were at release. Several were later renamed to
> the `cache_<what>_data_<source>.py` convention: `cache_wrds_data.py` →
> `cache_sp500_mr_data_wrds.py`, `cache_global_momentum.py` →
> `cache_global_momentum_data_wrds.py`, `cache_pead_data.py` →
> `cache_pead_data_wrds.py`, `cache_ibes_data.py` → `cache_ibes_data_wrds.py`.
> Renamed again later: `cache_ibes_data_wrds.py` →
> `cache_ibes_analyst_EPS_data_wrds.py`, and `cache_sp500_mr_data_wrds.py` →
> `cache_sp500constituents_mr_data_wrds.py`.

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
