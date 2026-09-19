# Portfolio Management

A quantitative research toolkit covering the whole path: **data → exploration →
time-series modeling → strategy → honest measurement.**

Three strategy families are implemented and documented — cross-sectional
momentum, post-earnings-announcement drift, and cross-asset trend-following.

The code is the smaller half of this repository. The larger half is
[`docs/`](docs/), where every result is recorded with its evidence, its error
bars, and what was retracted. A backtest number without those is not a finding.

## Quick start

```bash
pip install -e ".[us,dev]"
pytest                             # 198 tests, no network, synthetic data
python examples/eda_demo.py        # works with free data
```

Every module operates on plain pandas panels and is unit-tested on synthetic
data, so the code runs without any data subscription. The *research* behind it
mostly needs WRDS — see [Data](#data).

## Layout

```
portfolio_management/         the installable package
  dataloader/                 yfinance, Alpha Vantage, FRED, China, WRDS/CRSP
    ds_futures.py             Datastream continuous futures series
    ds_contracts.py           futures series built from individual contracts
  eda/                        distributions, stationarity, autocorrelation
  tsm/                        GARCH family and regime detection
  strategy/                   momentum, pead, trend, performance, universe
examples/                     demos, studies, and cache_* data pulls
tools/                        WRDS/Datastream discovery and diagnostics
tests/                        pytest, network-free
docs/                         research logs and surveys
local_data/                   licensed data — gitignored, never committed
```

Install extras for the sources you actually use; the loaders import them lazily.

```bash
pip install -e ".[us]"        # yfinance, Alpha Vantage, FRED
pip install -e ".[china]"     # AKShare, BaoStock, Tushare
pip install -e ".[wrds]"      # WRDS / CRSP
pip install -e ".[all]"
```

---

## Data

```python
from portfolio_management.dataloader import create_data_loader

yf = create_data_loader("yfinance")
prices = yf.get_prices(["SPY", "TLT"], start="2010-01-01")
```

Sources: **yfinance**, **Alpha Vantage**, **FRED**, **AKShare / BaoStock /
Tushare** (China), and **WRDS** (CRSP, Compustat, CCM, IBES, Datastream). All
normalise to the same canonical price panel.

```bash
export ALPHAVANTAGE_API_KEY="..."      # only for sources that need one
export FRED_API_KEY="..."
```

**Why WRDS rather than a free feed.** yfinance knows only *today's* index members
and drops delisted stocks, which biases any momentum backtest upward. CRSP gives
point-in-time S&P 500 membership (`crsp.msp500list_v2`) and returns that already
include the delisting return (`crsp.msf_v2`), removing both leaks at once.

WRDS data is licensed. The `cache_*.py` scripts in `examples/` pull it into
`local_data/`, which is gitignored and must stay that way — only aggregate
results are committed.

---

## Exploratory data analysis

```python
from portfolio_management.eda import (
    DistributionAnalyzer, PlotAnalyzer, TimeSeriesAnalyzer)
```

| class | what it answers |
|---|---|
| `PlotAnalyzer` | prices, returns, cumulative returns, multi-asset overviews |
| `DistributionAnalyzer` | mean, volatility, skew, kurtosis; VaR and CVaR; histograms and Q-Q plots |
| `TimeSeriesAnalyzer` | stationarity (ADF **and** KPSS), ACF/PACF with per-lag significance |

ADF and KPSS are run together on purpose: they test opposite null hypotheses, so
agreement is evidence and disagreement is a finding rather than a failure.

```bash
python examples/eda_demo.py
```

Loads real S&P 500 prices, plots the series, computes return statistics, tests
stationarity with an interpretation of the ADF/KPSS pair, and checks
autocorrelation at α = 0.01.

---

## Time-series modeling

```python
from portfolio_management.tsm import (
    ARIMAGARCHPredictor, GARCHPredictor,
    MarkovSwitchingGARCHPredictor, RegimeDetector)
```

| class | model |
|---|---|
| `GARCHPredictor` | GARCH(p,q) volatility, with standardised-residual and Ljung-Box diagnostics |
| `ARIMAGARCHPredictor` | AR-mean + GARCH. **Not** a full ARIMA(p,d,q)-GARCH — the mean equation has autoregressive terms but no moving-average innovations |
| `MarkovSwitchingGARCHPredictor` | latent volatility regimes (`MarkovRegression`), then a GARCH per regime, forecasts weighted by transition probability |
| `RegimeDetector` | rule-based, not a model: rolling volatility against a baseline with run-length smoothing |

```bash
python examples/garch_demo.py           # GARCH and AR-GARCH
python examples/ms_garch_demo.py        # standard vs Markov-switching
python examples/regime_change_demo.py   # rule-based regime detection
```

---

## Strategies

Three families, each with its own research log.

### 1. Cross-sectional momentum

Ranks assets **against each other** and holds winners against losers — always
both long and short, market-neutral by construction.

```python
from portfolio_management.strategy import MomentumStrategy

returns, membership, caps = wrds.get_sp500_universe(start="2005-01-01")
strat = MomentumStrategy(n_quantiles=10, long_short=True, weighting="value")
result, weights = strat.backtest(returns, membership=membership,
                                 market_caps=caps, return_weights=True)
```

`n_quantiles` (10 for deciles), `long_short`, `weighting` (`"equal"` or
`"value"`), `lookback`/`gap` (default 11-month return skipping the last month).
Survivorship-bias-free when fed CRSP data through `universe.py`.

→ [`momentum-research-log.md`](docs/momentum-research-log.md): regime dependence,
the 2009 crash, why long-only is roughly the market plus a fading tilt.

### 2. Post-earnings-announcement drift

Measures drift in **event time** around earnings announcements.

```python
from portfolio_management.strategy import (
    analyst_sue, event_car, standardized_unexpected_earnings)

sue  = standardized_unexpected_earnings(earnings)   # seasonal random walk
asue = analyst_sue(actuals, consensus)              # IBES, vs last pre-announcement consensus
cars = event_car(daily, events, windows={"announce": (0, 1), "drift": (2, 63)})
```

`event_car` takes either a market adjustment or a supplied `benchmark_col` for
characteristic-matched abnormal returns.

→ [`pead-research-log.md`](docs/pead-research-log.md): how the drift decays
across eras.

### 3. Trend-following

Judges each asset **against its own past** — long if its own trailing return is
positive, short if negative. That absolute signal is why trend-following can be
long everything in a bull market and short everything in a crash, and why it pays
in crises when a cross-sectional book cannot (Moskowitz, Ooi & Pedersen 2012).

```python
from portfolio_management.strategy import TimeSeriesMomentum

tsm = TimeSeriesMomentum(lookback=12, scale=True, long_short=True)
result, weights = tsm.backtest(returns, periods_per_year=12, return_weights=True)
```

`scale=True` sizes by inverse ex-ante volatility; `False` uses the bare sign,
isolating the trend signal from the volatility-timing effect. `long_short=False`
gives long-or-flat. Eligibility is rebuilt every date, so a **ragged panel is
fine** — an asset joins as soon as it has enough history.

`vol_returns` / `vol_periods_per_year` estimate risk on a higher-frequency panel
(daily) while still rebalancing monthly, so sizing sharpens with no extra
turnover. The alignment uses only observations dated on or before each formation
date, regression-tested for look-ahead.

#### Two futures datasets

| | v1 | v2 |
|---|---|---|
| markets | 35 across 6 classes | **50 across 7** |
| starts | 1979-01 | **1973-01** |
| built from | Datastream continuous series | 23 from individual contracts |
| effective breadth | 8.0 | **9.1** |

v2 exists because Datastream's continuous series no longer carry CME Group, and
the live CME classes have no continuous series at all — so half the basket had to
be rebuilt from contract-level data. `ds_contracts.py` picks the held contract by
open interest and takes returns *within* one contract, so the roll gap (term
structure, not a return) never enters.

Every trend demo and study takes `--dataset 1|2`, plus `--start` and `--through`:

```bash
python examples/trend_demo.py --dataset 2              # the construction
python examples/trend_speed_demo.py --dataset 2        # why speeds differ by class
python examples/trend_portfolio_demo.py --dataset 2    # sizing, and what it adds
```

Running both through one code path is the only way to attribute a difference to
the data rather than to a change in the code.

#### Speeds, and what the evidence supports

`lookback` accepts a dict (asset → months) as well as an int, because trends do
not persist over the same horizon everywhere: slow for bonds and precious metals,
mid for equities and FX, fast for energy, industrial metals and agriculture.

The grouping is **data, not code** — `GROUPING_V1` and `GROUPING_V2` are dicts
passed to `speed_group(..., grouping=)`, so a re-learned grouping and the
reversed one used to falsify it are alternative values rather than branches.

- **Reversing the grouping costs 31–49% of the Sharpe** across datasets and
  windows. Order carries information; a fitted pattern would not care which way
  round it went.
- **The grouping does not reliably beat a single 12-month lookback** — worth
  +0.19 on the 35-market basket, +0.01 on the 50-market one.
- **Learning it is worse than not learning it.** A walk-forward refitting every
  window scores below plain uniform 12m.

→ [`trend-research-log-v2.md`](docs/trend-research-log-v2.md) for v2 and
[`trend-research-log.md`](docs/trend-research-log.md) for v1, frozen and still
reproducible via `--dataset 1`.

---

## Measuring honestly

`strategy/performance.py` exists so market beta is not mistaken for alpha.

```python
from portfolio_management.strategy import (
    apply_costs, capm, performance_summary, turnover, volatility_target)

net = apply_costs(result["strategy"], weights, cost=0.0002)   # 2bp/side
performance_summary(net, periods_per_year=12)                 # Sharpe, max drawdown
capm(net, benchmark, periods_per_year=12)                     # beta, alpha, info ratio
turnover(weights)["annualized"]
```

Three conventions, because getting them wrong is silent:

- `apply_costs` charges `cost × Σ|Δw|` — dollars actually traded, both sides. For
  a high-turnover book this decides whether the edge exists at all.
- Use `rf=0` for a self-financing long/short book. A long-only book needs a real
  risk-free rate, or its Sharpe is inflated by cash it did earn.
- A **futures** series is already an excess return; an **ETF** total return is
  not. Subtracting cash from the first understates it.

`volatility_target` rescales to a constant ex-ante volatility using a lagged
estimate and a leverage cap, and costs the *levered* weights — the naive
`net × leverage` misses the leverage trade itself.

---

## Research logs

The logs are the deliverable. Each records what was tested, what survived, and
what was retracted.

| log | subject |
|---|---|
| [`trend-research-log-v2.md`](docs/trend-research-log-v2.md) | the 50-market basket: construction, two silent data defects, a liquidity and currency-access screen, the speed grouping with error bars |
| [`trend-research-log.md`](docs/trend-research-log.md) | the v1 basket, frozen |
| [`momentum-research-log.md`](docs/momentum-research-log.md) | regime dependence, the 2009 crash, cost sensitivity |
| [`pead-research-log.md`](docs/pead-research-log.md) | drift decay across eras |
| [`cta-primer.md`](docs/cta-primer.md) | how managed-futures funds implement this, and where this differs |
| [`strategy-research.md`](docs/strategy-research.md), [`-2`](docs/strategy-research-2.md) | which published edges survive net of costs; these motivated the trend build |

---

## Development

```bash
pytest                                     # 198 tests, network-free
flake8 portfolio_management examples tools tests
```

CI runs both on push ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Next

Carry, the other durable cross-asset premium
([`strategy-research-2.md`](docs/strategy-research-2.md) §2.2). Also open: a
shared backtest engine, since `MomentumStrategy` and `TimeSeriesMomentum`
duplicate panel and eligibility logic; portfolio optimisation; and momentum
crash control via Daniel–Moskowitz volatility scaling.
