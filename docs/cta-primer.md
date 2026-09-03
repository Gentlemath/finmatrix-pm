# Managed futures / CTA primer

Background reading for the next project. Written against what we have already
**measured** in [`trend-research-log.md`](trend-research-log.md), so every claim
here can be checked against a number we produced ourselves.

**CTA** = *Commodity Trading Advisor*. A regulatory term (registration with the
US Commodity Futures Trading Commission and National Futures Association), but in
practice it means a **managed futures fund**, and the overwhelming majority of
CTA assets run **trend-following on futures**. So yes — trend + futures *is* the
industry. What you built is a small, honest version of the core CTA strategy.

## 1. Why futures rather than ETFs

Our ETF study measured its own limits, and futures fix all four:

| Constraint we measured | ETF basket | Futures |
|---|---|---|
| History | 20.5 years (DBC 2006, UUP 2007) | 1980s or earlier |
| Effective breadth | **3.4** (10 assets, mean \|corr\| 0.39) | 50–300 markets |
| Shorting | Possible but needs borrow | Symmetric and free — a short is just a negative position |
| Capital efficiency | Full notional | Margin is a few % of notional |

Two more that do not show up as a number:

- **Cost.** Futures are among the cheapest instruments in the world to trade.
  Our 10 bps/side assumption is roughly right for liquid ETFs and *pessimistic*
  for futures like the S&P 500 E-mini or the Bund.
- **No dividend-adjustment ambiguity.** A futures price is a price. The whole
  mess we hit with Alpha Vantage vs AKShare adjustment factors simply disappears.

The catch is the one we are about to hit: **futures expire**, so a continuous
price series has to be manufactured. See §3.

## 2. What the industry actually earns

Public benchmarks (SG Trend Index, SG CTA Index, BTOP50) tell a consistent story:

| Year | SG Trend / CTA | What happened |
|---|---|---|
| 2022 | **+27.3%** (record; Sharpe > 1) | Stocks *and* bonds trended down all year |
| 2023 | −3.3% | Reversals, no persistent trend |
| 2024 | +2.4% (SG CTA) | Roughly flat |
| 2011–2019 | Broadly **sideways** | The drought — see §6 |

This is the honest frame for our own **0.55 Sharpe / 2.7% a year**: it is *in the
right neighbourhood*. It also matches the "live CTA net Sharpe ~0.3–0.7 post-2009"
figure in [`strategy-research-2.md`](strategy-research-2.md) §2.1. Nobody in this
business earns the Sharpe > 1 that appears in the original in-sample papers.

One striking 2024 statistic: the average pairwise correlation between SG Trend
constituents was **0.78**, yet the range of their returns was nearly **15
percentage points**. Managers all run the same idea and still land far apart —
implementation detail (roll timing, horizon mix, risk model) accounts for a large
share of realised performance. That is encouraging for a learner: the edge is not
one secret signal, it is engineering.

## 3. The continuous-contract problem (the first thing to get right)

Futures expire, so a decades-long price series is **stitched** from many
contracts. How you stitch changes the data, and there is no neutral choice.

**Why it matters.** At each roll the expiring and next contract trade at
different prices (carry, storage, seasonality). Naively concatenating them puts
an artificial jump in the series. Roll four times a year for twenty years and you
have injected **80 fake price shocks** — which a trend signal will happily read
as real, and a return series will report as real profit or loss.

Three standard methods:

| Method | What it does | Trade-off |
|---|---|---|
| **Panama / back-adjustment** | Shift all history by a constant at each roll | Continuous returns, but **cumulative drift**; prices can go negative far back |
| **Proportional / ratio** | Scale history by a multiplicative factor | No absolute-price bias, but historical prices are no longer real prices |
| **Perpetual / blended** | Weighted blend of two nearby contracts | Smooth, but corresponds to no tradeable position |

For a trend backtest the practical rule: **compute returns within a contract, and
never across a roll.** Whatever series you use, the return on roll day must come
from one contract, not from the price difference between two.

**This is exactly what we must verify in `tr_ds_fut`.** Datastream's
`rollmethoddesc` says "switch over when…", which describes *when* it changes
contract, not whether it *adjusts* for the gap. The `cmonth` column in
`wrds_fut_series` identifies which contract is live, so we can detect roll dates
and check for a jump. Do not assume; measure.

## 4. What a real CTA does that our code does not

| Stage | Our `TimeSeriesMomentum` | Industry practice |
|---|---|---|
| Universe | 10 ETFs, effective breadth 3.4 | 50–300 futures across 5+ asset classes |
| Signal | One 12-month lookback | **Several horizons blended** — fast (~1 month), medium (~3), slow (~12) |
| Signal shape | `sign()`, ±1 | Often continuous, capped (e.g. `tanh` of a z-score) |
| Sizing | Inverse ex-ante vol per asset ✓ | Same — we got this right |
| Portfolio risk | **None** — book vol is whatever it is | **Target portfolio volatility** (e.g. 10%/yr), rescaled continuously |
| Correlation | Ignored | Risk allocated so correlated markets do not double-count |
| Rebalance | Monthly | Daily, with trade buffering to suppress churn |
| Costs | Flat 10 bps | Per-market, with slippage and market impact modelled |
| Capacity | N/A | A binding constraint at scale |

The two biggest gaps, in order of expected value:

**(a) Portfolio-level volatility targeting.** We scale *each asset* to
`target_vol`, then average. But the book's realised volatility drifts with the
correlations between positions — when trend puts everything on the same side,
risk quietly doubles. A CTA rescales the whole book to a constant target. This is
the single most standard thing we are missing.

**(b) Multiple signal horizons.** One 12-month lookback is one bet on one
frequency. Blending fast/medium/slow diversifies across horizons and is a large
part of why CTA returns are steadier than any single-horizon backtest.

Note what we did *not* get wrong: inverse-volatility sizing, no look-ahead in
signal alignment, ragged-panel handling, and net-of-cost accounting are all
already right.

## 5. Crisis alpha — and why 2020 broke it

The selling point is crisis alpha: positive returns *during* equity drawdowns.
Our own results show both the promise and the limit:

| | SPY | our L/S trend |
|---|---|---|
| 2008 | −36.8% | **+7.6%** |
| 2022 | −18.2% | **+9.0%** |
| **2020** | +18.4% (full year) | **−2.2%** |
| Worst 10% of SPY months | −8.01% | **+0.69%** |

2008 and 2022 were **slow** dislocations — months of persistent decline, which a
trend system detects, flips short into, and rides. 2020 was **fast**: the COVID
crash and its recovery both happened inside a few weeks. A 12-month signal cannot
turn that quickly, so the strategy got whipsawed.

**So crisis alpha is conditional on crisis speed**, not a general hedge. This
matches [`strategy-research-2.md`](strategy-research-2.md) §2.4 and is one of the
few places our small study reproduces a documented industry result exactly. The
academic literature is notably thinner on this claim than the marketing is.

## 6. Where trend fails: the drought

CTA indices went broadly **sideways from 2011 to 2019** while equities compounded
double digits. Range-bound markets generate false signals and whipsaw losses;
trend needs sustained direction to pay.

This is the real risk of the strategy, and it is not drawdown risk — it is
**patience risk**. Using the arithmetic from `strategy-research.md`: at Sharpe
0.5, about 21.5% of arbitrary 30-month windows end below cash; at Sharpe 0.3,
about 32%. Roughly one three-year stretch in three is a losing one. Investors who
capitulate in year seven of a drought are why the premium survives to be earned
by those who do not.

## 7. Suggested roadmap for the new project

Ordered by expected value, not by ease:

1. **Get the continuous series right.** Verify roll handling on `tr_ds_fut`
   before anything else. A silent roll bug invalidates every number downstream,
   and it will not announce itself.
2. **Build breadth.** Target 30–50 markets across equity index, bonds/rates, FX,
   energy, metals, agriculture. Going from effective breadth 3.4 to ~15 matters
   far more than any signal refinement.
3. **Extend the span.** Futures reach back to the 1980s. At Sharpe 0.46, 20.5
   years gives t = 2.02; 40 years gives t ≈ 2.9. This is the only way to make the
   result statistically firm — `SE(Sharpe) ≈ 1/√years`, with no frequency term.
4. **Add portfolio-level volatility targeting.** The biggest structural gap.
5. **Blend signal horizons.** Fast/medium/slow rather than one 12-month lookback.
6. **Benchmark against reality.** WRDS carries `cisdm` (CISDM managed futures)
   and `hfr` — actual CTA fund returns. Comparing our backtest to live CTA
   performance is a genuine external check, not another in-sample statistic.
7. **Only then** tune parameters. Everything above changes the answer more than
   parameter choice does, and tuning first invites overfitting to a 20-year sample.

## 8. Things to stay honest about

- **`SE(Sharpe) ≈ 1/√years`.** Twenty years cannot establish a Sharpe of 0.5 with
  confidence, no matter how the data is sliced or how finely it is sampled.
- **Multiple testing.** We ran ~30 PEAD tests and found 3 with |t| > 2 — about
  what chance predicts. Trend has just as many knobs (lookback, vol window, roll
  rule, horizon mix, target vol). Decide what to test *before* testing it.
- **In-sample Sharpes are gross and optimistic.** MOP reported > 1 for 1985–2009;
  live net has been 0.3–0.7. Assume decay.
- **Costs are not a detail.** At 2–3%/yr gross, execution assumptions decide
  whether the strategy exists.

## References

- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, JFE — the canonical study.
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing*.
- Kim, Tse & Wald, *Time Series Momentum and Volatility Scaling* — the vol-timing critique.
- Huang, Li, Wang & Zhou (2020), *Time Series Momentum: Is It There?*, JFE — the power critique.
- [Graham Capital, *Trend-Following Primer*](https://www.grahamcapital.com/blog/trend-following-primer/)
- [Man Group, *Trend Following: Equity and Bond Crisis Alpha*](https://www.man.com/insights/trend-following-equity-and-bond-crisis-alpha)
- [CFM, *Steady Trends: The Reality of CTA Return Dispersion*](https://www.cfm.com/steady-trends-the-reality-of-cta-return-dispersion/)
- [SG Prime Services Indices](https://wholesale.banking.societegenerale.com/en/prime-services-indices/)
- [QuantStart, *Continuous Futures Contracts for Backtesting*](https://www.quantstart.com/articles/Continuous-Futures-Contracts-for-Backtesting-Purposes/)
- [QuantPedia, *Continuous Futures Contracts Methodology*](https://quantpedia.com/continuous-futures-contracts-methodology-for-backtesting/)
- *The crisis alpha of managed futures: Myth or reality?* (IRFA 2022)
- Our own: [`trend-research-log.md`](trend-research-log.md), [`strategy-research-2.md`](strategy-research-2.md) §2.1 and §2.4.
