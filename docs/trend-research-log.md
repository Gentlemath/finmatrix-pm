# Trend research log

Findings from backtesting `TimeSeriesMomentum` on two baskets: **35 cross-asset
futures, 1979–2026** (WRDS Datastream, the primary sample) and **10 liquid ETFs,
2006–2026** (the earlier, smaller sample). Only aggregate results are recorded
here; the underlying data is licensed and lives in the gitignored `local_data/`.

## Setup

| | Futures (primary) | ETFs (earlier) |
|---|---|---|
| Markets | 35 across 6 classes | 10 across 4 classes |
| Span | **572 months, 1979-01 → 2026-08** | 246 months, 2006-02 → 2026-07 |
| Effective breadth | **8.0** (mean \|corr\| 0.24) | 3.4 (mean \|corr\| 0.39) |
| Source | `tr_ds_fut` continuous series | Alpha Vantage adjusted |
| Currency | each contract's **local** currency | USD |

- **Signal**: sign of the trailing cumulative return; monthly rebalance, held one
  period. **Volatility** estimated on daily returns (126-day window).
- **Costs**: net throughout. Futures at **2 bps per side** (realistic for liquid
  contracts); ETFs at 10 bps. Cost sensitivity is reported below because it
  turned out to matter more than most parameters.
- **Reproduce**: `examples/cache_futures_data_wrds.py`, then the configurations
  below. Basket definition and all Datastream pitfalls live in
  `portfolio_management/dataloader/ds_futures.py`.

### Terms used throughout

**Gross vs net Sharpe.** Gross is computed before transaction costs — the raw
signal quality. Net subtracts `cost × Σ|w_t − w_{t−1}|` at each rebalance. The
gap is the cost drag and scales with turnover.

**Effective breadth.** How many genuinely independent bets a panel contains,
computed as `sum(λ)² / sum(λ²)` over the eigenvalues of the return correlation
matrix. Counting markets overstates diversification when ten of them are points
on two yield curves: the 35-futures basket has an effective breadth of 8.0, the
10-ETF basket 3.4. Implemented as `dataloader.ds_futures.effective_breadth`.

**Reversed configuration.** The falsification control. It swaps the *slow* and
*fast* speed assignments and leaves *mid* unchanged — so bonds and precious
metals are traded at the commodity speed and energy and industrial metals at the
bond speed. If the speed grouping were fitted noise rather than a real ordering,
reversing it should cost little; the point of the test is that it costs a lot.

**Falsification test.** Any comparison run specifically to fail if the claim is
wrong, rather than to confirm it. In this log it is always the reversed
configuration.

**Fit period / test period.** In out-of-sample tests, the span used to learn
group membership and the disjoint later span used to evaluate it. Split dates
and sample sizes are stated with each result.

**Contaminated.** A component chosen with knowledge of data it is later
evaluated on. Flagged wherever it applies, because a contaminated component
makes the surrounding result softer than it looks.

## Headline

Net of costs, full futures sample:

| Configuration | gross SR | net SR | t | ann.ret | ann.vol | maxDD | turn | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|
| uniform 12m | 0.72 | 0.70 | 4.77 | 2.7% | 4.0% | −8.0% | 2.6× | 0.77 | 0.63 |
| two-speed, superseded labelling (financials 12m / commodities 6m) | 0.84 | 0.82 | 5.60 | 3.1% | 3.9% | −8.3% | 2.7× | 0.79 | 0.88 |
| **three-speed 18 / 9 / 3** | **0.91** | **0.89** | **6.10** | 3.6% | 4.1% | −9.1% | **2.3×** | 0.79 | **1.07** |
| *reversed* (slow↔fast) | 0.49 | 0.45 | 3.24 | 1.8% | 3.9% | −14.2% | 4.2× | 0.49 | 0.42 |
| three-speed, sign-only | — | 0.55 | 3.81 | 5.0% | 9.7% | −37.3% | 1.7× | — | — |

**1st / 2nd half** split the sample at **2003-01** — 1979-2002 and 2003-2026,
about 24 years each. These columns are a **stability check, not an out-of-sample
test**: the speed grouping was chosen with both halves visible. Genuine
out-of-sample results, with the split dates and learning rule stated, are in
[Out-of-sample testing](#out-of-sample-testing) — they are materially lower
(0.61–0.87 against the in-sample 0.90).

The cost drag scales with turnover, which is why the same 10 bps assumption
penalises a 2.3× futures book far less than it looks — see "Costs are not a
detail".

For comparison the ETF basket reached Sharpe 0.55 with **t 2.42** over 20 years.
The Sharpe gain is modest; the **t-stat more than doubles**, which is what the
longer span buys — see "What this sample can establish".

## The main finding: trend speed differs by asset class

Sweeping the lookback from 1 to 24 months (five volatility windows each, 40
cells) gives a single-peaked curve — median Sharpe by lookback:

```
  1m 0.25   2m 0.49   3m 0.55   6m 0.53   9m 0.70   12m 0.69   18m 0.54   24m 0.34
```

But no single window is right for every market. Per-market optima, full sample:

| Speed | Markets | Optimum | Mechanism |
|---|---|---|---|
| **slow (18m)** | bonds (7 of 10 peak at 18m), **precious metals** | Bund 0.69, US 5y 0.70, gold 12m, silver 6m | the rate cycle; gold is a monetary asset priced off real rates and the dollar |
| **mid (9m)** | equity indices, FX, REITs | DAX/FTSE/HangSeng 9m, EuroStoxx/Nikkei 6m | — |
| **fast (3m)** | energy, **industrial metals**, agriculture | copper 3m, zinc 3m, Brent 3m, natgas 3m | inventory and supply response shorten trends |

### Two groupings, named once

Two different ways of assigning markets to speed groups are compared throughout
this log. They are distinct objects and the difference matters, so both are
defined here and referred to by these names everywhere else.

**Economic grouping** — assignment by mechanism, fixed by hand, the same in
every period:

```python
PRECIOUS = {"GOLD", "SILVER"}

def economic_grouping(asset, asset_class):
    if asset_class == "bond" or asset in PRECIOUS:
        return "slow"                    # priced off the rate cycle
    if asset_class in ("equity", "fx"):
        return "mid"
    return "fast"                        # inventory / supply response
```

Applied to the basket this gives slow = 12 markets (10 bonds + gold + silver),
mid = 9 (7 equity indices, USDINDEX, GBPJPY), fast = 14 (3 energy, 4 industrial
metals, 7 agriculture). The full membership list is in
[What "blending" means](#what-blending-means-precisely).

*This grouping is contaminated for out-of-sample purposes.* It was not derived
from theory alone — the mechanism story was written after inspecting the
full-sample per-market optima in the table above. It is a mechanism-shaped
summary of an in-sample observation, and every result that uses it inherits that.

**Learned grouping** — assignment by fitting, recomputed from data:

```python
# fit-period data only
best = argmax over lb in {3, 6, 9, 12, 18, 24} of single_market_sharpe(asset, lb)
group = "slow" if best >= 12 else "mid" if best >= 9 else "fast"
```

where `single_market_sharpe` is the annualised Sharpe of holding
`sign(trailing lb-month return)` in that one market, one position, no scaling. A
lookback needs 36 usable observations to be considered and a market needs 5 of
the 6 lookbacks evaluable to be assigned; otherwise it falls back to the economic
grouping. This is the grouping the out-of-sample tests evaluate, because it is
the only one that can be recomputed without hindsight.

The two agree on 20 of 35 markets when the learned version is fitted to
1979–2012, and on 22 of 35 when fitted to 1979–2008.

Running each group at its own speed lifts gross Sharpe from **0.70 to 0.91** and
*reduces* turnover from 2.6× to 2.3× — because bonds, the heaviest leg under
inverse-vol sizing, slow from 12m to 18m.

**The precious-vs-industrial split inside "metals" is the load-bearing part.**
Gold optimises at 12m and copper at 3m. Any grouping that treats them as one
asset class gets this wrong, which is exactly what happened first.

### How the grouping was found: a failed replication

The first version of this finding was a **two-speed** split labelled
"financials slow (12m) / commodities fast (6m)". On futures it looked strong —
0.70 → 0.82, stable across halves, and reversing it collapsed Sharpe to 0.47.

Then it was tested on the independent 10-ETF basket and **failed**:

| ETF configuration | gross SR | net SR |
|---|---|---|
| uniform 12m | 0.60 | 0.55 |
| two-speed, superseded labelling (financials 12m / commodities 6m) | **0.56** | 0.51 |
| *reversed* fin 6m / cmd 12m | **0.68** | 0.60 |
| **three-speed 18 / 9 / 3** | **0.73** | **0.67** |

The reversed version was *better* on ETFs — the opposite of the futures result.
The reason turned out to be diagnostic rather than fatal: the ETF basket's only
two "commodities" are **GLD** (a monetary metal) and **DBC** (a 14-commodity
index, whose averaging removes the fast idiosyncratic reversals and leaves the
slow common factor). Both are slow assets wearing a commodity label, so giving
them 6m hurt; and the "financials" bucket contained SPY/EFA/EEM, which want
6–9m, so giving them 12m also hurt. Reversing the labels accidentally gave each
group roughly the right speed.

Regrouping by the three measured speeds lifts the same ETF basket from 0.60 to
**0.73**, beating even the accidental reversal. **The failed replication is what
produced the correct grouping** — the two-speed labels happened to align with
the mechanism on the futures basket only because its "financials" were dominated
by 10 bonds and its "commodities" by energy and industrial metals.

### Why this is economic and not fitted

1. **Falsification.** Reversing the speeds collapses gross Sharpe 0.91 → 0.49 and
   raises turnover 2.3× → 4.2×, consistently in both halves (0.49 / 0.42).
   Curve-fitting has no preferred direction.
2. **An independent basket confirms it** after the regrouping — and the
   confirmation came from a construction the grouping was not fitted on.
3. **Plateau, not spike**: 18/9/3 scores 0.91 and 18/9/6 scores 0.90.
4. **A mechanism stated in advance**: monetary assets track the slow macro
   clock; consumption commodities have inventory and supply responses that
   truncate trends.

### But do not tune the exact month

Every class changed its precise optimum between sample halves:

```
             1st half optimum    2nd half optimum
  equity          12m                  9m
  bond            12m                 18m
  fx              12m                  9m
  energy           3m                  6m
  metal            3m                  6m
  ag               3m                  6m
```

The coarse grouping survives; the exact month does not. Use
`lookback_by_group` with `TREND_SPEEDS` and blend over neighbouring speeds
rather than committing to one. Blending 6m+9m+12m uniformly gives 0.73 against
the ex-post best single 9m at 0.72 — no alpha, but no need to have known which
window would win.

## Per-asset tuning overfits; the coarse grouping does not

If three speeds beat one, why not fit a speed to each of the 35 markets? Tested
with optima fitted on the **fit period only**, then applied unchanged to the test
period. Split dates and the thin-history problem are explained in
[Out-of-sample testing](#out-of-sample-testing) — an earlier version of this
section used a 2003-01 split, which is invalid for exactly that reason.

**Split 2012-01** (fit 1979–2012, test 2012–2026, 176 test months, all 35
markets assignable):

| Configuration | free parameters | fit period | **out-of-sample** | turn |
|---|---|---|---|---|
| uniform 12m | 1 | 0.82 | **0.38** | 2.6× |
| three-speed single 18/9/3, [economic grouping](#two-groupings-named-once) | 3 | 0.93 | **0.81** | 2.3× |
| 2-point blend, [economic grouping](#two-groupings-named-once) | 3 | 0.97 | 0.75 | 2.3× |
| 2-point blend, [learned grouping](#two-groupings-named-once) | 3 | 1.07 | 0.61 | 2.7× |
| **per-asset optimum** (one speed fitted per market, fit period only) | **35** | **1.14** | **0.69** | 3.0× |

**Split 2008-01** (fit 1979–2008, test 2008–2026, 224 test months):

| Configuration | free parameters | fit period | **out-of-sample** | turn |
|---|---|---|---|---|
| uniform 12m | 1 | 0.83 | **0.44** | 2.6× |
| three-speed single 18/9/3, [economic grouping](#two-groupings-named-once) | 3 | 0.90 | **0.87** | 2.3× |
| 2-point blend, [economic grouping](#two-groupings-named-once) | 3 | 0.95 | 0.82 | 2.3× |
| 2-point blend, [learned grouping](#two-groupings-named-once) | 3 | 1.01 | 0.75 | 2.4× |
| **per-asset optimum** (one speed fitted per market, fit period only) | **35** | **1.05** | **0.57** | 2.9× |

The pattern is the textbook shape of overfitting, and it is monotone in both
directions at both split dates: **fit-period Sharpe rises with parameter count
while out-of-sample Sharpe falls.** Thirty-five parameters reach the best fit
(1.14 and 1.05) and one of the worst tests (0.69 and 0.57). Turnover rises too —
jumpy fitted speeds flip positions more often, so they cost more to trade.

Note also that the *economic* grouping tests better than the *learned* grouping
(0.81 vs 0.61; 0.87 vs 0.75) even though it fits worse. Its group membership is
contaminated — it was informed by full-sample per-market optima — so this is not
proof. But it is the pattern one expects if a mechanism-based split generalises
better than a data-fitted one.

The grouping works partly *because* it is coarse. Three parameters drawn on an
economic distinction — monetary assets versus consumption commodities —
generalise where thirty-five fitted ones do not.

## Regime drift: the exact speed moves, the ordering does not

The optimal lookback per class, computed decade by decade, drifts substantially:

| Class | 1979s | 1990s | 2000s | 2010s | 2020s |
|---|---|---|---|---|---|
| bond | 12m | 12m | **18m** | **18m** | **9m** |
| equity | 12m | **24m** | **6m** | 9m | **24m** |
| fx | — | 18m | 12m | **6m** | 9m |
| energy | — | **3m** | 6m | **9m** | 6m |
| metal | — | 6m | **18m** | **6m** | 9m |
| ag | 6m | 3m | 3m | 3m | **9m** |

Every class moves; equities run 24m → 6m → 24m. **There is no stable global
optimum per asset to find** — which is the deeper reason per-asset fitting
fails, beyond the parameter count.

But the *relative ordering* survives every decade. Three-speed against its own
reversal:

| Decade | three-speed | reversed | difference |
|---|---|---|---|
| 1979–1989 | 0.58 | 0.48 | +0.10 |
| 1990–1999 | 1.21 | 0.56 | **+0.65** |
| 2000–2009 | 1.38 | 0.58 | **+0.80** |
| 2010–2019 | 0.80 | 0.43 | +0.37 |
| 2020–2026 | 0.98 | 0.16 | **+0.82** |

**Five decades, five wins, no exceptions.** "Bonds and precious metals trend
slowly; energy and industrial metals trend fast" holds in every regime even
though the precise month does not.

The 1979–1989 margin is the thinnest (+0.10) and worth noting rather than
explaining away: only 10 markets existed then, so the grouping has little to
work with.

**Practical consequence.** Do not search for a per-asset optimum, and do not
adapt speeds dynamically either — if a static per-asset fit already overfits,
a rolling one makes more choices on less data and will be worse. Fix the coarse
grouping and **blend neighbouring speeds within each group**, so that when the
true optimum drifts from 12m to 18m part of the book is always pointed at it.
Diversify across parameters instead of selecting one.

## Blending neighbouring speeds: buys risk, not return

### What "blending" means, precisely

It is **averaging, not searching.** No asset selects a speed. To blend two
speeds per group, the backtest is run twice — once with each speed assignment —
and the two **weight panels are averaged element-wise**. Every slow asset then
holds 50% of its 12-month signal and 50% of its 18-month signal, simultaneously
and permanently.

The only decision made per asset is **which group it belongs to**, fixed once:

| Group | Speeds blended | n | Markets |
|---|---|---|---|
| **slow** | 12m + 18m | 12 | AUS3Y, BOBL, BUND, GILT, GOLD, JGB10Y, SCHATZ, SILVER, US2Y, US5Y, US10Y, US30Y |
| **mid** | 9m + 12m | 9 | DAX, ESTOXX50, FTSE100, GBPJPY, HANGSENG, KOSPI200, NIKKEI225, SPI200, USDINDEX |
| **fast** | 3m + 6m | 14 | ALUMINIUM, BRENT, COCOA, COFFEE, COPPER, CORN_MAT, NATGAS, NICKEL, ORANGEJUICE, SUGAR, WHEAT_LIF, WHEAT_MAT, WTI, ZINC |

### The configurations tested

Each row states the **full speed assignment per variant**, so the table is
reproducible. "Variant A / B / C" are the runs whose weight panels are averaged.

| # | Configuration | slow group | mid group | fast group |
|---|---|---|---|---|
| 1 | single (no blend) | 18 | 9 | 3 |
| 2 | **2-point blend** | 12, 18 | 9, 12 | 3, 6 |
| 3 | 3-point blend, tight | 12, 18, 24 | 6, 9, 12 | 3, 6, 9 |
| 4 | 3-point blend, faster tail | 12, 18, 24 | 6, 9, 12 | 2, 3, 6 |
| 5 | 3-point blend, **wide spacing** | 9, 18, 24 | 6, 9, 18 | 2, 3, 9 |
| 6 | control: ungrouped blend | 6, 9, 12 | 6, 9, 12 | 6, 9, 12 |
| 7 | control: ungrouped, wide | 3, 9, 18 | 3, 9, 18 | 3, 9, 18 |

Results, full sample, net of 2 bps per side:

| # | net SR | t | 1st half | 2nd half | vol | maxDD | turn |
|---|---|---|---|---|---|---|---|
| 1 | 0.89 | 6.10 | 0.79 | 1.07 | 4.1% | −9.1% | 2.3× |
| **2** | **0.90** | **6.21** | **0.84** | 1.02 | 3.7% | **−6.4%** | 2.3× |
| 3 | 0.88 | 6.06 | 0.79 | 1.04 | 3.5% | −6.3% | 2.1× |
| 4 | 0.85 | 5.87 | 0.78 | 0.99 | 3.6% | −6.0% | 2.2× |
| 5 | 0.81 | 5.58 | 0.72 | 0.97 | 3.5% | −6.9% | 2.3× |
| 6 | 0.74 | 5.04 | 0.71 | 0.80 | 3.5% | −7.5% | 2.7× |
| 7 | 0.70 | 4.76 | 0.62 | 0.82 | 3.3% | −7.4% | 2.9× |

> **The "1st half / 2nd half" columns are a stability check, not an
> out-of-sample test.** The grouping was chosen with both halves visible. For a
> genuine out-of-sample evaluation see the next section.

### What blending does and does not buy

**Sharpe barely moves** (#1 0.89 → #2 0.90) but **maximum drawdown falls 30%**,
from −9.1% to −6.4%, and volatility from 4.1% to 3.7%. An expectation recorded
here for the correction: blending was expected to raise Sharpe. It does not. It
buys risk reduction.

**Spacing must be tight.** Config #5 spreads each group across a wide range —
the slow group blends 9m with 24m — and drops to 0.81. Averaging in a speed far
from the group's own optimum dilutes the signal. "Neighbouring" is load-bearing.

**Blending without grouping is worthless.** Controls #6 and #7 apply the same
blend to every market regardless of group and land at 0.74 and 0.70 —
indistinguishable from a single uniform 12m (0.70). All of the edge comes from
the grouping; blending only makes it safer to hold.

**What it does buy is immunity to picking the wrong centre.** Taking the three
variants of config #4 separately:

| Single variant (slow / mid / fast) | net SR |
|---|---|
| 12 / 6 / 2 | **0.64** |
| 18 / 9 / 3 | **0.89** |
| 24 / 12 / 6 | 0.82 |
| *average of the three weight panels* | **0.85** |

Choosing one centre badly costs 0.25 of Sharpe. The blend returns 0.85 — above
the mean of the three (0.78), near the ex-post best (0.89) — **without needing
to know in advance which was right.** Give up 0.04 against hindsight to remove a
0.25 selection risk.

### Full numbers for the recommended configuration (#2)

Slow 12+18, mid 9+12, fast 3+6, at 2 bps per side:

```
  gross SR 0.93   net SR 0.90   t 6.21   ret 3.3%   vol 3.7%   maxDD -6.4%   turn 2.3x
  costs:   2bps 0.90    5bps 0.87    10bps 0.80
  decades: 1979-89 0.72   1990-99 1.03   2000-09 1.37   2010-19 0.74   2020-26 0.92
  crisis:  1980 +9.4  1987 +2.5  1990 +1.7  1998 +3.2
           2002 +7.1  2008 +7.6  2020 +1.1  2022 +8.8
```

Every decade and all eight stress years positive. At a 15% volatility target:
**13.8% a year, 15.4% volatility, −24.7% maximum drawdown, Sharpe 0.92**.

Added to equities over 2006–2026 (trend 0.71 standalone against SPY's 0.63
excess of cash, beta −0.21, correlation −0.21). **The trend leg here is levered
to the 15% volatility target — median 4.6× notional in that leg.** Unlevered it
runs at 3.2% volatility and the conclusion changes materially; see
[the portfolio section](#the-real-case-marginal-contribution-not-standalone-sharpe)
for both versions and the margin arithmetic.

| Mix | Sharpe | ann.ret | maxDD | total notional |
|---|---|---|---|---|
| 100% SPY | 0.63 | 10.7% | −38.3% | 1.0× |
| 80% SPY + 20% trend @15% vol | 0.82 | 11.2% | −27.0% | 1.7× |
| **60% SPY + 40% trend @15% vol** | **1.02** | **11.4%** | **−14.9%** | **2.4×** |

Config #1 (single 18/9/3) reaches 1.06 / −14.4% on the same basis. The two are
within noise; #2 is preferred because it does not require having chosen the
right centre speed and its drawdown is a third smaller.

## Out-of-sample testing

Everything above is in-sample: the speed grouping was derived from full-sample
per-market optima. This section tests it properly. Read it before believing any
number in the preceding sections.

### Method

**What is being tested.** Whether the speed *grouping* — which markets are slow,
mid, fast — carries information that survives out of sample.

**What is learned from data, and what is not.** Two things must be separated:

| Component | How chosen | Contaminated? |
|---|---|---|
| Group membership — the [learned grouping](#two-groupings-named-once) | fitted on the fit period only | **No** — this is what the test evaluates |
| Speed values per group (12/18, 9/12, 3/6) | chosen by the author after seeing the full sample | **Yes** — acknowledged, not fixed |
| Volatility window (126d), cost (2 bps), rebalance (monthly) | fixed in advance for all configurations | not varied |

So the test is honest about group membership and **still contaminated on the
speed values**. A fully clean test would learn the speeds from the fit period
too; that is not done here.

**Learning rule.** The [learned grouping](#two-groupings-named-once) as defined
above, fitted on fit-period data only. Markets that cannot be assigned fall back
to the economic grouping, which is itself contaminated — so a split date where
many markets fall back is a weak test. That is why the split date matters.

**Choosing the split date.** This is where the first attempt went wrong. The
markets do not all start together — the basket runs from 4 markets in 1979 to
all 35 by 2006:

```
  1979 COCOA COFFEE ORANGEJUICE SUGAR      1993 ALUMINIUM COPPER NICKEL ZINC
  1982 GILT                                1995 AUS3Y      1996 KOSPI200
  1984 FTSE100                             1997 GBPJPY
  1985 USDINDEX                            1998 WHEAT_MAT ESTOXX50 BOBL BUND
  1988 HANGSENG NIKKEI225 BRENT                 SCHATZ US30Y US10Y US2Y US5Y
  1989 WHEAT_LIF                           1999 CORN_MAT   2000 SPI200
  1990 NATGAS DAX                          2004 GOLD SILVER  2005 JGB10Y  2006 WTI
```

Evaluating an 18-month lookback needs roughly 18 + 48 months of history, so a
fit period ending before ~2011-08 cannot assess the long lookbacks for the
late-starting markets:

| Split | Markets with sufficient fit-period history |
|---|---|
| 2003-01 | **19 / 35** |
| 2008-01 | 31 / 35 |
| **2012-01** | **35 / 35** |

### Retracted: the 2003-01 split

An earlier version of this analysis split at 2003-01 and reported a genuine
out-of-sample Sharpe of 0.70 against uniform 12m's 0.63, with **no falsification
signal** (the reversed grouping also scored 0.70). That result is withdrawn: it
was an artifact.

At that split, every bond had data for the 3-month lookback only; 12m, 18m and
24m returned NaN for insufficient observations. The argmax therefore selected
3m for BUND, BOBL, SCHATZ and all four US Treasuries **because it was the only
value available**, not because it was best. A third of the group assignments
were noise, which is exactly why the falsification test showed nothing.

The lesson is recorded rather than buried: **when a learning rule can return a
degenerate answer on thin data, check that it did not.**

### Results

Split **2012-01** — fit 1979-01 to 2012-01, test 2012-02 to 2026-08
(**176 test months**, 35/35 markets assignable, learned grouping agrees with the
[economic grouping](#two-groupings-named-once) on 20/35):

| Configuration | fit period | **out-of-sample** | turn |
|---|---|---|---|
| uniform 12m (nothing learned) | 0.82 | **0.38** | 2.6× |
| blend, [learned grouping](#two-groupings-named-once) | 1.07 | **0.61** | 2.7× |
| blend, [economic grouping](#two-groupings-named-once) *(contaminated)* | 0.97 | 0.75 | 2.3× |
| blend, learned grouping **reversed** | 0.66 | **0.31** | 3.1× |
| blend, [economic grouping](#two-groupings-named-once) **reversed** | 0.64 | **0.23** | 3.6× |

Split **2008-01** — fit 1979-01 to 2008-01, test 2008-02 to 2026-08
(**224 test months**, 31/35 assignable; the 4 markets with too little history
fall back to the [economic grouping](#two-groupings-named-once)):

| Configuration | fit period | **out-of-sample** | turn |
|---|---|---|---|
| uniform 12m (nothing learned) | 0.83 | **0.44** | 2.6× |
| blend, [learned grouping](#two-groupings-named-once) | 1.02 | **0.74** | 2.4× |
| blend, [economic grouping](#two-groupings-named-once) *(contaminated)* | 0.95 | 0.82 | 2.3× |
| blend, learned grouping **reversed** | 0.57 | **0.31** | 3.5× |
| blend, [economic grouping](#two-groupings-named-once) **reversed** | 0.66 | **0.30** | 3.6× |

### Walk-forward

**Procedure.** At the start of each five-year window, using only data up to that
date, both components are recomputed and then held fixed while the next five
years are traded:

1. **Group membership** — the [learned grouping](#two-groupings-named-once).
   Markets that cannot yet be assigned fall back to the economic grouping.
2. **The two speeds per group** — for each learned group, the average
   single-market Sharpe is computed across its members at each candidate lookback
   in {3, 6, 9, 12, 18, 24}, and the top two are blended.

Nothing from a test window informs its own configuration. **This is the one
fully clean test in this log**: everywhere else the speed values were fixed at
12/18, 9/12, 3/6, which the author chose after seeing the full sample.

**"Stitched" means the six test windows are concatenated into one continuous
return series**, and a single Sharpe is computed on the whole thing. The six
windows tile 1994-01 through 2023-12 exactly — 6 × 60 = **360 months**, verified
to contain no duplicated and no missing months. The comparison row is the uniform
12m strategy over that identical set of 360 months, so the two are aligned
month-for-month.

#### Per-window configuration

One row per test window, with every parameter that window used. Nothing in a row
was chosen with knowledge of that row's test period.

| Test window | months | SR | markets: exist / assignable / new mid-window | learned groups slow/mid/fast | speeds: slow | mid | fast |
|---|---|---|---|---|---|---|---|
| 1994-01 – 1998-12 | 60 | 1.18 | 17 / 10 / **12** | 6 / 1 / 10 | 12+18 | 12+12 | 3+12 |
| 1999-01 – 2003-12 | 60 | 1.11 | 29 / 17 / 2 | 13 / 5 / 11 | 12+18 | 9+12 | 3+6 |
| 2004-01 – 2008-12 | 60 | 1.90 | 31 / 29 / 4 | 12 / 6 / 13 | 12+18 | 9+12 | 3+6 |
| 2009-01 – 2013-12 | 60 | 0.65 | 35 / 31 / 0 | 16 / 4 / 15 | 12+18 | 9+18 | 3+6 |
| 2014-01 – 2018-12 | 60 | 0.63 | 35 / 35 / 0 | 16 / 6 / 13 | 12+18 | 9+12 | 3+6 |
| 2019-01 – 2023-12 | 60 | 0.79 | 35 / 35 / 0 | 14 / 7 / 14 | 18+24 | 9+12 | 3+6 |

Column meanings: **exist** = markets with any history at the window start;
**assignable** = of those, how many had enough history to evaluate all six
candidate lookbacks; **new mid-window** = markets that begin trading during the
test period and therefore run on the fallback grouping. **speeds** are the two
lookbacks blended for that group — `12+18` means every slow-group market holds
the average of its 12-month and 18-month signals.

Parameters held fixed across all windows, chosen once and never varied:
volatility window 126 days, cost 2 bps per side, monthly rebalance, long/short,
inverse-volatility sizing, candidate lookback menu {3, 6, 9, 12, 18, 24},
minimum 36 observations for a lookback to be evaluable, minimum 5 of 6 lookbacks
evaluable for a market to be assigned.

#### Aggregate comparison

These are **not additional configurations** — the first row is the six windows
above concatenated into one continuous return series, with a single Sharpe
computed on the whole 360 months. The other two rows are alternatives evaluated
over that identical set of months, so all three are aligned month-for-month.

| Series over 1994-01 – 2023-12 (360 months) | grouping | speeds | SR |
|---|---|---|---|
| **walk-forward, both re-learned every 5 years** | re-learned per window (see table above) | re-learned per window (see table above) | **1.02** |
| walk-forward, grouping re-learned, speeds fixed | re-learned per window | fixed 12+18 / 9+12 / 3+6 | 1.00 |
| uniform 12m — nothing learned at all | none; every market identical | fixed 12 for every market | 0.79 |

**An earlier version of this table was wrong and the correction matters.** It
reported group counts summing to 35 in every window — including 1994–1999, when
only 17 markets existed. The counts were taken over all 35 columns, so the 18
markets that did not yet exist were silently counted in whichever bucket the
fallback assigned them. The Sharpe figures were not affected (a market with no
data is excluded by the eligibility test regardless of its group), but the
counts were meaningless.

**Only the last three windows are clean walk-forward tests.** Before 2009 a
large number of markets either could not be assigned from fit-period data or
appeared part-way through the test window and traded on the fallback — 12 of them
in 1994–1999. Those windows therefore measure something closer to the economic
grouping than to a learned one.

Read the clean windows on their own: **0.65, 0.63, 0.79**, or 0.69 for the three
stitched together against uniform 12m's 0.40 over the same 180 months. That is
materially below the full stitched 1.02, and consistent with the single-split
results (0.61–0.87) rather than with the in-sample 0.90. The clean windows also
happen to cover 2009–2024, which contains the drought — so this is a hard test,
not a representative one.

### The speed contamination turns out to be immaterial

Because this walk-forward learns the speeds as well, it measures how much the
contamination elsewhere in this log actually cost. Read the speed columns above:
**four of the six windows select exactly `12+18 · 9+12 · 3+6`** — the values
chosen by hand after seeing the full sample — and the other two differ in one
group only (1994–1999 has too little history to separate mid from fast;
2019–2024 shifts the slow group to 18+24).

Learning the speeds honestly scores **1.02** against **1.00** for the hand-picked
values. So the hand-picked speeds were not doing hidden work: the data selects
the same ones at nearly every point in time, without hindsight. That does not
repair the contamination in the other sections, but it bounds it — the speed
values look like a stable property of these markets rather than a fitted choice.

### What the out-of-sample tests actually establish

**Supported.** The grouping carries out-of-sample information. At both split
dates the learned-grouping blend beats uniform 12m by a wide margin (0.61 vs
0.38; 0.74 vs 0.44), and the **falsification survives out of sample** — reversing
the grouping drops it to 0.31 and 0.23 at the 2012 split, 0.31 and 0.30 at 2008.
Four reversal tests, four clear failures. Overfitting does not produce a
direction that holds in data it never saw.

**Not supported.** The magnitudes in the preceding sections. The full-sample
0.90 is in-sample; honest out-of-sample readings are **0.61 to 0.74**, and the
test windows overlap the 2012–2019 drought, which cuts every configuration.
Uniform 12m falls to 0.38 over the same months.

**Still contaminated.** The speed values (12/18, 9/12, 3/6) were chosen after
seeing the full sample. Only the group membership was learned cleanly. A fully
out-of-sample result requires learning both.

**A separate, cleaner piece of evidence** is the ETF basket test recorded above:
a differently constructed 10-market basket, not used to derive anything, where
regrouping lifted gross Sharpe from 0.60 to 0.73. That is out-of-sample in the
cross-section rather than in time.

## What turned out not to matter: the volatility window

Median Sharpe by volatility window, across all lookbacks:

```
  42d 0.53    63d 0.54    126d 0.55    252d 0.52    504d 0.45
```

Flat from two months to a year; only the two-year window degrades. **An earlier
version of this log said "252-day is best" — that was wrong.** The real effect
was daily-versus-monthly estimation, not the specific window. On the ETF sample
(monthly and weekly data only) shorter windows looked better because monthly data
runs out of observations; with daily data there are enough observations that
window length stops mattering. One coherent statement covers both: **you want
roughly a year of volatility lookback, and daily data lets you estimate it
precisely.**

## Volatility scaling works — through risk, not return

| | ann.ret | ann.vol | maxDD | Sharpe |
|---|---|---|---|---|
| sign-only | **5.0%** | 9.7% | −37.3% | 0.55 |
| vol-scaled | 3.6% | **4.1%** | **−9.1%** | **0.89** |

The scaled book earns **less** return; the entire Sharpe gain comes from cutting
volatility by 60% and the drawdown from −37% to −8%. This is the mechanism Kim,
Tse & Wald identified — much of what looks like a trend premium is a
**volatility-timing** effect. On 47 years and 35 markets the critique holds, and
more strongly than on the ETF sample (0.37 → 0.46 there).

The reason is the volatility spread: 1.0% (AUS 3-year) to 61.9% (natural gas),
a factor of 62. Unscaled, natural gas alone would dominate the book.

## The return level is a leverage choice, not a property of the strategy

A recurring objection is that 3.1%/year is very low. That is an artifact of the
construction: weights are `sign × (target_vol / vol_i) / n`, so **portfolio
volatility falls as markets are added** — 35 futures run at 3.9% vol where 10
ETFs ran at 5.3%. Portfolio volatility should be targeted independently of how
many markets are traded.

Adding ex-ante portfolio volatility targeting (36-month trailing estimate of the
strategy's own volatility, lagged one period):

| Target vol | Sharpe | ann.ret | realised vol | maxDD | median leverage |
|---|---|---|---|---|---|
| none (as built) | 0.90 | 3.3% | 3.7% | −6.4% | 1.3× |
| 10% | 0.92 | **9.3%** | 10.3% | −17.0% | 3.1× |
| 15% | 0.92 | **13.8%** | 15.4% | −24.7% | 4.6× |

**The return scales linearly.** Sharpe also rises slightly, 0.90 → 0.92, because
the rolling rescaling adds a little volatility timing of its own — leaning in
when the book is calm. Attribute that to the timing, not to the leverage:
scaling by a *constant* cannot change Sharpe, only a time-varying factor can.
At a 15% target the strategy earns **13.8% a year at 15.4% volatility with a
−24.7% maximum drawdown**, against equities' ~11% at ~15% with −38%, at
beta ≈ −0.2.

Implemented as `performance.volatility_target(gross, weights, target_vol, ...)`.
Two details it handles that a hand-rolled version usually does not:

- **The leverage trade is charged.** Multiplying a net return series by leverage
  scales the strategy's own costs correctly but misses the cost of *changing*
  leverage — moving from 5.50× to 5.38× is itself a trade. The function scales
  the weights and re-costs them, so `Σ|w_t − w_{t−1}|` is computed on the levered
  book. Measured impact: **−0.01pp of annual return, 0.00 Sharpe.** The omission
  was real but immaterial, because a 36-month volatility estimate drifts too
  smoothly to generate much rebalancing.
- **A leverage cap** (default 10×). It never binds here — raw leverage peaks at
  6.3× against a 4.6× median — but calm stretches in other samples will imply
  absurd gearing, and a cap is the difference between a backtest and a fantasy.

**Sensitivity worth knowing.** These figures depend on the warm-up length, not
because the estimator is fragile but because of sample composition: 36/18 gives
Sharpe 0.92, 36/24 gives 0.96, 36/36 gives 0.99. Restricted to the **common**
sample all three give exactly 0.99 — so the entire spread comes from whether the
weak 1980–1982 months are included, when only 10 markets existed. The table
above uses the module default (`min_periods = window // 2`), which includes the
most data and therefore reads lowest. An earlier version of this log quoted the
`min_periods=24` figures without saying so, which was not a defensible way to
pick a number.

Futures make this practical: margin is a few percent of notional, so a 4.4×
notional book consumes roughly a quarter of capital in margin. Doing the same
with ETFs would require actual borrowing. This is the capital-efficiency argument
for futures, quantified.

## Breadth rose, gross performance did not

Effective breadth went from 3.4 (10 ETFs) to 8.0 (35 futures). Over the
**overlapping** period both baskets produced a **gross Sharpe of 0.60** — the
whole net difference was the cost assumption (ETF turnover 1.3×, futures 3.6×).
An earlier version of this log called the breadth gain "the payoff"; that was
premature.

Two things it is *not*:

- **Not bond redundancy.** Bonds take 55% of gross weight (inverse-vol gives low-
  volatility assets large notional) but only **26% of risk** — inverse-vol is
  already handling the concentration. Risk-based effective market count is 24.5
  of 35.
- **Not weak commodity signals.** Dropping agriculture costs 0.72 → 0.63 Sharpe,
  and dropping both agriculture and FX costs 0.72 → 0.49 while *raising*
  volatility and drawdown. The obscure markets are the diversifying ones: FX
  correlates **−0.01** with the average of equity/bond/energy/metal, ag +0.36.

What it plausibly *is*: the ETF basket is US-centric during a US-trending regime.
SPY, IEF and LQD are three of its four best single-market signals, while the
futures basket contains **no US equity index** — the E-mini S&P continuous series
is absent from the CS0x family — and its equity leg averages a per-market Sharpe
of only 0.01 over 2006–2026 against SPY's 0.55. That is a real gap in the basket
with a measured cost, and worth fixing.

## Costs are not a detail

| Cost per side | net Sharpe | ann.ret |
|---|---|---|
| 2 bps | 0.89 | 3.6% |
| 5 bps | 0.85 | 3.5% |
| 10 bps | 0.80 | 3.2% |

A 0.09 Sharpe swing from an execution assumption, on a strategy whose whole edge
is 0.89. Turnover is 2.3×/year, so this scales directly. Any comparison between
instruments has to use each one's real cost — comparing futures and ETFs at the
same 10 bps understates futures by about 0.09 Sharpe.

## Crisis alpha, and the drought

Calendar-year returns of the three-speed configuration:

```
  1980 +8.0    1987 +2.7    1990 +4.5    1998 +1.6
  2002 +6.4    2008 +8.6    2020 +1.4    2022 +8.1
```

**Positive in all eight equity-stress years**, including 2020 — the uniform and
two-speed versions were flat or negative there. The fast commodity leg is what
does it: energy and industrial metals turned inside the COVID quarter, which a
12-month signal could not.

Decade Sharpe:

```
  1979-1989 0.58    1990-1999 1.21    2000-2009 1.38
  2010-2019 0.80    2020-2026 0.98
```

Every decade positive, and the 2011–2019 CTA drought reads **0.80** against 0.37
under a uniform lookback. Industry benchmarks went broadly sideways in that
decade. This is the single largest practical gain from the speed grouping: it is
not that the good decades got better, it is that the bad one stopped being bad.

## The real case: marginal contribution, not standalone Sharpe

Over the ETF-overlapping period (2006–2026) the strategy scores about **0.71**
standalone against SPY's **0.63** excess of cash. But the portfolio effect is the
stronger argument — with one precondition that has to be stated up front.

**The trend leg is leveraged, and the argument depends on it.** The rows below
allocate capital to the trend strategy *after* volatility targeting it to 15%,
which runs a median notional of **4.6× the capital in that leg**. Without
leverage the strategy runs at 3.2% volatility, and a 40% allocation is mostly an
allocation to cash:

| Mix | trend leg | Sharpe | ann.ret | ann.vol | maxDD | total notional |
|---|---|---|---|---|---|---|
| 100% SPY | — | 0.63 | 10.7% | 15.4% | −38.3% | 1.0× |
| 80/20 | **unlevered** (3.2% vol) | 0.67 | 9.2% | 12.2% | −30.8% | 1.0× |
| 60/40 | **unlevered** (3.2% vol) | 0.74 | **7.6%** | 9.1% | −22.7% | 1.0× |
| 80/20 | **15% vol target** | 0.82 | 11.2% | 12.1% | −27.0% | 1.7× |
| **60/40** | **15% vol target** | **1.02** | **11.4%** | 10.0% | **−14.9%** | **2.4×** |
| 40/60 | 15% vol target | 1.05 | 11.3% | 10.1% | −8.9% | 3.2× |

Unlevered, a 40% allocation buys a better Sharpe (0.63 → 0.74) but **gives up a
third of the return** (10.7% → 7.6%): the leg is too quiet to contribute much
risk, so the portfolio is mostly 60% equities and 40% near-cash. Levered to 15%,
the return is essentially unchanged (11.4%) while the drawdown halves. That is
the result worth having, and it is a statement about the levered leg.

**What the leverage costs to hold.** At the 60/40 mix the trend leg contributes
0.4 × 4.6 ≈ 1.8× of portfolio capital in futures notional, for a total notional
of 2.4×. At a 5% margin rate that consumes about **9% of portfolio capital** in
margin — comfortable, with room for the 95th-percentile leverage of 5.9×. This
is only practical with futures; the same position in ETFs would require actual
borrowing at a real financing cost, which none of these figures include.

Note the Sharpe convention: futures are self-financing (margin embeds the
funding), so `rf=0` is the correct excess Sharpe for the strategy. Equity
buy-and-hold must have cash subtracted, or its Sharpe is inflated — SPY reads
0.74 at `rf=0` against 0.63 properly measured.

## What this sample can and cannot establish

### Statistical power

`SE(annualised Sharpe) ≈ 1/√years`, with no frequency term. At 47 years the
standard error is about 0.15, so the in-sample t-stats (4.77 uniform, 6.10
three-speed, 6.21 blended) are comfortable. The ETF sample's t of 2.42 over 20
years was not. **But an in-sample t-stat is not evidence against overfitting** —
it measures whether a return series differs from zero, not whether the
configuration that produced it was chosen honestly.

### The multiple-testing count

Reaching these numbers took roughly **80 distinct configurations**:

| Family | Count |
|---|---|
| lookback × volatility-window grid | 40 |
| uniform-blend variants | 6 |
| two-speed variants (superseded labelling) | 6 |
| three-speed and blended variants | 7 |
| basket subsets (dropping classes) | 6 |
| cost levels | 3 |
| per-asset and learned-grouping fits | 6 |
| out-of-sample splits × configurations | ~10 |

At that count, a best-in-sample figure of 0.90 should be read as an upper bound
on what an honest process would have found. The PEAD log records the same lesson
from the other direction: ~30 tests there produced 3 with |t| > 2, which is what
chance predicts.

### What survives the count, and what does not

**Survives — the direction of the speed grouping.** The falsification control
(reversed slow↔fast) fails everywhere it is run, and crucially *out of sample*:

| Test | correct grouping | reversed |
|---|---|---|
| full sample, in-sample | 0.91 | **0.49** |
| OOS split 2012-01, learned grouping | 0.61 | **0.31** |
| OOS split 2012-01, economic grouping | 0.75 | **0.23** |
| OOS split 2008-01, learned grouping | 0.74 | **0.31** |
| OOS split 2008-01, economic grouping | 0.82 | **0.30** |

Five tests, five failures, four of them on data the grouping never saw.
Overfitting does not produce a direction that holds out of sample.

**Survives — cross-sectional replication.** The grouping was applied unchanged
to an independently constructed 10-ETF basket and lifted gross Sharpe from 0.60
to 0.73. That basket contributed nothing to deriving it.

**Survives — the shape of the parameter surface.** The lookback response is a
plateau, not a spike: 9m and 12m are within 0.02 of each other across five
volatility windows, and the volatility window itself is flat from 42 to 252 days.
A spike would suggest fitting; a plateau suggests a real, broad effect.

**Does not survive — the magnitudes.** The headline 0.90 is in-sample. Honest
out-of-sample readings are **0.61–0.87** depending on split, and the clean
walk-forward windows read **0.62–0.78**. Every out-of-sample window overlaps the
2012–2019 drought, which cuts all configurations (uniform 12m falls to 0.38 over
the same months), so these are hard tests rather than representative ones — but
0.90 is not the number to plan with.

**Does not survive — per-asset or dynamic speed selection.** Fitting one speed
per market reaches the best fit (1.14) and one of the worst tests (0.69). There
is no stable per-asset optimum to find: the optimal lookback drifts by decade in
every asset class.

### Still uncontrolled

- **The speed values are contaminated in every section except the walk-forward.**
  12/18, 9/12, 3/6 were chosen after seeing the full sample. The walk-forward
  learns them causally and scores 1.02 against 1.00, and four of its six windows
  select exactly those values — so the contamination is bounded and appears
  immaterial. It is still contamination everywhere else.
- **The economic grouping is a post-hoc mechanism story.** It was written after
  inspecting full-sample per-market optima. It generalises better than the fitted
  alternative, which is suggestive, but it is not theory that preceded the data.
- **Execution assumes 2 bps per side** with no slippage, no market impact and no
  margin financing cost. At 10 bps the recommended configuration reads 0.80
  rather than 0.90.
- **Returns are local-currency**, with no FX hedging cost for the 23 non-USD
  markets.
- **Basket survivorship.** The 35 markets were selected for having long, clean
  Datastream histories. Contracts that were delisted or never got liquid are
  absent, and the FX leg is thin because the FINEX contracts died.
- **No fees.** A real CTA charging 2/20 would turn a 0.90 gross Sharpe into
  roughly 0.5–0.6 net to the investor. Running it yourself avoids that, which is
  the main argument for doing so.

## Takeaways

1. **Trend speed differs by asset class, in three groups** — slow 18m (bonds,
   precious metals), mid 9m (equity, FX), fast 3m (energy, industrial metals,
   agriculture). Worth 0.70 → 0.91 gross **in sample**, with *lower* turnover
   (2.6× → 2.3×). The precious-vs-industrial split inside metals is the
   load-bearing part: gold optimises at 12m, copper at 3m.
2. **The direction survives out of sample; the magnitude does not.** Reversing
   the grouping fails in all five tests, four of them out of sample (0.61 vs
   0.31, 0.75 vs 0.23, 0.74 vs 0.31, 0.82 vs 0.30). But honest out-of-sample
   Sharpe is **0.61–0.87**, and the clean walk-forward windows read 0.62–0.78 —
   not the in-sample 0.90. Plan with the lower number.
3. **A failed replication produced the right answer.** The first labelling,
   "financials slow / commodities fast", failed on the ETF basket because its two
   commodities were gold and a 14-commodity index — both slow assets wearing a
   commodity label. Test a structural claim on a second basket before believing
   it.
4. **The volatility window barely matters** once estimated on daily data —
   anywhere from two months to a year. The earlier "252-day is best" claim was
   wrong; the real effect was daily-versus-monthly estimation.
5. **Do not tune per asset, and do not adapt dynamically.** Fitting a speed to
   each of 35 markets scores 1.14 in sample and 0.69 out of sample against the
   3-parameter [economic grouping](#two-groupings-named-once)'s 0.81 — and the
   fitted speeds agree with the mechanism for only 10 of 35
   markets. The optimal month also drifts by decade (equities 24m → 6m → 24m),
   so there is no stable per-asset optimum to find. Blend neighbouring speeds
   within each group instead of selecting one — that holds Sharpe at 0.90 while
   cutting the drawdown 30% and removing a 0.25 parameter-selection risk.
6. **Volatility scaling works by cutting risk, not raising return** — the
   Kim-Tse-Wald critique holds on 47 years and 35 markets.
7. **The return level is a leverage choice.** 3.3% at 3.7% vol is the same
   strategy as 13.8% at 15.4% vol. Target portfolio volatility explicitly;
   futures margin makes it practical where ETFs would need borrowing.
8. **More markets did not raise gross Sharpe**, but the diversifying legs are
   the valuable ones — FX correlates −0.01 with the rest of the book, and
   dropping agriculture and FX costs 0.72 → 0.49 while *raising* volatility.
9. **Costs are a first-order parameter**, worth 0.09 Sharpe between 2 and 10 bps
   at 2.3× turnover. Compare instruments at each one's real cost.
10. **Crisis alpha now covers all eight stress years**, 2020 included, because
   the fast commodity leg can turn inside a quarter. The drought decade reads
   0.80 (single 18/9/3) or 0.74 (recommended blend) against 0.37 under a uniform
    lookback — the largest practical gain, though still an in-sample figure.
11. **Standalone Sharpe understates the strategy — but only levered.** At 40%
    weight, with the trend leg volatility-targeted to 15% (median 4.6× notional
    in that leg, ~9% of portfolio capital in margin), the recommended blend lifts
    a portfolio from 0.63 to 1.02 and cuts the drawdown from −38% to −15% while
    *raising* return (10.7% → 11.4%). **Unlevered the same allocation gives up a
    third of the return** (7.6%), because a 3.2%-volatility leg cannot contribute
    enough risk to matter. Leverage is the precondition, not a detail — and
    futures margin is what makes it practical. The single-speed
    18/9/3 reads 1.06 / −14.4% on the same basis — within noise of each other.
    This is the argument that does not depend on the contested magnitudes: even
    at an out-of-sample standalone Sharpe of 0.6, a −0.2-beta leg with that
    drawdown profile still improves an equity portfolio.

## Methodological notes

- **Ragged panel by design**: eligibility is rebuilt each date, so markets join
  as history allows (10 markets in the 1980s, 29 by the 1990s, all 35 from 2000).
  Restricting to a common window would discard two decades.
- **Roll returns are masked, not repaired.** Datastream does not back-adjust: on
  a roll day `pct_change` compares the old contract yesterday with the new
  contract today. On the Bund that is a systematic −0.545% per roll, about
  −2.2%/year, which would push the signal toward short. The new contract's prior
  close is not in the series, so the value is masked. Details in
  `dataloader/ds_futures.py`.
- **Two real data defects were found and are regression-tested**: a zero
  settlement price on a holiday (silver, 2013-01-01) and one observation left in
  francs across the 1999 euro changeover (MATIF wheat, 1998-12-30, 762 vs
  neighbours of 116 and 120; 762 / 6.55957 = 116.2). Both are repaired by
  dropping the *price*, so `pct_change` spans the gap and recovers the true move.
- **Zero-volatility assets are dropped** by the `vol > 0` eligibility guard —
  necessary, since inverse-vol sizing would divide by zero. Synthetic test data
  for `scale=True` therefore needs real dispersion.
- **No look-ahead in the mixed-frequency path**: daily volatility is carried
  forward to each monthly formation date using only observations dated on or
  before it, regression-tested in `TestMixedFrequencyVol`.
- **Two ways to implement per-asset speeds give different answers, and one is
  wrong.** An early script ran two separate backtests — one on the 19 financial
  markets, one on the 16 commodity markets — and averaged the return series
  50/50. That reported 0.78 where the pooled implementation reports 0.82, for
  two reasons worth remembering. First, aligning the two sub-books on
  `index.intersection()` discarded **52 months**: the financial sub-book starts
  1983-11 (its latest-starting market gates it) while the commodity sub-book
  starts 1979-07, so the whole Volcker period was thrown away. Second, averaging
  50/50 silently imposes a **class-level risk budget** — the pooled book runs
  71/29 financial/commodity — so the script was changing two things at once and
  could not attribute either. The pooled version (a dict `lookback` on one book)
  changes only the speeds. Worth noting that the discarded variable is itself
  interesting: forced 50/50 class budgeting scored 0.91 in the second half
  against the pooled 0.88, so **class-level risk budgeting is a separate
  hypothesis still to be tested properly**, not a dead end.
- **Volatility targeting uses a lagged estimate** (`shift(1)`) and a 10× leverage
  cap; without the cap, low-volatility stretches imply implausible gearing. It
  also re-costs the levered weights so the leverage trade is charged — worth
  −0.01pp/year here, i.e. real but immaterial.

## References

- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, JFE.
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing*.
- Kim, Tse & Wald, *Time Series Momentum and Volatility Scaling*.
- Huang, Li, Wang & Zhou (2020), *Time Series Momentum: Is It There?*, JFE.
- See also [`cta-primer.md`](cta-primer.md) for how managed-futures funds
  implement this, and [`strategy-research-2.md`](strategy-research-2.md) §2.1
  and §2.4, which motivated the build.
