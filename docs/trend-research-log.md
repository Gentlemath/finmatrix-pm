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
- **The basket shrinks at the end of the sample** — 35 markets in 2010, 33 in
  2024, **28 by 2026**. Seven series stop carrying prices before the sample ends.
  See below; it does not move the headline but it invalidates any claim about the
  current book.

### CME Group data is gone: seven markets die before the sample ends

Discovered 2026-09-09, after the results below were computed. The monthly panel
runs to 2026-08, but seven of the 35 markets stop earlier — and they are
**exactly the seven CME Group markets**, 7 of 7, against 28 of 28 live elsewhere:

| market | class | last real price | stale for |
|---|---|---|---|
| **GOLD** | metal | 2022-11-30 | **3.8 yrs** |
| **SILVER** | metal | 2022-11-30 | **3.8 yrs** |
| US2Y, US5Y, US10Y, US30Y | bond | 2025-04-25 | 1.4 yrs |
| NATGAS | energy | 2026-04-02 | 0.4 yrs |

**The cause is that `tr_ds_fut` no longer carries any live CME Group content.**
A survey of every series priced within the three months before the 2026-09-09
check (cutoff 2026-06-01 — an arbitrary threshold, stated because "live" is
otherwise undefined) returns 40 exchange prefixes with three or more such
series — EUREX (328), NSE, LIFFE,
BSE, MEFF, HKFE, KSE, ICE, SFE, LME, TOCOM, ME, SGX, TAIFEX, MATIF and so on —
and **no CME, CBOT, ECBOT, COMEX, NYL or NYMEX entry anywhere**. The withdrawal
is staggered by exchange (COMEX 2022-11, CBOT 2025-04, NYMEX 2026-04), which is
what progressive content removal looks like rather than a re-keying.

So no search within this table recovers them. Two things were ruled out first:
no roll variant helps (all four `CS00`–`CS03` variants of all four Treasury
maturities die on the identical date; gold and silver `CS01`/`CS03` reach
2022-12-28, one month past `CS00`, and the mini `CY*` contracts are equally
dead), and the contracts are not present under new names (a deliberately wide
name search across all exchanges and currencies found no US-exchange candidate).

**The catalogue cannot detect this, and neither can `max(date_)`.** None of the
seven is flagged `DEAD` in `calcseriesname` — Datastream does use that flag, just
not here. Worse, `wrds_fut_series` keeps emitting rows after the prices stop, with
`settlement` NULL: gold has 13 such rows spread over 3.6 years, so
`max(date_)` reads 2026-06-26 while the last real price is 2022-11-30. Only
`max(date_) filter (where settlement is not null)` finds the truth. This cost two
wrong diagnoses before it was pinned down.

`fetch_series`, `clean_prices` and `to_monthly` all behave correctly here —
`bad_zero` and `bad_spike` are 0 for all seven, and `dropna(subset=["px"])`
discards the NULL rows exactly as it should. The data is genuinely gone.

**What this does and does not affect.** The window is 45 of 572 months, **8% of
the sample**, so the 45-year headline (Sharpe 0.92) is barely moved. But:

- **Precious metals are absent for the last 3.8 years.** Gold and silver are the
  only two in the basket, and the precious/industrial split is described below as
  "the load-bearing part" of the speed grouping. That finding has no
  out-of-sample support after 2022-11.
- **US rates are absent from the current book**, taking the bond class from 10
  live markets to 6 (AUS3Y, BOBL, BUND, GILT, JGB10Y, SCHATZ). Every
  point-in-time statement about the recent portfolio inherits this.
- **The 2026-08-31 snapshot** in the margin section holds 24 markets, and its
  AUS3Y-dominated position list is partly a consequence of the missing markets
  rather than of the strategy's choices.

**Substitutes, and they are better than what died.** Precious metals are
recoverable with *longer* history than the COMEX series ever had, in local
currency exactly as the basket convention requires:

| need | substitute | span | observations |
|---|---|---|---|
| GOLD | `JAUCS00` TOCOM-GOLD (JPY) | **1986-06** → 2026-09 | 9,832 |
| SILVER | `JSVCS00` TOCOM-SILVER (JPY) | **1984-01** → 2026-09 | 10,437 |
| NATGAS | `LNGCS00` ICE-NATURAL GAS (GBP) | 1997-02 → 2026-09 | 7,570 |

Against NYL gold's 2004-10 start, TOCOM roughly doubles the sample. Tokyo is a
major bullion market, so this is an upgrade rather than a compromise.

**US rates have no substitute** — no US-exchange bond future survives in this
table. What is available is more *sovereign* breadth to partly replace the lost
bond diversification: `AGDCS00` SFE-AU 10YR T-BOND (1984-12, 10,580 obs),
`CDGCS00` ME-10Y Canadian Govt Bond (1989-09, 9,128), `KTBCS00` KSE-3YR Treasury
Bond (1999-09, 6,642), `CGZCS00` ME-2YR Canadian Govt Bond (2004-05, 5,533). The
loss of US-specific rate exposure is real and permanent from this source.

**A separate bug surfaced in the same search.** The module records *"Dropped (no
usable variant in CS00–CS03): AUS10Y (~700 rows everywhere)"*. But `AGDCS00`
carries 10,580 observations from 1984-12. The original resolution searched the
pattern that matched AUS3Y — `SFE-AUST 3 YEAR T-BOND` — while the ten-year is
named `SFE-AU 10 YR T-BOND DAY CONT`. A 42-year bond series was excluded by a
naming mismatch, and should be added back.

### The CME data was never missing — only the continuous series lost it

`tr_ds_fut` has 20 tables; this project uses two. The continuous series
(`wrds_cseries_info` / `wrds_fut_series`) are a **derived** product. The
individual contracts they are stitched from live in `wrds_contract_info` /
`wrds_fut_contract`, and those **do** carry CME Group — 2,231 NYMEX, 679 CME,
559 CME E, 425 ECBOT contracts — with far more history than the derived series
ever had:

| market | contracts | first price | last settle | continuous series had |
|---|---|---|---|---|
| GOLD (COMEX) | 821 | **1977-08** | 2026-04-03 | 2004-10 → 2022-11 |
| US10Y (CBOT) | 179 | **1982-05** | 2026-04-03 | 1998-10 → 2025-04 |
| US5Y (CBOT) | 155 | 1988-05 | 2026-04-03 | 1998-10 → 2025-04 |
| NATGAS (NYMEX) | 1,213 | 1990-04 | 2026-04-03 | 1990-04 → 2026-04 |
| US30Y Ultra | 68 | 2010-01 | 2026-04-03 | 1998-09 → 2025-04 |

Every contract carries a settlement, and `volume` and `openinterest` are
populated for essentially all of them. Front-month open interest confirms these
are the right contracts: US5Y peaks at 6,803,094 contracts, US10Y at 5,611,437.

> **Resolved 2026-09-09, after two wrong turns.** The spans below were first
> obtained by matching `contrname`; a `clscode` check then suggested they were
> unattainable, because the basket's gold class (335) runs only 2004-10 →
> 2022-12. Both readings were incomplete. There is a **hierarchy** —
> instrument → class (`clscode`) → contract — and a single instrument carries
> several classes. The basket's continuous series pin each market to *one* class,
> and for the CME markets that class is deprecated. The long histories are real
> and sit in other classes of the same instrument. See *The classes are the fix*
> below.

**And they stitch with zero gaps.** Contract-level coverage was tested month by
month — for every month between first and last price, does any contract carry a
settlement? — because a long span with sparse early listings would not be
usable. It is fully covered:

| market | first | last | months | covered | gaps | contracts live at once (min) |
|---|---|---|---|---|---|---|
| SILVER 5000OZ | **1973-01** | 2026-04 | 640 | 640 | **0** | 8 |
| GOLD 100OZ | 1977-08 | 2026-04 | 585 | 585 | **0** | 3 |
| US10Y | 1982-05 | 2026-04 | 528 | 528 | **0** | 2 |
| US5Y | 1988-05 | 2026-04 | 456 | 456 | **0** | 2 |
| NATGAS | 1990-04 | 2026-09 | 438 | 438 | **0** | 11 |
| US30Y **Ultra** | 2010-01 | 2026-04 | 196 | 196 | **0** | 3 |

Against the ~218 months the continuous series gave gold and silver, this is
**2.7×** and **2.9×** more data. US10Y gains 1.7×.

**A consequence for the whole sample, not just these markets.** The basket
currently starts 1979-01 (cocoa). COMEX silver is priced from **1973-01**, so
rebuilding would extend the sample by six years — 572 months to 640+, a 12%
larger sample, and specifically in the high-inflation 1970s where trend
following is supposed to have performed best. That period is currently absent
altogether.

Roll choice is available throughout: at least two contracts are simultaneously
priced in every era for every market (US10Y runs a clean quarterly cycle, median
4 live; natural gas has a median of 259 after 2010).

### The classes are the fix, and "CME data is gone" was wrong

`tr_ds_fut` has a hierarchy this log missed for a long time:

```
instrument  (COMEX gold)
  └─ class      clscode 335  -> 2004-10 .. 2022-12, 218 months, DEAD
     class      clscode 1508 -> 1977-08 .. 2026-04, 584 months, 29 unexpired
       └─ contract   NGC0926, expires 2026-09-28
            └─ prices  wrds_fut_contract
```

A continuous series pins its market to **one** class. For the CME markets that
class is deprecated — but the instrument's other classes are intact. Comparing
every class of each basket market's instrument:

| market | basket class | better class | months: now → better | staleness: now → better |
|---|---|---|---|---|
| **SILVER** | 3607 | **1574** (1973-01 →) | 218 → **639** | 1351d → 159d |
| **GOLD** | 335 | **1508** (1977-08 →) | 218 → **584** | 1351d → 159d |
| **US30Y** | 330 | **2441** (1977-08 →) | 319 → **584** | 502d → 159d |
| **US2Y** | 342 | **2523** (1990-06 →) | 319 → **430** | 502d → 159d |

All four are the same instrument on the same exchange, reached by a different
`clscode`. Silver nearly triples, gold nearly doubles, and US30Y turns out to run
from **1977-08** — the classic 30-year bond, not the 2010 Ultra contract an
earlier draft confused it with.

**What remains true:** every CME class still stops at 2026-04-03, so the feed
cutoff is real and no class reaches the sample end. **What was wrong:** the
conclusion that these markets were permanently lost. Recovering 2022-12 → 2026-04
for the metals, 2025-04 → 2026-04 for the bonds, and roughly tripling the history
is a different outcome entirely.

**Method note, because this cost four wrong conclusions.** In order, I claimed:
the series were dead (right, badly evidenced); it was a pipeline bug (wrong —
`max(date_)` counts NULL-settlement rows); CME data is absent from WRDS (wrong —
only from the *derived* series); and the long histories were unattainable (wrong
— they are in other classes). Every error came from trusting a proxy for the
thing actually wanted: `max(date_)` for "last price", `contrname` for identity,
one `clscode` for "the instrument". The reliable procedure is to resolve identity
by key, verify against price data rather than metadata, and check whether the key
is one-to-one before assuming it.

**All four US Treasuries have upgrades, in a second naming family.** The
`... US TREASURY NOTE` names carry only the deprecated classes; the live ones sit
under `... US T-NOTE COMP.`, which the first scan never saw because it compared
only classes sharing the basket's own `contrname`:

| market | basket class | better class | mnem | months: now → better |
|---|---|---|---|---|
| US30Y | 330 (`CZB`) | **2441** (`CUB`) 1977-08 → | CUB | 319 → **584** |
| US10Y | 338 (`CZN`) | **3896** (`CTT`) 1982-05 → | CTT | 318 → **527** |
| US5Y | 334 (`CZF`) | **1997** (`CTF`) 1988-05 → | CTF | 318 → **455** |
| US2Y | 342 (`CZT`) | **2523** (`CTE`) 1990-06 → | CTE | 319 → **430** |

Three parallel families exist per maturity: `CZ*` (what the basket uses, dead
2025-04), `CT*`/`CU*` (live to 2026-04), and a third dead since 2015. The
contract `CTT0926` — a ten-year note expiring 2026-09-21, unexpired as of this
writing — belongs to class 3896, which is why it was invisible while querying 338.

**The other three flagged "upgrades" were false positives**, caught by checking
currency and mnemonic prefix rather than name:

| market | basket | flagged | verdict |
|---|---|---|---|
| NATGAS | 1539 USD `NNG` Henry Hub | 3756 **GBP** `LNG` | ICE UK gas — different market |
| CORN_MAT | 3836 EUR `PCO` MATIF | 2216 **JPY** `JCN` | Tokyo corn — different market |
| WHEAT_LIF | 1295 GBP `LWH` LIFFE | 1405 **USD** `MMW` | US wheat — different market |

So **NATGAS has no upgrade** — 1539 is already the best Henry Hub class and
simply stops at the CME cutoff. Any future class swap must verify currency and
mnemonic family, not just the name; `contrname` alone would have silently
replaced Paris corn with Tokyo corn.

**A genuine addition, not an upgrade:** clscode 2420, USD `CCF` — CBOT corn,
1973-01 → 2026-04-03, 639 months. The basket carries only MATIF corn from
1999-10. Worth adding on its own merits.

**Contract-identity warning.** `ULTRA T-BOND` is a contract introduced in 2010,
**not** the classic 30-year T-Bond the basket used
(`ECBOT-30 YEAR US T-BOND CONT.`, priced 1998-09). An earlier draft of this
section compared the two as though they were the same instrument. Exact names
for the 2-year note and the classic 30-year bond are still unresolved — the
naming is inconsistent even among the ones that resolve (`5 YEAR US T-NOTE
COMP.` beside `10 YRS US T-NOTE COMP.`), so they must be found by search rather
than by analogy.

**The hard limit is 2026-04-03.** Every CME market's last settlement is that same
date — five months before the 2026-09-09 check — so the contract tables do not
reach the sample end either, and for these markets there is no current price at
all. Note that unexpired CME contracts remain *listed* well beyond that date;
listing and pricing are different things, and conflating them produced a
"currently trading" table in an earlier draft that consisted entirely of expired
contracts. This also
explains the staggered continuous-series deaths: Datastream stopped maintaining
the derived series per-market at different times while the contract feed ran on
until it ceased entirely.

**Why rebuilding from contracts would be worth more than restoring seven
markets.** Three defects recorded elsewhere in this log are artifacts of using a
vendor-stitched series, and all three dissolve:

- **Roll returns are currently discarded.** `mask_roll_returns` throws away one
  return per roll — 4.64 rolls/year per market — because the vendor series is not
  back-adjusted and the roll-day `pct_change` compares two different instruments.
  With both contracts' prices at the roll the true return is computable, which
  also closes the roll-yield question flagged as "not determinable from this
  data".
- **The roll rule is fixed and suboptimal.** CS00 means "switch on the first day
  of the new month"; the log measures 7–10 days of Bund exposure left on a
  contract still holding 1.43M contracts of open interest. With `openinterest`
  per contract, rolling on liquidity — the managed-futures convention — becomes
  testable rather than unavailable.
- **Gold's history nearly triples**, 1977-08 against 2004-10, which matters
  because precious metals carry the load-bearing part of the speed grouping and
  currently have the shortest history of any slow-group market.

Not yet done. Two known traps for whoever does it: contract names need the same
careful resolution as the continuous series (gold has a retired `CZG*` family —
`CZG0626` last priced 2021-12-13 with zero open interest — alongside the live
`NGC*` one), and a `SILVER%` name search picks up TOCOM, DGCX and MCX contracts,
so COMEX silver still needs verifying specifically.

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

Futures make this practical: at a 15% target the book consumes **8% of capital
in margin at the median and never more than 14%**, because exchange margin tracks
contract *risk* and inverse-volatility sizing puts the large notional in the
low-risk contracts. Doing the same with ETFs would require actual borrowing. This
is the capital-efficiency argument for futures, quantified — see *Risk, margin and
cost of actually running this* below for the derivation, and note that an earlier
version of this paragraph used a flat percent-of-notional model that overstated
the requirement by 3–8×.

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

The table above is the **unlevered** book. The same sensitivity at a 15%
volatility target, what the 2 bps assumption is actually worth contract by
contract, and the roll cost and yield this model omits entirely, are all in
*Risk, margin and cost of actually running this* below. Short version: 2 bps is
roughly 5× too conservative for the liquid financial futures, and roll days are
treated as return-neutral so an uncharged cost of the same order as signal
turnover is missing; the two errors largely cancel.

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

**What the leverage costs to hold — and why the median understates it.** Two
different quantities get confused here, so both are stated. The leverage
*multiplier* is well behaved; the *gross notional* it produces is not, because
inverse-volatility sizing makes the unlevered book's own exposure swing between
1× and 5× (a 1.3%-volatility Schatz position alone can consume most of it):

| Per unit of trend-leg capital | median | 95th pct | worst |
|---|---|---|---|
| leverage multiplier | 4.6× | 5.8× | 6.3× |
| unlevered gross notional | 1.0× | 2.7× | 5.0× |
| **levered gross notional** | **4.6×** | **13.3×** | **23.7×** |

Both factors vary, so the tail of their product is far fatter than the product of
the medians — 13.3× against 4.6×. Margin as a share of total portfolio capital
for a 60/40 mix, under both models:

| margin, share of portfolio capital | median | 95th pct | worst |
|---|---|---|---|
| flat 5% of gross notional | 9% | 27% | 47% |
| **risk-based** (see derivation below) | **3.2%** | **4.5%** | **5.6%** |
| overstatement | 2.9× | 5.9× | 8.4× |

**How these numbers are built.** Three inputs, only one of which is measured:

| input | value | status |
|---|---|---|
| median levered gross notional, per unit of trend-leg capital | 4.6191× | **measured**, 566 months |
| blended margin rate | 5% of notional | **assumed** — the weak link |
| trend-leg allocation | 40% | a **choice** |

```
$1,000,000 portfolio × 40%   = $400,000     trend-leg capital
$400,000 × 4.6191            = $1,847,633   futures face value
$1,847,633 × 5%              = $92,382      margin
$92,382 / $1,000,000         = 9.24%        of portfolio capital
```

i.e. `4.6191 × 0.05 × 0.40 = 9.24%`. The 4.6191× is the *median of the monthly
product* `Σ|w_i × lev_t|`, not the product of the medians — `0.9840 × 4.5711 =
4.50`, which is why those two figures do not tie to 4.62.

The **risk-based** column replaces only the margin-rate step, pricing each
position as `K × sd_i × notional_i` with `K = 3.5`, then summing: median
8.07% of trend-leg capital, × 40% = **3.23%**. The 2.9× gap decomposes cleanly —
the flat model charges 5% on every position while the risk model averages **1.50%**
of notional, because the large notional sits in the low-volatility contracts, and
5.0 / 1.50 = 3.3×.

`K = 3.5` is a choice, not a derivation: a two-day 99% move is `2.33 × √2 = 3.30`,
rounded up. Halve `K` and every risk-based margin figure here halves.

**The same thing in dollars**, which is the only framing that answers whether the
position is fundable. $1,000,000 portfolio: $600,000 in equities and **$400,000 in
the trend leg, held as T-bills.** All margin comes out of that $400,000.

| | median | 95th pct | worst |
|---|---|---|---|
| *flat 5%-of-notional model* | | | |
| margin required | $92,382 | $265,840 | **$474,061** |
| as % of the $400k leg | 23% | 66% | **119%** |
| T-bills left free | $307,618 | $134,160 | **−$74,061** |
| *risk-based model* | | | |
| margin required | $32,298 | $44,819 | **$56,313** |
| as % of the $400k leg | 8% | 11% | **14%** |
| T-bills left free | $367,702 | $355,181 | **$343,687** |

Under the flat model the worst month needs $474,061 against a $400,000
allocation, so the equity sleeve has to be sold to post collateral — that is the
margin call. Under the risk-based model the worst month in 45 years uses 14% of
the allocation and leaves $343,687 free. Nothing is ever forced.

The reason is the same timing observation, with the sign corrected.
**`corr(gross notional, average asset volatility) = −0.62`**: gross notional is
`Σ(1/σᵢ)`, so it peaks precisely when volatility is low. Margin is the *product*
of exposure and volatility, so the two factors offset rather than compound. The
tail in gross notional is real; the tail in the funding requirement is not.

Two corrections are recorded here rather than deleted, because both were made in
this log and both are instructive:

- An early draft called 9% "comfortable, with room for the 95th-percentile
  leverage of 5.9×". Wrong quantity: 5.9× is the *multiplier*, which barely moves
  (4.6× → 6.3×), not the gross notional, which triples.
- The correction to that then asserted a margin call at the 95th percentile,
  and was wrong twice over. It priced margin as a flat percentage of notional —
  once margin is priced on risk the requirement is nearly flat across the
  gross-notional distribution (see *Margin: notional-based models overstate it by
  3–8×* below). And even within the flat model the named percentile was wrong:
  the 95th needs 66% of the trend allocation, which is affordable; only the single
  worst month exceeds it.
- Both of those errors shared a hidden premise — "an account funded to the
  median" — which imagines earmarking exactly the median requirement and
  deploying the rest. Nothing else in this log describes the 60/40 mix that way.
  Funded as described, the whole 40% sits in bills and there is nothing to fall
  short of until the requirement exceeds 40%. State the capital actually
  available before claiming a shortfall against it.

**What survives from that argument** is the risk observation, not the funding
one: exposure peaks when realised volatility has been low, and that is exactly
when a backward-looking estimator is most likely to be about to understate risk.
That is a statement about vulnerability to a regime break — the lagged-estimator
exposure noted throughout this log — and it is unaffected by how margin is
computed.

This is only practical with futures; the same position in ETFs would require
actual borrowing at a real financing cost, which none of these figures include.

Note the Sharpe convention: futures are self-financing (margin embeds the
funding), so `rf=0` is the correct excess Sharpe for the strategy. Equity
buy-and-hold must have cash subtracted, or its Sharpe is inflated — SPY reads
0.74 at `rf=0` against 0.63 properly measured.

## Risk, margin and cost of actually running this

Everything above measures the return series. This section measures the *account*
— what the daily and monthly cash flows look like, how much collateral is
pledged, and what execution really costs. All figures are the recommended
configuration at a 15% volatility target (Sharpe 0.92, 13.76%/year, 15.43%
realised volatility, −24.7% maximum drawdown), 1981-01 to 2026-08, 548 months
and 11,829 trading days, on a notional $1M account.

The daily figures come from applying each month's *levered* weights to the daily
return panel — the honest representation of the book, because contract counts are
set at the monthly rebalance and then frozen for the rest of the month.

### Monthly outcomes

**Normal months.**

| | |
|---|---|
| median | **+0.95%** |
| mean | +1.18% |
| standard deviation | 4.45% |
| 25th / 75th pct | −1.50% / +3.74% |
| 5th / 95th pct | −5.44% / +8.66% |
| win rate | 61.7% |
| months spent in drawdown | 69% |

**Extreme months.**

| | | |
|---|---|---|
| worst month | **−23.2%** | 1981-01 |
| 2nd worst | −11.4% | 2001-04 |
| 3rd worst | −11.3% | 1999-05 |
| best month | **+18.1%** | 2008-10 |
| 2nd best | +17.6% | 2019-08 |
| worst rolling 12m | **−20.6%** | to 1981-12 |
| best rolling 12m | +77.2% | to 1997-07 |
| maximum drawdown | **−24.7%** | trough 1990-05 |

Two features of this distribution matter more than the summary statistics.

**The strategy is in drawdown 69% of the time.** A 0.92 Sharpe does not mean a
smooth ride; it means a small positive drift with a positively skewed tail. The
median month is +0.95% and the win rate is only 61.7%, so most of the return
arrives in the +8% to +18% months. Sitting under water two-thirds of the time is
the normal state of this strategy, not a warning sign.

**The worst month, −23.2% in 1981-01, is nearly the entire maximum drawdown in
one observation.** That month had only ten markets trading and the volatility
estimator was still warming up. It is the single most influential observation in
the sample and it sits in the least reliable part of it.

### Daily outcomes

| | | on $1M |
|---|---|---|
| \|daily\| median | 0.48% | $4,807 |
| \|daily\| 90th pct | 1.37% | $13,661 |
| \|daily\| 95th pct | 1.75% | $17,528 |
| \|daily\| 99th pct | 2.71% | $27,064 |
| daily sd | 0.87% | (13.9% annualised — consistent with the 15% target) |
| **worst day** | **−7.65%** | **−$76,455** (2021-11-26) |
| best day | +7.06% | +$70,578 (2008-10-06) |
| worst 2-day | −9.37% | −$93,705 (to 2008-10-14) |
| worst 5-day | −10.95% | −$109,550 (to 2007-03-05) |
| worst 20-day | −14.86% | −$148,590 (to 2006-06-08) |

The worst day is 8.8 daily standard deviations. That is not a fat-tail artifact of
a single contract — it is what happens when a one-way book meets a coordinated
reversal, which is the characteristic failure mode of trend following and is
discussed under crisis alpha above.

### Intra-month: the path inside a frozen book

Because contract counts are frozen between rebalances, the intra-month path is
not something the strategy can respond to. Both measures below are computed on
the daily NAV path within each calendar month:

| | median | 5th pct | 1st pct | worst |
|---|---|---|---|---|
| peak-to-trough (a drawdown) | −2.78% | −8.02% | −11.48% | −13.99% |
| **start-to-trough** (an actual loss from the rebalance) | **−1.37%** | −6.89% | −10.61% | **−13.14%** |

The distinction is load-bearing and an earlier draft of this log got it wrong.
Peak-to-trough measures a drawdown from an intra-month high, which may sit above
the rebalance level; start-to-trough measures the loss against the equity the
account actually had when the position was set. **For margin purposes only
start-to-trough matters**, because a margin call tests equity against the
requirement in absolute terms, not against a high-water mark. The worst
start-to-trough months were 2019-09 (−13.1%), 2001-11 (−11.7%), 2001-04 (−11.0%)
and 2018-02 (−10.9%).

Reproduce with `examples/trend_intramonth_demo.py`; pass a month
(`... 2020-03`) to print that month's daily NAV path.

### Margin: notional-based models overstate it by 3–8×

The natural first model — margin is a few percent of gross notional — is wrong
here, and wrong in a direction that makes the strategy look infeasible when it
is not.

**The reason is structural, and it needs no model to see.** Margin is set **per
contract**, from that contract's own risk, and then summed across the portfolio.
That is the shape of SPAN and of every system that succeeded it. Real margin
rates therefore vary by roughly an **order of magnitude** across a diversified
basket — short-dated bond futures sit near 0.3–0.6% of notional, energy and softs
near 7–17%. **That alone means no single percentage applied to total gross
notional is the right shape of model**, whatever number is chosen for it.

It fails in a predictable direction here, because inverse-volatility sizing
deliberately puts the *largest notional in the lowest-risk contracts* — precisely
the ones carrying the smallest margin rates. A blended rate calibrated to the
average *contract* is far too high for a book whose notional is concentrated in
the cheap tail. (Measured on this basket: the equal-weighted margin rate across
markets is 5.1%, while the notional-weighted rate is 1.5%. The flat model's 5% was
a reasonable guess at the first number and was then applied to the second.)

**Everything above is exchange practice. What follows is an estimate of the
resulting error, and it carries a model.** Pricing each position as

```
margin_i = K × sd_i × |notional_i|        K = 3.5
```

where `sd_i` is asset *i*'s **daily** return standard deviation and `K = 3.5`
approximates a two-day 99% adverse move (`2.33 × √2 = 3.30`, rounded up) — the
rough basis exchanges use:

| Gross notional percentile | flat 5% of gross | risk-based | overstatement |
|---|---|---|---|
| median | 23.1% | **8.1%** | 2.9× |
| 90th | 58.6% | 10.7% | 5.5× |
| 95th | 66.5% | **11.2%** | 5.9× |
| 99th | 95.4% | 12.5% | 7.6× |
| max | 118.5% | **14.1%** (2020-03) | 8.4× |

The flat model implies the requirement exceeds capital in 0.91% of months —
i.e. that the strategy is unimplementable. On the risk-based model it never
exceeds 14.1%. **The infeasibility was an artifact of the wrong margin model.**

The per-position detail below is **modelled output, not observed exchange
margin** — the last two columns are computed from the daily-standard-deviation
column via `K × sd_i × notional_i`.

Snapshot: the rebalance of **2026-08-31**, the last in the panel, on a notional
$1M account. That month held **24 of the 35 markets** (the rest had no signal),
at 7.13× gross notional against a 4.62× median — so it is a high-exposure month,
not a typical one. The `daily sd` column is the 126-day rolling standard
deviation over 2026-03-04 to 2026-08-26. The rows are the three largest and two
smallest positions by notional, chosen to show the range rather than as a sample:

| market | notional | daily sd | *modelled* margin | *implied* rate |
|---|---|---|---|---|
| AUS3Y | $2,147,995 | 0.06% | $4,383 | 0.2% |
| SCHATZ | $1,293,204 | 0.10% | $4,549 | 0.4% |
| BOBL | $596,641 | 0.22% | $4,536 | 0.8% |
| ORANGEJUICE | $27,226 | 4.47% | $4,260 | 15.6% |
| KOSPI200 | $27,453 | 4.78% | $4,592 | 16.7% |

**And the near-equality of the margin column is arithmetic, not evidence.** If
`notional_i ∝ 1/σ_i` (the sizing rule) and `margin_i ∝ σ_i × notional_i` (the
proxy), then `margin_i` is constant identically. The measured $4,471 ± $171
across the 24 held positions is that identity reappearing, not a discovery. It
tells us the *sign* of the effect is right — real margin does rise with contract
risk, so the offset against inverse-volatility sizing is genuine — but the
tightness of the equalisation is an artifact of assuming margin is exactly linear
in the standard deviation. Real requirements include floors, stress buffers and
liquidity add-ons that break that linearity, which is the anti-procyclicality
point below.

Read the conclusion accordingly: **total margin is far closer to constant across
the gross-notional distribution than a flat percentage implies, and the flat
model overstates the requirement by something in the region of 3×.** The
direction is solid; the multiple is an estimate. Gross notional of 7.13× ($7.1M
on $1M) is modelled to consume $106,996 — 10.7% of capital — against $356,685
under the flat model.

This corrects the "a 4.4× notional book consumes roughly a quarter of capital in
margin" estimate under the leverage section above, which used the flat model.

**This is a proxy, not an industry standard — and the gap runs both ways.**

No clearinghouse computes margin as a multiple of trailing volatility. The real
systems are scenario engines: SPAN (16 risk-array scenarios per contract), SPAN 2
(historical Value at Risk plus stress and liquidity add-ons), Eurex Prisma
(filtered historical VaR), OCC STANS (Monte Carlo). What *is* conventional is the
**target** — CPMI-IOSCO's Principles for Financial Market Infrastructures require
99% coverage over an appropriate close-out period, and EMIR specifies 99% over two
days for exchange-traded futures, which is where `2.33 × √2` comes from. The
objective is standard; the method here is a back-of-envelope stand-in.

Two omissions push the estimate **down**: SPAN inter-commodity credits (which this
book barely earns — see below) and the normality assumption, which understates
fat tails.

One omission pushes it **up, and it is the important one.** Regulators mandate
**anti-procyclicality**: margin floors, stress-period buffers, and long lookbacks
(EMIR requires e.g. a 25% buffer, or a 10-year window including stressed
observations) precisely so requirements do not collapse in calm markets and spike
in a crisis. This model has margin falling whenever volatility falls — exactly
what the rules forbid. Re-running under progressively more conservative
specifications:

| specification | median | 95th | max |
|---|---|---|---|
| this proxy (126-day sd) | 8.1% | 11.2% | **14.1%** |
| 10-year lookback | 8.6% | 14.5% | 20.5% |
| anti-procyclical `max(126d, 10y)` | 9.4% | 14.9% | 20.6% |
| **+ 25% EMIR-style buffer** | 11.7% | 18.6% | **25.7%** |

It bites hardest exactly where this section claimed safety — the calm,
high-gross months of 2020–2021, where an anti-procyclical requirement is
**1.25–1.43× this proxy** (2021-02: 9.2% → 12.8% → 16.1% at 23.7× gross). The
model reads those months as cheap because short-rate volatility had collapsed; a
clearinghouse with a ten-year lookback refuses to recognise the calm.

**The funding conclusion survives, with roughly half the headroom.** For the
60/40 mix the worst month moves from $56,313 (14% of the $400,000 trend
allocation) to $102,909 (26%). Nothing is forced under any of the four
specifications — but "never near a call" was too confident, and too confident in
the direction that partially rehabilitates the concern retracted above.

### SPAN offsets: this book barely earns any

SPAN (Standard Portfolio Analysis of Risk, the CME system used by most
exchanges) computes margin on portfolio risk rather than leg-by-leg, and grants
**inter-commodity credits** for offsetting positions. Two structural facts mean
this basket collects very little of that:

**Credits do not cross clearinghouses.** The 35 markets clear at roughly eleven
different clearing organisations (CME Group, Eurex Clearing, ICE Clear Europe,
ICE Clear US, LME Clear, LCH/Euronext, HKEX, KRX, JPX, ASX, SGX). A long CME
Treasury position and a short Eurex Bund position are near-perfectly hedged
economically and attract no offset at all.

**A trend book is directionally one-way.** SPAN credits reward holding one leg
long and a correlated leg short. Trend following in a coherent regime holds the
whole complex in the same direction. Measuring `|net| / gross` within each
clearing group (1.00 = fully one-way, no offset available):

| clearer | markets | % of gross | \|net\|/gross median | months >0.9 |
|---|---|---|---|---|
| Eurex | 5 | 20.7% | **1.00** | 54% |
| CME | 7 | 18.1% | **1.00** | 63% |
| ASX | 2 | 14.8% | **1.00** | 48% |
| ICE-US | 6 | 8.9% | 0.41 | 15% |
| ICE-EU | 5 | 7.2% | 0.57 | 29% |
| LME | 4 | 1.9% | 1.00 | 49% |
| LCH | 2 | 0.9% | 1.00 | 48% |
| single-market clearers | 4 | 7.0% | n/a | n/a |

The three groups carrying 54% of gross are fully one-way. Only the two ICE
groups (16% of gross combined) hold genuinely two-sided positions.

**This is a real asymmetry in the diversification argument.** The basket's
effective breadth of 12.7 independent directions is what produces the 0.92
Sharpe — diversification pays on the *return* side. It does not pay on the
*margin* side, because SPAN keys off clearing structure and position direction
rather than economic correlation. Lowering portfolio volatility does not lower
capital consumption proportionally.

### Daily clearing: what actually moves

Two distinct things are called margin and they behave differently:

| | what it is | T-bill eligible? |
|---|---|---|
| Initial / maintenance margin | a performance bond; still the account's asset, still earning | **yes** (with a haircut) |
| **Variation margin** | daily cash settlement of the day's mark-to-market | **no — cash only** |

Variation margin is computed against the **previous day's settlement price**
(against the fill price on the day of entry) and settled in cash. So futures carry
no unrealised profit or loss: each day's move is paid or collected, and the cost
basis resets to the new settlement every day. This is why a futures return series
is a pure price-return series with no accrual, and why `rf = 0` is the correct
Sharpe convention — the funding embedded in the futures price and the yield on
posted collateral cancel.

Cash for a call is sourced, in order: excess cash in the account; the clearing
broker's overnight credit against posted collateral; repo of the T-bill holdings;
a wire from the bank; and, failing all of those, forced liquidation by the broker
at its discretion. Exchanges can also call **intraday** in fast markets rather
than waiting for the settle, and brokers generally require a cushion above the
exchange minimum ("house margin").

The implied balance sheet on a $1M account at a 15% volatility target:

| | share of capital | form |
|---|---|---|
| margin (95th pct, risk-based) | 11.2% | T-bills |
| cash sleeve for variation margin | ~4% | cash |
| unencumbered | ~85% | T-bills, free |

The 4% cash sleeve covers the 99th-percentile daily outflow ($27,064, 2.7%) with
room to spare, and is self-replenishing because winning days pay *in*. It is
drawn down only during a losing run — the worst two-day run is $93,705 (9.4%),
which requires selling T-bills (T+1) or drawing on the broker. Note that the
collateral yield is **additive**, not forgone: the account earns the T-bill yield
on the whole balance *and* the 13.76% futures overlay, which is why the Sharpe is
invariant to the assumed cash rate.

The unrecorded cost here is the cash sleeve's yield give-up: ~4% of capital at
whatever the bill yield is, or roughly **0.08%/year at a 2% rate**. Immaterial
against 13.76%.

### The cost stack

Per-contract fees are **flat dollars** — the same $2 whether the contract is worth
$22,000 or $490,000 — and therefore convert to wildly different basis points.
Assuming $3.50 per contract round turn all-in (brokerage commission + exchange +
clearing + regulatory):

| contract | notional | flat fees (bp) | half-spread (bp) | total per side |
|---|---|---|---|---|
| DAX | $490,000 | 0.04 | 0.13 | **0.16** |
| S&P e-mini | $275,000 | 0.06 | 0.23 | 0.29 |
| Gold | $240,000 | 0.07 | 0.21 | 0.28 |
| Bund | $145,000 | 0.12 | 0.34 | 0.47 |
| US 10Y | $110,000 | 0.16 | 0.71 | 0.87 |
| WTI | $75,000 | 0.23 | 0.67 | 0.90 |
| NatGas | $30,000 | 0.58 | 1.67 | 2.25 |
| Sugar | $22,400 | 0.78 | 2.50 | 3.28 |
| Corn | $22,500 | 0.78 | 2.78 | **3.56** |

**Commissions are nearly irrelevant** — at most 0.8 bp, on the smallest contract.
The cost is the bid-ask spread, and its basis-point value is set by contract
notional. The half-spread convention measures cost against mid: a market order
buys at the ask, one half-spread above mid, so a round trip pays the full spread —
which is consistent with `transaction_costs` charging `Σ|w_t − w_{t−1}|` once per
side.

So **the 2 bps per side used throughout this log is conservative** — roughly 5×
too high for the liquid financial futures that carry most of the gross, and
slightly too low for the small agricultural contracts.

#### Does leverage change cost sensitivity?

Two separable effects, and only one of them is real.

| cost per side | unlevered | constant 4.6× | vol-targeted 15% |
|---|---|---|---|
| 2 bps | 0.904 | 0.904 | **0.917** |
| 5 bps | 0.866 | 0.866 | 0.874 |
| 10 bps | 0.804 | 0.804 | **0.803** |
| **spread, 2→10 bps** | **0.100** | **0.100** | **0.114** |

**Constant leverage changes nothing, exactly.** Since

```
net_L = L·gross − cost·Σ|Δ(L·w)| = L·(gross − cost·Σ|Δw|) = L · net_1
```

leverage scales numerator and denominator identically and `Sharpe(L·X) = Sharpe(X)`.
Verified numerically: `max|net_L − 4.57·net_1| = 2.8e-17`. Only annual return
moves, 3.3% → 14.8%. So the unlevered cost table above transfers to any
*constant* gearing without adjustment.

That invariance is a property of the **cost model**, not of leverage, and it
holds only because costs here are strictly proportional to notional traded. Two
real components break it in opposite directions:

| cost structure | Sharpe at 1× → 10× | why |
|---|---|---|
| proportional only (as modelled) | 1.070 → 1.070 | cost/return ratio fixed |
| plus a **fixed** charge | 1.012 → 1.065 | flat fees diluted by a bigger book |
| plus **market impact** (`∝ size^1.5`) | 1.059 → 1.033 | trading more moves the price |

Neither is modelled. At $1M the impact term is negligible — the account trades
fractions of a contract — so the identity is a good approximation there; it
degrades as size grows. The fixed-fee term works the other way and favours scale.
Do not read the invariance as a claim that leverage is free.

**Time-varying leverage makes cost bite about 14% harder**, 0.114 against 0.100.
Mean leverage is 4.40× but two-way turnover rises 4.79× — the extra 0.39× is the
leverage trade itself, turnover a constant multiplier never generates, incurred
by moving from 5.50× to 5.38× as the volatility estimate drifts. It is charged at
full cost while the target pins realised volatility at 15% regardless, so the
drag hits the numerator with no offsetting reduction in the denominator.

**The consequence is that volatility targeting's Sharpe bonus is cost-fragile.**
The 0.904 → 0.917 gain attributed to incidental volatility timing under the
leverage section above is entirely consumed by 10 bps execution (0.803 vs 0.804).
It survives at futures-like costs and disappears at ETF-like costs — a sharper
form of the rule that instrument comparisons must use each instrument's own cost.

Two things this does not capture. **Market impact**: the half-spread applies only
if the order fits inside the resting quote, which is comfortable at $1M and not at
$1B. And **adverse selection on passive execution**: resting a limit order to earn
the half-spread instead of paying it works, but fills arrive preferentially when
the price is about to move against you, so the expected saving is smaller than the
quoted half-spread.

### Rolls: cost and yield, both excluded

Futures expire. Holding a trend position for nine months means closing the
expiring contract and opening the next one every quarter or so — same market,
same direction, same size. The economic position is unchanged; the trade is real.

**Two distinct things are called "roll" and this log needs both named.**

| | what it is | sign |
|---|---|---|
| **roll cost** | spread + fees paid to execute the swap | always negative |
| **roll yield** | the price gap between the expiring and next contract (contango / backwardation) | either — it is a *return*, not a friction |

Roll yield is not a cost. In contango a long holder rolls into a higher price and
gives that up; in backwardation they collect it. It is the basis of commodity
carry strategies and a genuine P&L component.

**This construction excludes both.** `mask_roll_returns` deletes the roll-day
return, because Datastream does not back-adjust and the roll-day `pct_change`
compares two different instruments — a measured −0.545% mean signed artifact on
the Bund. `to_monthly` then compounds with `fillna(0.0)`, so **every roll day
contributes exactly zero return**. That is the right treatment of the data
artifact and it is the only treatment available from this series, but it means:

- the roll **cost** is never charged — unambiguously flattering;
- the roll **yield** is never earned — ambiguous in sign, and not recoverable
  from this data, which carries one stitched series per market rather than the
  two contract prices a basis calculation needs.

Whether excluding roll yield biases the trend result up or down is **not
determinable here.** There is a plausible mechanism for it mattering — a
backwardated market tends to be one that is trending up, so roll yield may
correlate with the signal — but this sample cannot test it. Flagged, not
resolved.

The rest of this subsection prices only the *cost* half. `transaction_costs`
charges `Σ|w_t − w_{t−1}|`, and a roll leaves the weight unchanged, so the model
sees no trade. Gross-weighted, the basket rolls **4.64 times a year** per market
(range 3.8 to 12.2):

| annual notional traded, capital = 1 | |
|---|---|
| signal turnover (weights changing) | 22.14× |
| **rolls (position unchanged, trade required)** | **25.88×** |

Roll trading slightly exceeds signal turnover. The mitigant is that a roll
executes as a **calendar spread** — a single instrument, quoted far tighter than
two outright legs, with discounted exchange fees — so the right per-roll
assumption is 0.5–1 bp, not two outright half-spreads:

| per-roll cost | annual drag | Sharpe | ann.ret |
|---|---|---|---|
| none (as backtested) | 0.00% | **0.92** | 13.8% |
| 0.5 bp | 0.13% | 0.91 | 13.6% |
| 1 bp | 0.26% | 0.90 | 13.5% |
| 2 bp | 0.52% | 0.88 | 13.2% |
| 4 bp (upper bound) | 1.04% | 0.85 | 12.6% |

**Verdict: the omission is real but costs 0.01–0.02 Sharpe** at realistic
calendar-spread pricing, and it is more than offset by the 2 bps outright
assumption being ~5× too conservative on the contracts carrying most of the
gross. The two modelling errors point in opposite directions and roughly cancel.
That is luck, not design, and both should be priced explicitly in any future
version.

### Integer contracts: a $1M account cannot hold this book

Futures trade in whole contracts. At $1M and the most recent weights, several
positions are fractions of one contract:

| market | notional implied | contract size | contracts |
|---|---|---|---|
| DAX | $107,937 | ~$490,000 | **0.22** |
| NIKKEI225 | $58,055 | ~$150,000 | 0.39 |
| COPPER | $103,967 | ~$225,000 | 0.46 |
| SPI200 | $136,503 | ~$180,000 | 0.76 |
| ESTOXX50 | $108,537 | ~$60,000 | 1.81 |
| BUND | $387,867 | ~$145,000 | 2.67 |

Rounding to whole contracts means either dropping those markets — which destroys
the breadth the whole result rests on — or holding them at 0 or 1, which is a
±100% sizing error on the position. Neither is what the backtest assumes.

The practical thresholds: micro and mini contracts exist for several of these
(Micro E-mini equity indices, MicroBund) and push the minimum viable account down
substantially, but not for all 35. Trading this basket at full breadth with
sizing error under ~10% requires roughly **$10–20M**. Below that, the honest
version is a reduced basket, and the reduced-basket Sharpe is not measured
anywhere in this log.

This is the single largest gap between these results and a $1M account, and it is
larger than every cost effect in this section combined.

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
- **Basket survivorship, at both ends.** The 35 markets were selected for having
  long, clean Datastream histories. Contracts that were delisted or never got
  liquid are absent, and the FX leg is thin because the FINEX contracts died. At
  the *recent* end, seven series stop carrying prices before 2026-08 (gold and
  silver from 2022-11, the four US Treasuries from 2025-04, natural gas from
  2026-04), so the live basket is 28 markets, not 35 — see *Seven series die
  before the sample ends* above. Precious metals, which the speed grouping rests
  on, have no data for the final 3.8 years.
- **No fees.** A real CTA charging 2/20 would turn a 0.90 gross Sharpe into
  roughly 0.5–0.6 net to the investor. Running it yourself avoids that, which is
  the main argument for doing so.
- **Roll days are treated as return-neutral, in both directions.** Roll-day
  returns are masked (correctly — Datastream does not back-adjust) and compounded
  as zero, so neither the roll **cost** nor the roll **yield** enters. The cost
  omission flatters: roll trading is 25.9×/year of notional against 22.1× from
  the signal, worth 0.01–0.02 Sharpe as calendar spreads or 0.07 as paired
  outright trades. The yield omission is ambiguous in sign and untestable on a
  single stitched series per market.
- **Integer contracts are ignored.** Weights are continuous. At $1M several
  positions are fractions of a contract (DAX 0.22), so the backtested basket is
  not holdable below roughly $10–20M. This is the largest single gap between
  these results and a small account — larger than every cost effect combined.
- **Margin is estimated, not quoted, and the proxy is not an industry method.**
  The risk-based figures use `3.5 × daily standard deviation × notional`. Real
  clearinghouses run scenario engines (SPAN, SPAN 2, Eurex Prisma, OCC STANS);
  only the 99%/two-day *target* is conventional. The proxy ignores SPAN
  inter-commodity credits (pushing the estimate down) and, more importantly,
  ignores mandated **anti-procyclicality** — floors, stress buffers and long
  lookbacks that stop requirements falling in calm markets. Under a
  `max(126d, 10y)` floor plus a 25% buffer the worst month rises from 14% to 26%
  of the trend allocation. No margin parameter files were consulted.
- **No cash-buffer drag.** Variation margin settles in cash, so a real account
  holds ~4% in cash rather than bills. Worth ~0.08%/year at a 2% bill yield.

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
    in that leg — ~9% of portfolio capital in margin typically, but 27% at the
    95th percentile, which is the number to fund), the recommended blend lifts
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
