# Trend research log — dataset v2

Results on the rebuilt basket: **50 markets across 7 asset classes, 1973-01
onward**, roughly half of it built from contract-level Datastream data rather
than read from Datastream's own continuous series.

Dataset v1 — 35 markets from 1979-01, all continuous series — is frozen in
[trend-research-log.md](trend-research-log.md) and stays reproducible. Both
panels are on disk and the demos take `--dataset 1|2`, because the **only** way
to attribute a difference to the data rather than to a code change is to run the
same code over both. Do not mix numbers across the two documents.

Underlying data is licensed and lives in the gitignored `local_data/`. Only
aggregate results are recorded here. Datastream's own quirks are documented in
`portfolio_management/dataloader/ds_futures.py`; the contract-level construction
in `ds_contracts.py`. This section does not repeat those; it records what the
dataset *is* and what it can and cannot support.

---

# Part 1 — The dataset

## 1.1 What it contains

| | v2 | v1 |
|---|---|---|
| Markets | **50** across 7 classes | 35 across 6 classes |
| Span | **1973-01 → 2026-09** | 1979-01 → 2026-08 |
| Months (analysis window) | **639** (through 2026-03) | 572 |
| Effective breadth | **9.1** (mean \|corr\| 0.23) | 8.0 (mean \|corr\| 0.24) |
| Construction | 23 contract-built, 26 continuous, 1 mixed | 35 continuous |

**Twenty** markets were added and **five** dropped, leaving **thirty** shared
with v1; six of those thirty were rebuilt from contract data, and one (JGB10Y)
had its listing replaced. Part 6's table lists eight rows because it also counts
the source-replacements and palladium, which was removed before shipping and was
never in v1 — those are not drops from the basket. Mean pairwise correlation went
*down* (0.24 → 0.23) while the market count rose by **43%**, so the additions are
diversifying rather than duplicating.

**Terms used throughout.** *Open interest* is the number of contracts
outstanding — a stock, not a flow, unlike volume. A *continuous series* is a
stitched sequence of expiring contracts standing in for one market over decades.
The *roll* is the switch from an expiring contract to the next; the *roll gap* is
the price step between the two, which is term structure and not a return. *Front
month* is the contract carrying most of the open interest.

## 1.2 Per-market coverage

`source` is `contract` where we built the series ourselves, `continuous` where we
read Datastream's, `mixed` where a splice uses both. `OI rank1` is the share of
days on which the contract we held was the single largest by open interest;
`OI share` is the median fraction of the day's open interest it carried. Both are
blank for continuous series, which expose no contract-level data — that
asymmetry is itself a reason to prefer building.

### equity (8)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| SP500 | contract | USD | 528 | 1982-04 | 2026-03 | 98% | 99% |
| FTSE100 | continuous | GBP | 508 | 1984-05 | 2026-08 | — | — |
| HANGSENG | continuous | HKD | 464 | 1988-01 | 2026-08 | — | — |
| NIKKEI225 | continuous | JPY | 440 | 1988-09 | 2026-08 | — | — |
| DAX | continuous | EUR | 429 | 1990-12 | 2026-08 | — | — |
| KOSPI200 | continuous | KRW | 364 | 1996-05 | 2026-08 | — | — |
| ESTOXX50 | continuous | EUR | 326 | 1998-07 | 2026-08 | — | — |
| SPI200 | continuous | AUD | 317 | 2000-05 | 2026-09 | — | — |

v1 has **no US equity index at all**; SP500 is a splice of the full-size CME
contract and the E-mini (§3.6).

This used to force v1's equity beta to be measured against the SPY ETF, which
starts only in 2006 — so v1 and v2 were being scored against different
benchmarks over different windows, and their equity drawdowns disagreed by
twenty points for that reason alone. Both are now measured against the CRSP /
Fama-French US market excess return (1926–2026, `mktrf`), pulled by
`examples/cache_equity_benchmark_wrds.py`. It is already an excess return, so
no cash is subtracted from it; the ETF, being a total return, still is. With
the benchmark and window matched, the two datasets give the same portfolio
result — 60/40 levered scores **1.10 (v1)** against **1.09 (v2)** over the
common 1981-12 – 2024-12 window.

### bond (12)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| US30Y | contract | USD | 584 | 1977-08 | 2026-03 | 97% | 91% |
| US10Y | contract | USD | 527 | 1982-05 | 2026-03 | 98% | 96% |
| GILT | continuous | GBP | 526 | 1982-11 | 2026-08 | — | — |
| AUS10Y | continuous | AUD | 501 | 1984-12 | 2026-08 | — | — |
| **JGB10Y** | continuous | JPY | **477** | **1986-12** | 2026-08 | — | — |
| US5Y | contract | USD | 454 | 1988-06 | 2026-03 | 98% | 98% |
| CAN10Y | continuous | CAD | 438 | 1989-09 | 2026-08 | — | — |
| US2Y | contract | USD | 429 | 1990-07 | 2026-03 | 98% | 99% |
| AUS3Y | continuous | AUD | 381 | 1995-01 | 2026-09 | — | — |
| BOBL | continuous | EUR | 335 | 1998-10 | 2026-08 | — | — |
| BUND | continuous | EUR | 335 | 1998-10 | 2026-08 | — | — |
| SCHATZ | continuous | EUR | 335 | 1998-10 | 2026-08 | — | — |

The four US rates markets covered 1998-10 → 2025-04 in v1. Rebuilding moved
US30Y back to **1977-08** and US10Y to **1982-05**, and carried all four to
2026-03. AUS10Y and CAN10Y are new. **JGB10Y is a different contract from v1's**:
that one was the Singapore listing, which barely trades (§9.1), and it covered
only 2005-02 onward. Tokyo's starts 1986-12.

### fx (6)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| CADUSD | contract | USD | 639 | 1973-01 | 2026-03 | 98% | 90% |
| CHFUSD | contract | USD | 639 | 1973-01 | 2026-03 | 97% | 98% |
| JPYUSD | contract | USD | 639 | 1973-01 | 2026-03 | 98% | 95% |
| GBPUSD | contract | USD | 606 | 1975-10 | 2026-03 | 99% | 97% |
| AUDUSD | contract | USD | 471 | 1987-01 | 2026-03 | 97% | 99% |
| EURUSD | contract | USD | 334 | 1998-06 | 2026-03 | 99% | 98% |

The whole class is new. v1 held a dollar index and one thin cross (GBPJPY); both
were dropped, the index because it *is* a weighted basket of these six (the euro
alone is about 57% of it) and the cross because it is thin and spanned by the GBP
and JPY legs. Three of the six start in **1973-01** — the first months of
floating exchange rates after Bretton Woods.

### metal (7)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| PLATINUM | contract | USD | 639 | 1973-01 | 2026-03 | 94% | 78% |
| SILVER | contract | USD | 639 | 1973-01 | 2026-03 | 93% | 57% |
| GOLD | contract | USD | 583 | 1977-09 | 2026-03 | 92% | 53% |
| ALUMINIUM | continuous | USD | 395 | 1993-07 | 2026-08 | — | — |
| COPPER | continuous | USD | 394 | 1993-07 | 2026-08 | — | — |
| NICKEL | continuous | USD | 395 | 1993-07 | 2026-08 | — | — |
| ZINC | continuous | USD | 395 | 1993-07 | 2026-08 | — | — |

Gold and silver covered **2004-10 → 2022-11** in v1 — 217 months, and dead for
the last four years of the sample. Rebuilding gave 583 and 639 months, alive to
2026-03. Platinum is new; palladium was added and then dropped on liquidity (§9.5).

### ag (9)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| CORN_CBOT | contract | USD | 639 | 1973-01 | 2026-03 | 90% | 44% |
| SOYBEAN_CBOT | contract | USD | 639 | 1973-01 | 2026-03 | 88% | 44% |
| SOYOIL_CBOT | contract | USD | 627 | 1974-01 | 2026-03 | 95% | 42% |
| WHEAT_CBOT | contract | USD | 627 | 1974-01 | 2026-03 | 95% | 50% |
| COTTON | contract | USD | 587 | 1977-10 | 2026-08 | 93% | 51% |
| COCOA | continuous | USD | 572 | 1979-01 | 2026-08 | — | — |
| COFFEE | continuous | USD | 572 | 1979-01 | 2026-08 | — | — |
| SUGAR | continuous | USD | 572 | 1979-01 | 2026-08 | — | — |
| WHEAT_MAT | continuous | EUR | 341 | 1998-04 | 2026-08 | — | — |

v1's grains were London feed wheat, Paris milling wheat and Paris corn — none of
them the global benchmark, two of them thin. The world's most liquid grain
contracts were missing for a purely mechanical reason (§2.1). Chicago wheat,
corn, soybeans and soybean oil, plus ICE cotton, replace them; London wheat and
Paris corn were dropped, Paris milling wheat kept as a genuinely distinct market.

### energy (6)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| HEATOIL | contract | USD | 574 | 1978-11 | 2026-08 | 92% | 28% |
| WTI | mixed | USD | 521 | 1983-04 | 2026-08 | 88% | 23% |
| BRENT | continuous | USD | 452 | 1988-12 | 2026-08 | — | — |
| NATGAS | continuous | USD | 432 | 1990-04 | 2026-03 | — | — |
| NATGAS_UK | continuous | GBP | 355 | 1997-02 | 2026-08 | — | — |
| GASOLINE | contract | USD | 244 | 2006-05 | 2026-08 | 68% | 26% |

WTI covered 2006-02 onward in v1 (the ICE contract); the NYMEX original takes it
back to **1983-04**. Heating oil and gasoline are new, as is UK natural gas —
which matters because Henry Hub gas stops in 2026-03 and European gas decoupled
from it violently in 2022.

Their low `OI share` is **not** thinness: energy lists monthly contracts years
out and refiners, producers and airlines hold real positions all along the curve,
so even the front month carries only a quarter of the total. WTI is the most
traded commodity future in the world and shows 23%. `OI rank1` is the diagnostic
that means what it looks like; `OI share` measures curve depth.

### livestock (2)

| market | source | ccy | months | first | last | OI rank1 | OI share |
|---|---|---|---|---|---|---|---|
| LEANHOGS | contract | USD | 629 | 1973-11 | 2026-03 | 94% | 41% |
| LIVECATTLE | contract | USD | 567 | 1979-01 | 2026-03 | 97% | 43% |

An entirely new asset class. Livestock prices are driven by breeding cycles —
sow inventory, herd turnover, one to two years long — rather than by rates,
energy or grain, so the prior is that they diversify. That prior is not yet
tested, and neither is their trend speed (§1.5).

## 1.3 Breadth by window

Markets live in each five-year window, v2 against v1:

| window | ag | bond | energy | equity | fx | livestock | metal | **v2** | v1 |
|---|---|---|---|---|---|---|---|---|---|
| 1973–77 | 5 | 1 | 0 | 0 | 4 | 1 | 3 | **14** | 0 |
| 1978–82 | 8 | 3 | 1 | 1 | 4 | 2 | 3 | **22** | 5 |
| 1983–87 | 8 | 5 | 2 | 2 | 5 | 2 | 3 | **27** | 7 |
| 1988–92 | 8 | 8 | 4 | 5 | 5 | 2 | 3 | **35** | 13 |
| 1993–97 | 8 | 9 | 5 | 6 | 5 | 2 | 7 | **42** | 20 |
| 1998–02 | 9 | 12 | 5 | 8 | 6 | 2 | 7 | **49** | 31 |
| 2003–26 | 9 | 12 | 6 | 8 | 6 | 2 | 7 | **50** | 35 |

The 1988–92 window alone now holds as many markets as v1's *entire* sample.

## 1.4 The weakness this was built to fix

v1's three-speed finding was weakest in the 1980s, and the reason was arithmetic
rather than economic: the slow group had **one market in it**.

Membership is `GROUPING_V2`'s (§10.0), so livestock and platinum count as slow.

| window | v2 slow group | v1 |
|---|---|---|
| 1973–77 | 5 — GOLD, LEANHOGS, PLATINUM, SILVER, US30Y | 0 |
| 1978–82 | 8 — + GILT, LIVECATTLE, US10Y | **1** |
| 1983–87 | 10 — + AUS10Y, JGB10Y | **1** (GILT alone) |
| 1988–92 | 13 — + CAN10Y, US2Y, US5Y | **1** |
| 1993–97 | 14 — + AUS3Y | 2 |
| 1998–02 | 17 — + BOBL, BUND, SCHATZ | 9 |
| 2003–26 | 17 | 12 |

An average over one market carries no information about a group, so "grouping
versus no grouping" could not show a difference there whatever the truth. The
1983–97 stretch now holds 10–14 slow markets spanning four countries and three
asset classes.

## 1.5 What the grouping does *not* yet cover

The three-speed grouping in `GROUPING_V1` was learned on v1. Applied unchanged to
v2 it places four of the sixteen new markets by default rather than by
measurement:

- **PLATINUM and PALLADIUM fall to `fast`**, because the precious-metals
  override lists only gold and silver. Defensible — their demand is industrial
  (autocatalysts) and their roll gaps are small, unlike gold's — but untested.
- **LIVECATTLE and LEANHOGS fall to `fast`** because `livestock` is not in the
  class map at all and hits the default.

So any v2 result that uses the v1 grouping is a mixture, not a measurement of
either. The grouping is now **data** (`speed_group(asset, cls, grouping=...)`)
rather than hard-coded, precisely so that a re-learned grouping and the reversed
grouping used to falsify it are alternative values of one mechanism. Re-learning
it is the first analysis on this dataset and has not been done yet.

---

# Part 2 — Why the basket had to be rebuilt

## 2.1 Datastream's continuous series no longer carry CME Group

Withdrawal is staggered by exchange: **COMEX 2022-11, CBOT 2025-04, NYMEX
2026-04**. A survey of every continuous series priced after 2026-06 returns 40
exchange prefixes and **no CME, CBOT, ECBOT, COMEX or NYMEX entry anywhere**.

This is why v1 looked the way it did. It had no US equity index, no major FX
pair, no livestock, and its grains were London and Paris rather than Chicago —
not by choice, but because the route into the data could not see those markets.
Gold and silver appeared to die in 2022 and US rates in 2025 for the same reason.

The **contract-level** tables still hold all of it, with settlements, volume and
open interest, and with far more history than the derived series ever had: COMEX
silver from 1973-01 against the continuous series' 2004-10; CBOT 30-year from
1977-08 against 1998-10.

## 2.2 Live classes are the ones *without* continuous series

The natural fix — find the live class, point the basket at it — does not work. Of
17 target classes, **12 had no continuous series at all**, and they were exactly
the US markets. Meanwhile the long series that do exist sit on classes flagged
DEAD: `IBPCS00` is marked dead and contains 43 years of sterling, 1972–2015.

So class and series had come apart: the tradeable history is on one class code
and the usable series on another. Addressing markets by class code, which the
rebuild plan originally assumed, was not a workable scheme.

## 2.3 Three naming traps

Every live CME class was found by guessing a name, and each guess failed a
different way first:

1. **The `COMP.` / `COMPOSITE` family.** Live CME classes are named "JAPANESE YEN
   COMP.", "WHEAT COMPOSITE FUTURES", "10 YRS US T-NOTE COMP."; the deprecated
   ones carry the plain product name. Searching by the basket's own contract
   names finds only the dead classes.
2. **The E-mini is called "MINI S&P 500 INDEX"** — the string "E-mini" appears
   nowhere in it.
3. **Soybean oil's live class uses the British spelling**, "SOYABEAN OIL COMP.",
   while both dead ones say "SOYBEAN OIL". A search for `SOYBEAN` misses it
   entirely.

The general lesson: **never conclude a market is absent from one name search.**
`tools/survey_ds_classes.py` queries the contract table, which sees every class,
and `COMP` as a pattern enumerates the live CME family in one go.

## 2.4 Two vendor cliffs, not one

Continuous series for CBT/CME-prefixed markets stop on a single day, **2015-07-10**
— nine markets at once, which is a vendor migration and not a market event. The
successors (ECBOT, GLOBEX prefixes) then stop on **2021-03-26**. Only the `COMP.`
family ran to 2026-04.

## 2.5 Coverage is overstated by rows without prices

A continuous series emits rows past the date its prices stop. Counting rows
therefore overstates history — COMEX gold has rows to 2026-06 but settlements
only to 2022-11. Every coverage figure in this document counts **days with a
non-null settlement**, which is what the loader keeps. Three earlier conclusions
in this rebuild were wrong until that filter was applied.

---

# Part 3 — How the contract-level series are built

Implementation and the registry live in `ds_contracts.py`.

## 3.1 The problem a continuous series cannot solve

A continuous series prints the old contract on one day and the new one on the
next. Their ratio is not the return on any position, so v1's loader had to
**discard** the roll-day return. That is not a small loss: it is one real day per
roll, four to twelve times a year depending on the market.

Masking was nonetheless the right call for v1, because the alternative was worse.
Left in, the roll step injects pure term structure: **+4.97%/yr on gold, −2.10%/yr
on the 10-year note** (§4.2). Gold's own return over the sample is +4.10%/yr, so
the artefact alone would have roughly doubled its apparent performance.

## 3.2 The construction

> The contract to hold over (t−1, t) is chosen at t−1, and the return is that
> **one** contract's own settlement at t over its own settlement at t−1.

Every day is then a real return on a real position, roll days included, and
nothing needs masking.

## 3.3 Three constraints, each fixing an observed failure

**`buffer_days = 5`** drops contracts within five days of last trade, whose
settlements thin out into delivery.

**`window_months = 6`** limits the choice to contracts expiring within six
months. Without it, a rule free to pick any live contract occasionally takes a
deep-deferred one — gold's far December carries real open interest from financing
trades — and the no-backward constraint then pins the position there. Measured on
gold before the window existed: 13 holding runs over 4.5 months, **one of 43
months**, and a roll pace of 3.7 months against a true cycle of 2.4.

**No backward roll**: once a contract is left it is not re-entered, so a thin day
in the new front month cannot bounce the position back and forth.

## 3.4 Why nearest-expiry is unusable

Metals and softs list a contract every month but trade only a few of them — COMEX
gold's active months are Feb/Apr/Jun/Aug/Dec — and the serial months settle on
administratively derived rather than traded prices. A nearest-expiry rule walks
straight into them:

| gold, roll rule | median OI rank | median share of day's OI | days below 5% of OI |
|---|---|---|---|
| nearest expiry (calendar) | **11** | **0.3%** | **83%** |
| most open interest | **1** | **53%** | **0%** |

The calendar rule also produced a *higher* return (6.99% vs 4.10%/yr) despite
rolling four times as often in a contango market, where more rolling should cost
more — the sign that the prices it was compounding were not traded prices.
Daily volatility rose with it (18.5% → 19.4%), the stale-then-catch-up signature.

For bonds the two rules nearly agree, because bonds list quarterly only and
nearest-expiry *is* the liquid one. The rule therefore cannot be chosen once for
all markets from first principles; it has to be checked per market, which is what
the liquidity diagnostic is for.

## 3.5 The roll pace reproduces each market's own cycle

Nothing tells the builder what a market's delivery calendar is. It recovers it
from open interest:

| market | rolls/yr | mean holding | the market's actual cycle |
|---|---|---|---|
| US 2/5/10/30Y, E-mini S&P | 4.0 | 3.0 months | quarterly Mar/Jun/Sep/Dec |
| GOLD, SILVER | 5.0 | 2.4 months | Feb/Apr/Jun/Aug/Dec → 2.4 average |
| COTTON | 3.9 | 3.1 months | Mar/May/Jul/Oct/Dec, skipping a thin Oct |
| WTI, HEATOIL | ~12 | 1.0 month | monthly listings |

Cotton's holding periods include regular five-month runs starting each June:
after July expires the next genuinely liquid contract is December, and the rule
skips the thin October by itself.

## 3.6 Splices

Three markets are assembled from more than one series. The **first** listed
component wins a date — order is preference, not chronology.

| market | components | why |
|---|---|---|
| SP500 | E-mini, then full-size | the E-mini is the liquid contract and runs to 2026-03; the full-size one fills 1982-04 → 1997-08 |
| HEATOIL | NYMEX, then ICE | NYMEX is liquid throughout; ICE fills only the months after the NYMEX feed stops |
| WTI | NYMEX, then ICE | likewise |

The SP500 splice is validated like for like — both legs built the same way —
and returns **corr 0.9983, beta 1.00, volatility 15.3% / 15.3%** over 289
overlapping months.

**WTI's splice mixes constructions:** its ICE leg is a Datastream continuous
series, so those months carry the masked roll treatment. It covers four months of
521, which is why it is tolerated rather than fixed; `source = mixed` in the meta
file records it.

---

# Part 4 — What the construction is worth

## 4.1 Construction matters about twelve times more than which contract you trade

Three comparisons, each changing one thing:

| comparison | what differs | monthly corr |
|---|---|---|
| E-mini vs full-size S&P, both built by us | **the contract** | **0.9983** |
| our build of class 3725 vs `ISPCS00`, which is *derived from* class 3725 | **the construction** | **0.9796** |
| E-mini vs `ISPCS00` | both | 0.9725 |

Changing contract costs 0.0017 of correlation. Changing construction costs
0.0204. This is the single most useful number in the rebuild, because it explains
why every built-vs-continuous comparison lands in a narrow band:

```
US10Y 0.985  US30Y 0.984  US5Y 0.983  US2Y 0.983
SP500_FULL 0.980  ← pure construction difference
E-mini 0.973  GOLD 0.971  SILVER 0.968  PALLADIUM 0.965
```

That band is the fingerprint of a construction difference, **not** a measure of
data quality. Bonds sit above it because their roll gaps are smallest; metals
below because theirs are largest. Reading 0.97 as a defect was a mistake made
twice during this work.

Roll construction is therefore a free parameter of the same order as any modelling
choice, and it had never been treated as one.

## 4.2 The roll gap, by market

What a continuous series prints on a roll day, and masking discards. Sign follows
the curve: storage costs put commodities in contango, a positively sloped yield
curve puts bonds the other way.

| market | gap per roll | **per year** | the market's own return |
|---|---|---|---|
| GOLD | +0.99% | **+4.97%** | +4.10% |
| SILVER | +0.57% | **+2.87%** | +6.52% |
| WHEAT_CBOT | +2.23% | large | — |
| COTTON | +0.73% | — | — |
| PLATINUM | +0.36% | — | — |
| PALLADIUM | +0.05% | — | — |
| SP500 (E-mini) | +0.18% | +0.74% | — |
| US2Y | −0.16% | −0.65% | +0.92% |
| US5Y | −0.30% | −1.22% | +1.94% |
| US30Y | −0.40% | −1.64% | +3.07% |
| US10Y | −0.52% | **−2.10%** | +3.60% |

The gap is a **cross-contract** quantity, so a single bad settlement on a contract
being rolled away from distorts its mean without touching any return. CHFUSD's
mean is +8.81% against an FX peer group of −0.38%..+0.63% while its returns are
clean — its two largest moves are the 2011 and 2015 Swiss National Bank floor
events. Medians are now recorded alongside means for this reason.

Real roll-day returns, which this construction recovers and masking threw away,
run **−0.81%/yr (silver) to +0.76%/yr (gold)** — small, and of both signs.

## 4.3 Return-level differences are inside sampling error

Built series differ from the corresponding continuous ones by up to +2.6%/yr in
mean return. That looks large and is not:

| market | diff | residual vol | years | **t** |
|---|---|---|---|---|
| PALLADIUM | +2.63% | 9.0% | 46.4 | **1.96** |
| SILVER | +2.55% | 8.0% | 18.2 | **1.35** |
| GOLD | +1.12% | 4.1% | 18.1 | **1.17** |
| SP500_FULL | +0.48% | 3.0% | 39.4 | **0.99** |
| US30Y | −0.35% | 1.8% | 26.6 | **−1.01** |
| COTTON | −1.01% | 7.5% | 47.7 | **−0.93** |

Every one is inside two standard errors, and across ten markets a *t* near 2 is
expected. The differences look large because these are 20–35% volatility assets:
a residual whose volatility scales with the asset's produces mean differences
that scale too. **Scaling with volatility is the signature of noise, not of
bias** — misread once during this work, in the opposite direction.

A sweep of the roll buffer from 1 to 30 days moved palladium's difference by
0.07 percentage points (+2.56% to +2.63%), confirming the level is not being
driven by roll timing either.

**What this construction pins down is coverage and volatility, not the level of
long-run return.** Palladium's 46-year mean carries a standard error of 5.1%/yr
from its own volatility alone; no construction choice can rescue that.

---

# Part 5 — Two defects found and fixed

Both were found by checking the built panel against expectations, not by the
construction failing loudly. Both are recorded because the *class* of error
recurs.

## 5.1 Missing last-trade dates silently truncated two markets by thirty years

The builder dropped contracts with no `lasttrddate`, since the roll rule needs an
expiry. Five of 27 classes have such contracts, and two are largely made of them:

| market | contracts missing an expiry | cost |
|---|---|---|
| WHEAT_CBOT | 161 of 273 (59%) | 1974-01 → 2006-12 |
| LEANHOGS | 192 of 400 (48%) | 1973-11 → 2002-02 |
| CADUSD / GBPUSD / PLATINUM | 4 / 1 / 1 | isolated contracts, no truncation |

The symptom was only that two series started thirty years late — no error, no
warning. It was caught by comparing the built start dates against the class
survey, which reports price coverage without requiring an expiry.

**Fix:** an expired contract's last priced day *is* its last trading day. That
substitution is checked rather than assumed: on contracts that *do* carry an
expiry, the gap between it and the last priced day has **median 0 days**. The
95th percentile is large (over a year) only because still-live contracts have
expiries beyond the 2026-04 feed cutoff.

Using an observed date as an expiry is not look-ahead: a delivery month is a
contractual fact known at listing, and the price record merely recovers it. The
one failure mode — a contract whose data stops before it truly expires — makes
the rule roll away early, which is conservative.

## 5.2 Uncleaned contract prices destroyed one market

The continuous-series path has always run a price cleaner that drops zero prices
and isolated reversing spikes. The contract path did not. ICE RBOB gasoline
prints a settlement roughly 10,000× too large on three days — 2007-10-17,
2008-08-25, 2008-09-26 — each reversing the next day:

```
2007-10-17  +999900%     2007-10-18  −100%
2008-08-25 +1004676%     2008-08-26  −100%
2008-09-26  +987662%     2008-09-29  −100%
```

A −100% daily return drives that **month's** compounded return to −1.0, and
annualised volatility to 8,000%. Nothing downstream recovers from that.

This gap had been noticed earlier and dismissed, on the reasoning that a
reversing spike cancels when compounded within a month. That holds only while the
spike is mild; a 10,000× spike does not cancel, it annihilates. **Cleaning is now
applied per contract** — per contract rather than on the assembled series, because
a glitch belongs to one contract's price record, and dropping the *price* rather
than the return lets the next return span the gap.

Cleaning drops 17 bad prints across gasoline's 285 contracts; only three
surface in the assembled series, since one contract is held at a time. After the
fix its annualised volatility is **33.8%** (from 8,033%), its largest daily move
22.1%, and its worst month **−55.2% in 2020-03** — the same month in which WTI
fell 54.8% and Brent 56.2%. Three independently constructed energy series
agreeing on that month is itself a check.

A scan of all 27 built series for the same pattern found gasoline alone.

Three other large moves were checked and are **real**, not glitches: NICKEL
+64.2% on 2022-03-07 (the LME squeeze), NATGAS_UK +50.9% on 2022-02-24 (the
invasion of Ukraine) and +61.2% on 2006-09-29. The spike filter passed them
because they do not reverse, which is exactly its design.

---

# Part 6 — What was dropped, and why

| dropped | reason |
|---|---|
| ORANGEJUICE | among the thinnest listed futures anywhere; it was in the sample from 1979 and so entered every v1 result |
| WHEAT_LIF (London feed wheat) | thin; Chicago wheat covers the exposure |
| CORN_MAT (Paris corn) | thin, and redundant with Chicago corn |
| USDINDEX | a weighted basket of the six FX majors now held directly |
| GBPJPY | thin cross, and spanned by the GBP and JPY legs |
| US 2/5/10/30Y, GOLD, SILVER (continuous) | replaced by contract-level rebuilds of the same markets |
| JGB10Y (`SJGCS00`) | the Singapore listing; 26 trading days in 27,573 (§9.1). Replaced by Tokyo's `JGBCS00` |
| PALLADIUM | 4,043 contracts/day, thinnest in the basket, five times below platinum (§9.5) |

Candidates considered and rejected: TOCOM gold and silver (longer than the dead
COMEX series, but yen-denominated — measured correlation to USD gold only 0.795 —
and superseded once the contract-level USD series reached 1973); Tokyo corn and
South African wheat (thin, and largely a Chicago price plus a currency leg);
MGEX spring wheat (a genuine distinct benchmark, but too thin for the liquidity
bar this basket is held to); COMEX copper (~0.98 correlated with the LME copper
already held); Kansas City wheat (~0.9 correlated with Chicago); the S&P GSCI
index future (a basket, not a market); CME Nikkei (duplicates Osaka).

---

# Part 7 — Limits of this panel

**The 2026-04 cliff.** 21 of the 50 markets stop when the CME feed does, so from
2026-04 the panel holds 29 markets and a very different, much less US-weighted
mix. `load_basket(version=2)` therefore ends at **2026-03** by default; pass
`--through all` deliberately. Any cross-market result that averages across the
change is comparing two baskets.

**Two constructions in one panel.** 23 markets carry their roll-day returns; 26
have that day masked. The measured cost is a volatility discrepancy of **+0.3 to
+0.5 percentage points** for built series, not a return discrepancy (§4.3). It is
small but real, and `source` in the meta file records which construction each
market used. Building every market the same way is possible — contract data
exists for the continuous ones too — and is not done.

**Local-currency convention.** Futures returns are taken in the contract's own
currency, as is standard, so FTSE is in sterling and DAX in euro. This is
consistent across the panel and was the deciding argument against the yen-priced
TOCOM metals: adding them alongside CME yen would have put the same currency leg
in two markets.

**A regime break in lean hogs.** CME replaced Live Hogs (physically delivered, by
live weight) with Lean Hogs (cash settled, by carcass yield) at the end of 1996.
If the composite class joins the two, there is a definitional break around
1996-12. Harmless for a trend strategy, which trades regime changes, but any
long-run statistic quoted for lean hogs must note it.

**Eight markets have interior gaps, all of them continuous series.** 48
market-months are missing inside a market's own span — 0.19% of the panel, but
concentrated: NIKKEI225 loses 16 months (2020-12 → 2022-03) and ESTOXX50 12.
CAN10Y loses 6, the four LME metals 3–4 each in 1993, Brent one.

Every one of these gaps is present in v1 **identically**, so they are inherited
from Datastream's continuous series rather than introduced by the rebuild. **No
contract-built market has any gap**, which is a further argument for building
every market the same way.

**The daily panel uses a union calendar, which couples the markets slightly.**
A market trading on a day when every other market is closed adds a row, and the
126-day rolling volatility window then spans a different stretch of calendar time
for everyone. Adding Tokyo JGB introduced six such dates and moved 31 monthly
currency returns by up to 2.13e-04. Negligible in itself — but large enough to
flip an argmax whose margin is zero (§10.3a).

**Three kept markets use a different roll convention.** AUS3Y and SPI200 use
Datastream roll method 3 and NATGAS method 1, against method 0 everywhere else.
This is inherited from v1, not introduced here.

**Nothing in Part 1–7 is a result.** This part of the log describes the dataset
only. No strategy conclusion should be drawn from it, and the v1 findings have
**not** been re-run on this panel.

---

# Part 8 — Verification record

Checks run on the assembled panel, all passing:

| check | result |
|---|---|
| Market count, registry ↔ panel ↔ meta agreement | 50 / 50 / 50, no extras or omissions |
| Panel reconstructs exactly from its cached parts | max difference 0.00e+00 |
| Splices: preferred leg wins its dates, series extends past it, no component leaks | pass |
| Reversing spikes remaining anywhere | 0 |
| Infinities, all-NaN markets | none |
| Contract-built markets whose median held contract ranked 1st by open interest | 23 of 23 |
| Annualised volatilities within 1%–70% | 1.0% (US2Y) to 61.9% (NATGAS) |
| Index sorted, unique, starting 1973-01 | pass |

Extremes were checked against history rather than only against thresholds:
Brent −56.2%, WTI −54.8% and gasoline −55.2% all in **2020-03**; silver −47.1% in
**1980-03** and +55.0% in 1979-09; nickel +64.2% on 2022-03-07. Independently
constructed series agreeing on the date and magnitude of known events is stronger
evidence than any range check.

Final panel: **50 markets, 1973-01 → 2026-03, 639 months, mean |correlation|
0.23, effective breadth 9.1**, with all 50 markets reporting in the last
analysis month.

The structural checks above were run on the 51-market panel and re-verified after
palladium's removal and the JGB replacement; only the counts change.

---

# Part 9 — Can the market be traded at all?

This question was asked last and should have been asked first. A market that
cannot be traded has no meaningful correlation and no meaningful Sharpe, so
screening on liquidity belongs before any of it.

Every liquidity figure produced earlier in this rebuild was **relative** — the
share of a market's own open interest carried by the contract we held. That
establishes we picked the right contract *within* a market. It says nothing about
the size of the market, and a market nobody trades can score perfectly on it,
because numerator and denominator vanish together.

## 9.1 A market with 21 years of prices and no trading

`rank_market_liquidity.py` measures absolute volume and open interest for every
market in the basket (51 at the time of the screen), resolving the continuous-series ones to their classes. One market failed
outright:

| | contract-days | with a volume field | **volume > 0** | max volume |
|---|---|---|---|---|
| BUND (control) | 105,110 | 105,110 | 84,626 | 3,591,302 |
| GILT (control) | 161,978 | 161,975 | 95,325 | 1,067,960 |
| **JGB10Y as held** | 27,573 | 27,539 | **26** | **80** |

The first reading was that the field must be empty — JGB futures are among the
most traded bond futures anywhere. It is not empty. 27,539 contract-days carry a
volume and twenty-six of them are above zero.

The class name explains it: the basket's JGB10Y resolved to **`SJGCS00`, "SGX
DT-10YR JGB CONTINUOUS"** — the Singapore offshore listing, not the Tokyo/Osaka
contract that is the Japanese government bond market. It supplied 27,568
settlement prices and a return series with normal volatility, normal
correlations, no gaps and no spikes. **Every check this project runs passed it.**

The replacement is `JGBCS00`, TSE 10-year: 49,242 of 58,804 contract-days trade,
peaking at 151,075 contracts, and it starts **1986-12 instead of 2005-02**.

Two things follow that are larger than the one market:

* **"Has prices" and "has a market" are different properties, and only the first
  had ever been verified.** This is the market-level form of the derived-price
  problem that made a nearest-expiry roll rule hold contracts ranked 11th by
  open interest (§3.4). There it cost a roll rule; here it put a non-market in
  the basket.
* **It was in v1 too**, so every result in the v1 log includes it. One of
  thirty-five markets, in a bond sleeve of ten, so the effect is small — but it
  is not zero and it was never disclosed.

## 9.2 All 27 continuous-series markets checked

The JGB was found by accident: it registered 100% zero-volume days and happened
to trip a threshold. That is not a method, so every continuous-series market was
then checked for which exchange's listing it is and whether that listing trades.
The 23 contract-built markets already carry per-market open-interest diagnostics;
the risk was concentrated entirely in the other 27.

All 27 trade. NIKKEI225 in particular resolves to `ONACS00`, **OSX-NIKKEI 225
INDEX** — Osaka, not one of the three Singapore listings, whose traded shares are
9–16% against Osaka's 66%.

The check also corrected the diagnostic itself. The *percentage* of contract-days
that trade is confounded by **curve depth**, exactly as the
share-of-open-interest measure was confounded by it (§9.3). LME lists daily
prompt dates out to three months and then monthlies for years, so an LME class
holds an enormous number of contract-days that never trade:

| market | priced contract-days | traded | busiest day |
|---|---|---|---|
| DAX | 136,902 | 91% | 537,606 |
| LME copper | 694,088 | **12%** | **164,009** |
| ICE UK natural gas | 379,113 | 27% | **39,270** — basket minimum |
| *SGX JGB (removed)* | *27,573* | *0.1%* | ***80*** |

Across the 27, traded-share and curve depth correlate **−0.67**. Depth is not
death. The discriminator that is not confounded is **maximum daily volume**:
every market in the basket peaks above 39,000 contracts, which is **491 times**
the Singapore JGB's peak of 80. The screen in `check_listing.py` now uses that
absolute floor rather than a percentage.

## 9.3 Currency access, which volume cannot see

Volume measures whether a market is big. It cannot see whether you are allowed
in. Of the 50 markets, 49 are denominated in freely deliverable currencies
(USD 33, EUR 6, AUD 3, GBP 3, JPY 2, HKD 1 — the peg makes the Hong Kong dollar
freely convertible in practice). One is not:

**KOSPI200 is denominated in Korean won**, which is not freely deliverable:
foreign participation requires an Investment Registration Certificate, settlement
is onshore, and the offshore market is non-deliverable forwards. It trades
208,307 contracts a day — among the most traded index futures in the world — so
**every volume-based screen passes it**. The friction is access, not size.

Whether to keep it is not a data question. With the registration it is an
ordinary liquid market; without it, it is not investable at all, which is a
different thing from being expensive to trade.

## 9.4 Two screens that failed, and why

**Zero-volume days above 2%** measures holiday calendars, not thinness. The
markets nearest that threshold were GILT 1.7%, FTSE 100 1.9%, SPI 200 1.7% and UK
gas 1.9% — every one sterling or Australian dollar, and FTSE 100 trades 439,080
contracts a day. British and Australian exchange holidays exceed American ones,
and Datastream emits a row on a closed day.

**Below 15% of the asset-class median volume** measures contract units. It
flagged Australian 3- and 10-year bonds (against a bond median inflated by US
Treasuries and Bunds trading in the millions), UK gas (whose lot is a month of
1,000 therms a day, against Brent's 1,000 barrels), SPI 200, and the full-size
S&P — the last of which is only used for 1982–1997, when it was *the* contract,
and was measured in its post-2015 death throes.

`wrds_contract_info` carries no contract-size field — only unit *codes*
(`currunitcode`, `unitcode`, `unitdesc`, `ticksizeunitcode`) — so contract counts
cannot be converted to notional. Comparisons are therefore valid **only between
markets whose contracts are of similar size**.

## 9.5 What the screen actually establishes

| market | finding | action |
|---|---|---|
| JGB10Y (`SJGCS00`) | 26 trading days in 27,573 | **replaced** by `JGBCS00`, Tokyo, from 1986-12 |
| KOSPI200 | KRW, access-gated, 208,307 contracts/day | **user decision** — not answerable from data |
| PALLADIUM | 4,043 contracts/day against platinum's 19,672 — same exchange, comparable contract sizes (100 vs 50 troy oz), so the comparison is meaningful. Roughly $600m/day notional | **dropped** on liquidity |
| the other 47 | no evidence of a problem; all 27 continuous-series listings verified as the primary exchange | kept |

Palladium is dropped on the liquidity bar this basket is held to: it is five
times thinner than platinum, its nearest comparable market, and the thinnest of
the fifty-one.

**The reason matters as much as the decision.** Palladium is also the weakest
addition since 2012 (§10.6), and that must not be read as why it went. Screening
on outcome is the bias that makes the older 35-market basket's recent Sharpe
untrustworthy, and repeating it here — deliberately, on our own basket — would be
worse than inheriting it. **Liquidity is knowable in advance; performance is
not.** Only the first may be screened on.

Two things establish that the rule applied was liquidity and not performance.

**Platinum is kept.** It shares the same −0.27 since 2012 and stays, because at
19,672 contracts a day it is in line with the other metals. A rule that removes
the thin loser and keeps the liquid loser is a liquidity rule.

**Palladium was one of the better trend markets in the basket.** Its single-market
trend Sharpe is +0.49 at nine months — third highest of the fifty that remain,
against a median of +0.18. Only its *recent* stretch is poor. A rule selecting on
performance would never have removed it.

Removing it cost about **0.02 Sharpe** across every configuration — the
walk-forward drops 0.92 → 0.90 for the v2 grouping, 0.90 → 0.88 for uniform 12m,
0.68 → 0.66 for the reversed learned grouping — and effective breadth 9.2 → 9.1.
(0.90 is the figure at that moment, with platinum still fast; §10.2a then moves
platinum and the final value is 0.89.) That
decline is **the price of the constraint, not evidence against the decision**.
Keeping a market because dropping it lowered the backtest is selection on the
outcome, and doing it knowingly would be worse than inheriting it.

It is worth stating the asymmetry plainly: the older basket's recent Sharpe of
0.86 contains an **undisclosed selection gain**; this basket's 0.90 contains a
**disclosed constraint cost**. Only the second is the kind of number that
survives contact with an actual account.

The basket is therefore **50 markets**, metals 7.

---

# Part 10 — The speed grouping, re-examined

The v1 log's headline finding was a three-speed grouping — slow 18 months for
bonds and precious metals, mid 9 for equities and currencies, fast 3 for
everything else — reported as worth about +0.20 Sharpe against a uniform
12-month lookback. This part tests whether it survives on v2, and the short
answer is that **most of it does not, for a reason that is about the basket
rather than about the finding**.

## 10.0 The two groupings, defined

Both are referred to throughout this part, so both are written out here rather
than described. Each is a **value** passed to `speed_group(asset, class,
grouping=...)`, not a branch in the code — a re-learned grouping and the reversed
one used to falsify it are then alternative values of one mechanism rather than
three copies of a function.

A grouping has three fields. `by_asset` overrides `by_class`; `default` catches
anything unlisted, and `None` there means **raise** rather than guess.

**`GROUPING_V1`** — as learned on the v1 basket and frozen:

```python
GROUPING_V1 = {
    "by_asset": {m: "slow" for m in PRECIOUS_METALS},   # GOLD, SILVER, GLD, SLV, XAU, XAG
    "by_class": {"bond": "slow",
                 "equity": "mid", "fx": "mid",
                 "energy": "fast", "metal": "fast", "ag": "fast"},
    "default": "fast",
}
```

**`GROUPING_V2`** — the same with two corrections, each argued in §10.2 and
§10.2a:

```python
GROUPING_V2 = {
    "by_asset": {**{m: "slow" for m in PRECIOUS_METALS}, "PLATINUM": "slow"},
    "by_class": {"bond": "slow", "livestock": "slow",       # livestock added
                 "equity": "mid", "fx": "mid",
                 "energy": "fast", "metal": "fast", "ag": "fast"},
    "default": None,                                        # unlisted class raises
}
```

Speeds are shared by both: **slow 18 months, mid 9, fast 3** (`TREND_SPEEDS`).

### Membership on the 50-market basket

`GROUPING_V1`:

| group | markets |
|---|---|
| **slow 18m** (14) | *bond* — AUS10Y, AUS3Y, BOBL, BUND, CAN10Y, GILT, JGB10Y, SCHATZ, US2Y, US5Y, US10Y, US30Y · *metal* — GOLD, SILVER |
| **mid 9m** (14) | *equity* — DAX, ESTOXX50, FTSE100, HANGSENG, KOSPI200, NIKKEI225, SP500, SPI200 · *fx* — AUDUSD, CADUSD, CHFUSD, EURUSD, GBPUSD, JPYUSD |
| **fast 3m** (22) | *ag* — COCOA, COFFEE, CORN_CBOT, COTTON, SOYBEAN_CBOT, SOYOIL_CBOT, SUGAR, WHEAT_CBOT, WHEAT_MAT · *energy* — BRENT, GASOLINE, HEATOIL, NATGAS, NATGAS_UK, WTI · **livestock — LEANHOGS, LIVECATTLE** · *metal* — ALUMINIUM, COPPER, NICKEL, **PLATINUM**, ZINC |

`GROUPING_V2`:

| group | markets |
|---|---|
| **slow 18m** (17) | *bond* — the same twelve · **livestock — LEANHOGS, LIVECATTLE** · *metal* — GOLD, **PLATINUM**, SILVER |
| **mid 9m** (14) | unchanged |
| **fast 3m** (19) | *ag* — the same nine · *energy* — the same six · *metal* — ALUMINIUM, COPPER, NICKEL, ZINC |

**Three markets move, forty-seven do not.** Lean hogs and live cattle leave the
fast group because `livestock` was absent from v1's class map and fell to the
commodity default, where their trend Sharpe is negative; platinum leaves it
because its lookback profile belongs with gold and silver. On the v1 basket,
which contains neither livestock nor platinum, the two groupings are **identical
market for market** — which is why they score the same 1.06 there.

### What "reversed" means

The falsification used throughout swaps the outer groups and leaves the middle:

| | slow | mid | fast |
|---|---|---|---|
| grouping | 18m | 9m | 3m |
| **reversed** | **3m** | 9m | **18m** |

So bonds run on a 3-month signal and energy on 18. If the grouping captured
nothing, reversing it should cost nothing.

## 10.1 With error bars, no class has an identifiable optimum

Each asset class is evaluated as a **portfolio** — hold that class's markets at
one lookback, size by inverse volatility — rather than as an average of
single-market Sharpes, which is not a quantity anyone can trade and whose error
bar does not shrink with the number of correlated markets in it.

| class | n | 3m | 6m | 9m | 12m | 18m | 24m | best | margin |
|---|---|---|---|---|---|---|---|---|---|
| bond | 12 | 0.22 | 0.24 | 0.44 | **0.51** | 0.45 | 0.35 | 12m | 0.06 |
| ag | 9 | **0.42** | 0.30 | 0.27 | 0.31 | 0.25 | 0.21 | 3m | 0.11 |
| equity | 8 | 0.19 | 0.26 | 0.39 | **0.42** | 0.16 | 0.25 | 12m | 0.03 |
| metal | 7 | 0.30 | 0.37 | 0.38 | **0.44** | 0.25 | 0.21 | 12m | 0.05 |
| fx | 6 | 0.51 | **0.52** | 0.49 | 0.45 | 0.36 | 0.27 | 6m | 0.02 |
| energy | 6 | **0.34** | 0.19 | 0.13 | 0.20 | −0.01 | 0.03 | 3m | 0.14 |
| livestock | 2 | −0.01 | 0.04 | **0.21** | 0.17 | 0.11 | 0.06 | 9m | 0.03 |

A Sharpe measured over T years carries a standard error near 1/√T. Here that is
**0.14**, and the best lookback's lead over the runner-up is 0.02 to 0.14.
**Not one class separates its optimum from the alternatives.** Energy and
agriculture come closest and neither clears the bar.

What *is* visible is the shape rather than the peak: energy decays monotonically
from 0.34 at 3m to 0.03 at 24m, bonds hump in the middle, and livestock is
**negative at 3m and 6m**. Shapes differ by more than argmaxes do.

## 10.2 The one correction the evidence supports

Four of the new markets were placed by v1's *default*, not by evidence:
platinum and palladium because the precious-metals override lists only gold and
silver, and both livestock markets because `livestock` is absent from v1's class
map entirely.

Platinum and palladium have no clear case for moving. Livestock does, and it is
not a marginal-argmax case — **its Sharpe at the assigned speed is negative**.

| walk-forward, v2, 518 OOS months | Sharpe |
|---|---|
| v1 grouping (livestock at 3m by default) | 0.87 |
| v1 grouping + livestock **9m** | **0.90** |
| v1 grouping + livestock **12m** | **0.90** |
| v1 grouping + livestock **18m** | **0.90** |

All three give the same 0.90: **the gain is in leaving 3m, not in locating an
optimum**, which is what a real effect looks like and what a fitted one does not.

Two markets of fifty move the portfolio by 0.02 because they are its least
correlated: lean hogs has a mean |correlation| of **0.063** to the rest and live
cattle 0.082, against a basket average of 0.184 — the **lowest and the fourth
lowest** of the fifty. Marginal contribution per unit of weight is correspondingly high.

`GROUPING_V2` is therefore v1's grouping with `livestock → slow`, the platinum
override of §10.2a, and `default: None` so that an unlisted class **raises** instead
of silently becoming a commodity. On the v1 dataset, which has no livestock,
`GROUPING_V2` and `GROUPING_V1` are identical to the digit (walk-forward 1.06
both) — a hole-filling change should be inert where there is no hole.

## 10.2a Platinum, moved for consistency and worth nothing

Platinum sits on the precious/industrial line: roughly 40% of its demand is
autocatalyst against gold's ~10% industrial, but it is stored as bullion and
traded on precious-metals desks. v1 placed it fast, because its
`PRECIOUS_METALS` override lists gold and silver **by name**.

Its argmax margin is 0.05 — inside the noise, and by §10.3a unusable. Two larger
quantities are readable:

| metal | 3m | 12m | **tilt (12m − 3m)** | group |
|---|---|---|---|---|
| GOLD | 0.15 | 0.50 | **+0.35** | slow |
| **PLATINUM** | 0.07 | 0.22 | **+0.15** | fast → **slow** |
| SILVER | 0.18 | 0.30 | **+0.12** | slow |
| ALUMINIUM | 0.06 | 0.10 | +0.03 | fast |
| COPPER | 0.27 | 0.25 | −0.02 | fast |
| ZINC | 0.32 | 0.22 | −0.10 | fast |
| NICKEL | 0.20 | 0.05 | −0.15 | fast |

Platinum tilts slower than silver, and the four base metals sit in a separate
band. Its profile correlates **+0.70** with gold and silver against **+0.22**
with the base metals — which themselves correlate **−0.17** with gold and
silver. Palladium, before it was dropped, tilted **−0.04**, matching a demand
base roughly 85% autocatalyst. Behaviour and demand structure agree on both.

**It is worth nothing, measured two ways that disagree in sign.** The
walk-forward loses 0.01 (0.90 → 0.89); the single split gains 0.01 (0.74 → 0.75)
while its training Sharpe falls from 0.88 to 0.78. Both are inside a tenth of a
standard error.

The change is therefore made on **consistency, not performance**: the override
exists to hold metals that trend slowly, platinum is one, and leaving it out
makes the name of the list untrue. It is recorded here precisely because it pays
nothing — a reader should be able to tell which decisions in this log were made
for returns and which were not.

One implementation note with teeth: platinum was added to `GROUPING_V2`'s own
overrides and **not** to `PRECIOUS_METALS`, even though that leaves a list named
for precious metals without platinum in it.

The reason is not that v1 results would move — **the v1 basket holds no
platinum**, so on v1 data the edit changes nothing whatsoever (0.909 → 0.909).
It is that `GROUPING_V1` is also the **baseline in every v2 comparison**,
standing for a prior fixed before this data and untouched since. Adding platinum
on v2 evidence would inject v2 information into
the baseline used to test whether injecting v2 information helps — and §10.3,
which finds that learning loses to not-learning on all three panels, rests on
that baseline being clean. Measured: the edit moves the v1-grouping baseline on
v2 data from **0.821 to 0.744**.

So the name is wrong on purpose, and says so where it is defined. The existing
test asserting platinum was fast in v2 failed on the change, which is what it
was for.

## 10.3 Learning the grouping is worse than not learning it

Walk-forward, stitched out-of-sample Sharpe. **learned** re-fits one lookback per
asset class at every window start from training data only (§10.3a shows what that
amounts to); the two groupings are §10.0's, applied unchanged in every window.

| panel | learned | `GROUPING_V2` | `GROUPING_V1` | uniform 12m | `V2` reversed | learned reversed |
|---|---|---|---|---|---|---|
| v1 dataset, 451 OOS months | 0.86 | **1.06** | **1.06** | 0.74 | **0.52** | 0.53 |
| v2 full, 518 months | 0.85 | **0.89** | 0.87 | 0.88 | **0.58** | 0.66 |

The two groupings tie on the v1 dataset because they are the same object there —
it holds neither livestock nor platinum (§10.0).

**The two reversal columns reverse different objects, and only the first tests
what is actually used.** `V2 reversed` swaps `GROUPING_V2`'s slow and fast groups,
so bonds run on 3 months and energy on 18. `learned reversed` swaps the *learned*
grouping's speeds — and on v2 that grouping collapses to two speeds, 3 and 12, so
its reversal exchanges 3m and 12m rather than 3m and 18m. It is a milder
perturbation of a different object, and earlier drafts of this log reported it
under the bare label "reversed", which was wrong.

**Learning loses to the fixed grouping on all three panels** — but it beats
uniform 12m on two of them, and that distinction was stated wrongly in an earlier
draft of this section. The claim is *not* that learning is useless. It is that a
prior fixed before the data in hand beats re-estimating on it — with the
qualification of §10.3b, which matters.

**This is also not a test of the v1 log's walk-forward, which learns something
else.** That procedure fits a lookback per MARKET, buckets markets into slow /
mid / fast by the result, and blends the top two lookbacks within each bucket;
it reports 1.02 against uniform 12m's 0.79 over 1994–2023. The procedure here
fits one lookback per asset CLASS with no blending, over 1989–2026. Both find
learning ahead of uniform. Neither reproduces the other, and the 0.86 in the
table above is not evidence against the 1.02.

What the v1 log never ran is the row this table adds: **the fixed grouping,
re-learning nothing at all.** Its aggregate walk-forward table compares two
learned variants against uniform 12m and stops there. On every panel tested here
that missing row comes first.

And on a single split the relationship between fit and test is not merely weak
but inverted — across the seven honest configurations below (the reversed
grouping is excluded, being deliberately wrong), train and test Sharpe correlate
**−0.95**, slope **−1.09**:

| configuration | train | test |
|---|---|---|
| learned on training window | 1.00 | 0.47 |
| uniform blend 3+12 | 1.15 | 0.41 |
| uniform blend 3+6+12 | 1.06 | 0.44 |
| uniform 12m | 1.06 | 0.44 |
| uniform blend 3+9+18 | 0.97 | 0.61 |
| v1 grouping | 0.89 | 0.71 |
| **v2 grouping** | **0.78** | **0.75** |

The configuration that fits worst tests best, and near enough one-for-one: a
slope of −1.09 means each extra unit of training Sharpe is repaid with slightly
more than a unit lost out of sample. Any selection performed on this training
window is counter-productive.

That is why the winner is the grouping **not fitted on this window** — though
§10.3b immediately qualifies how clean "not fitted" is, since it was fitted on
the wider sample.

## 10.3a Two of the seven learned assignments are decided by rounding

Replacing one bond market — the Singapore JGB listing of §9.1, whose data touches
no currency — flipped the learned grouping's assignment for **currencies** from
3 months to 12. Chasing that down produced the sharpest evidence in this part.

Training-window Sharpe by lookback, the quantity the learned grouping maximises:

| class | 3m | 6m | 9m | 12m | 18m | 24m | best − runner-up |
|---|---|---|---|---|---|---|---|
| ag | **0.5794** | 0.4041 | 0.2356 | 0.3511 | 0.2128 | 0.1812 | 0.1753 |
| bond | 0.3201 | 0.3662 | 0.4703 | **0.6192** | 0.3359 | 0.3096 | 0.1489 |
| energy | **0.3272** | 0.0198 | −0.0355 | 0.1891 | −0.2046 | −0.0465 | 0.1381 |
| equity | 0.1078 | 0.2397 | 0.3986 | **0.4801** | 0.0811 | 0.1598 | 0.0815 |
| metal | 0.4957 | 0.3715 | 0.5870 | **0.6374** | 0.2782 | 0.2129 | 0.0504 |
| livestock | 0.1040 | 0.2318 | 0.3378 | **0.3410** | 0.0770 | 0.0773 | **0.0031** |
| **fx** | **0.7955** | 0.7564 | 0.7355 | **0.7955** | 0.6797 | 0.5171 | **0.0000** |

**Currencies tie to four decimal places.** Which of 3m and 12m the argmax
returns is settled by a floating-point difference — and the perturbation that
flipped it has been traced: six calendar dates exist in the daily panel only
because Tokyo traded when every other market was closed (1986-12-25, 1987-04-17,
and four more). Those six rows shift the 126-day rolling volatility window,
changing 31 monthly currency returns by at most 2.13e-04 and the training Sharpe
by 0.0001. That was enough.

Livestock is nearly as close at 0.0031. Only three of seven classes separate
their best lookback from the runner-up by more than 0.1, against a test-window
standard error of 0.22.

**This does not undo §10.2, and the distinction matters.** Livestock was moved on
the evidence that 3m is *wrong*, not that 12m is *right*: on the training window
3m scores 0.1040 against 12m's 0.3410, a gap of 0.237 — seventy times the gap
between 12m and 9m. Hence 9m, 12m and 18m all producing the identical 0.92 in
§10.2. The usable rule is narrow: **when the argmax's margin is inside the noise
the argmax is unusable, but "this end of the range is clearly worse" can still
be read.**

The learned grouping also collapses to **two speeds**, not three: agriculture,
energy and currencies at 3m; bonds, equities and metals at 12m; livestock alone
at 9m. That two-speed shape is what the v1 log records trying **first** and then
abandoning when it failed to replicate on the ETF basket.

## 10.3b "Fixed" is not "clean": the baseline is contaminated too

Every comparison above sets a fixed grouping against one refitted per window, and
the fixed one wins. It would be easy to read that as a prior beating a fit. It is
weaker than that, and the v1 log says so about its own equivalent, labelling the
row *(contaminated)*.

`GROUPING_V1` learns nothing **inside** the test procedure: membership is a
hand-written rule over asset classes, the speeds are three fixed numbers, and
neither is recomputed in any window. But the object itself was chosen on the v1
full sample. The v1 log records the search: a two-speed split — financials slow,
commodities fast — looked strong on futures at 0.70 → 0.82, **failed to replicate
on the independent 10-ETF basket** (0.56 against the reversed grouping's 0.68),
and was changed to three speeds. The speed values 18/9/3 were likewise picked
after seeing the whole sample.

So the honest description of the contest is:

| | fitted inside the test window? | chosen using data that includes the test period? |
|---|---|---|
| learned (per class or per market) | **yes** | speeds yes, membership no |
| `GROUPING_V1` | no | **yes** — on v1 outright; on v2 partly, since 20 markets and 1973–1979 are new to it |
| `GROUPING_V2` | no | **yes** — its two departures from v1 were argued from v2 evidence (§10.2, §10.2a) |
| uniform 12m | no | the number 12 was chosen too |

The fixed grouping's advantage is **far fewer passes over the data**, not zero.
The v1 log counts roughly 80 configurations tried in total; a per-window refit
makes 6 choices per window from a 6-value menu, every window. Fewer passes
overfit less, which is a real effect and not the same claim as out-of-sample
validity.

On v2 the contamination is partial rather than total: 20 of its 50 markets and
the years 1973–1979 were never seen when the grouping was chosen, while the other
30 markets over 1979–2026 were. That is why the same comparison run on v1 data
(where the grouping is contaminated outright) shows a much larger margin — 1.06
against uniform's 0.74 — than on v2, where it shows 0.89 against 0.88.

**That pattern is itself the evidence.** A grouping that captured something real
should hold its margin as the sample grows; one that was fitted should see the
margin shrink where the data is new. The margin shrinks.

## 10.4 What the literature does, tested

Neither of the canonical studies assigns a speed per asset class.
Moskowitz-Ooi-Pedersen use a single 12-month lookback uniformly;
Hurst-Ooi-Pedersen blend 1-, 3- and 12-month signals with equal weight and apply
the same combination to every market. Levine-Pedersen show why that can suffice:
trend signals at different horizons are highly correlated. *No published
per-asset-class lookback table is cited here because none is recalled reliably
enough to quote.*

That default is a testable hypothesis, and it had never been tested against the
grouping. On the v2 walk-forward, uniform blends score **0.78** (3+9+18 and
3+6+12) against the grouping's 0.91 and uniform 12m's 0.88. On a single split the
ordering is the same. The blends are not better here, but nor is the gap
significant.

Notably the **speed set** matters about as much as the assignment: blending
3+9+18 tests at 0.62 on the 2004 split against 3+6+12's 0.45 and 3+12's 0.42,
while assignment by class buys 0.75 − 0.62 = 0.13 on top. Having a slow component
at all may be doing more of the work than giving it specifically to bonds.

## 10.5 The advantage has no stable sign over time

The grouping's edge over uniform 12m, by five-year block on v2:

| block | 1975–79 | 1980–84 | 1985–89 | 1990–94 | 1995–99 | 2000–04 | 2005–09 | 2010–14 | 2015–19 | 2020–24 |
|---|---|---|---|---|---|---|---|---|---|---|
| grouping − uniform | +0.35 | +0.02 | **−0.38** | −0.11 | **−0.59** | −0.32 | +0.19 | +0.40 | +0.13 | +0.34 |

Mean **+0.00**. Before 2012 it averages **−0.21**; after, **+0.33**. A five-year
block's Sharpe carries a standard error near 0.45, so **every one of these
numbers is inside one standard error of zero** and the simplest reading is a null
effect plus noise.

This reconciles numbers that look contradictory: the full walk-forward says
+0.01, the 2004 split +0.31 and the 2012 split +0.32. The splits test only the
recent period, which is the half where the sign happens to be positive.
**The v1 log's +0.20 was measured the same way**, on a test window beginning in
2012.

## 10.6 Why the bigger basket scores lower, and why that is the honest number

On the common period, v2 is **better**, not worse:

| 1979–2026, same grouping and construction | Sharpe |
|---|---|
| v1 full (35 markets) | 0.91 |
| **v2 full (50 markets)** | **0.95** |

The earlier impression came from comparing walk-forwards whose windows start in
different years. Decomposed:

| sleeve | 1979–2000 | 2000–2012 | 2012–2026 | full |
|---|---|---|---|---|
| v1 full (35) | 0.77 | **1.41** | **0.86** | 0.91 |
| v2 full (50) | **1.12** | 1.06 | 0.61 | **0.95** |
| v2, the 30 shared markets | 0.80 | 1.16 | 0.70 | 0.85 |
| v2, the 20 added markets | 0.93 | 0.57 | **0.30** | 0.65 |
| v2, the 7 rebuilt markets | 0.39 | 0.90 | 0.37 | 0.51 |
| v1, the 5 markets v2 dropped | 0.27 | 0.99 | **0.95** | 0.52 |

v2 is far stronger before 2000, when it holds 26–32 markets against v1's 6–11,
and weaker after 2012, where the additions return 0.30 and the five dropped
markets 0.95.

The five dropped markets are the clearest case of a sleeve whose recent run says
nothing about its character: **0.27 over 1979–2000, 0.99 over 2000–2012, 0.95
since** — and 0.52 across the whole sample, the weakest of any sleeve in either
basket. §11.3 attributes the v1-versus-v2 gap on the 2012 split almost entirely
to them.

Within the additions since 2012: platinum **−0.27** (with palladium, before it
was dropped), the Chicago grains and cotton −0.02, livestock +0.09, the six
currencies +0.15, Australian and Canadian bonds +0.21, energy +0.29, the S&P
+0.30.

**The direction of the bias matters more than the numbers.** v1's 35 markets were
assembled from what the continuous-series tables happened to offer and what
looked usable; v2's 21 additions were included by an *ex-ante* rule — every
liquid CME market — without regard to how they had performed. A basket selected
the first way is flattered by hindsight; one selected the second way is not.
Palladium returning −0.27 since 2012 is what an honest basket contains.

So **v2's 0.59 since 2012 is the better estimate of what to expect, and v1's 0.86
is not.** It also sits inside the range this project has already recorded for the
strategy in practice — in-sample Sharpes above 1 against live net results of
0.3–0.7 — where 0.86 does not.

## 10.7 What is retracted, and what stands

**Retracted.** The three-speed grouping as a finding worth +0.20 Sharpe. On v2 it
is worth **+0.01** against a uniform 12-month lookback over the full
walk-forward, with no stable sign across decades. The v1 measurement was not
wrong — it was in-sample, on a 35-market basket, over a test window starting in
2012 — but it **does not transfer**, and it was presented with more confidence
than a single split can carry.

**Stands.**

* *Reversal is costly.* Turning `GROUPING_V2` upside down — bonds on 3 months,
  energy on 18 — costs **0.54 on v1 and 0.44 on v2** on the 2012 split, and
  **0.54 and 0.31** in the walk-forward. Speeds are not interchangeable, even
  though the specific assignment cannot be identified. Earlier drafts supported
  this with the reversal of the *learned* grouping, a different and milder test.
* *Fitting speeds to the sample makes things worse.* Learning loses on all three
  panels, and on a single split fit and test correlate −0.70.
* *Livestock belongs on a slow speed.* Not because 18m beats 9m — they are
  identical — but because 3m is negative, and the two markets are the least
  correlated in the basket.
* *The metals split by trend behaviour, not by name.* Gold, platinum and silver
  tilt slow; aluminium, copper, nickel and zinc tilt fast; the two groups'
  profiles correlate −0.17 with each other. Moving platinum across that line
  pays nothing and was done for consistency (§10.2a).
* *An unlisted asset class must raise.* Livestock spent the whole of v1 in the
  wrong bucket because a default existed to catch it.

**Open.** Whether the grouping's collapse is caused by breadth — 50 markets and
effective breadth 9.1 averaging away per-market misassignment that 35 markets and
8.0 could not. The test is to draw random 35-market subsets from v2 and see where
v1's advantage falls in the distribution. Not run.

---

# Part 11 — v1 against v2, one window, one code path

`--dataset 1|2` exists so that a difference can be attributed to the data rather
than to a code change. This part uses it: identical configurations, identical
window (1979-01 → 2026-03), split 2012-01.

## 11.1 The matched split

Test 2012-02 → 2026-03, 170 months, standard error **0.27**.

| configuration | v1 fit / **test** | v2 fit / **test** | test Δ |
|---|---|---|---|
| v2 grouping | 0.94 / **0.85** | 1.10 / **0.61** | −0.24 |
| v1 grouping | 0.94 / 0.85 | 1.10 / 0.55 | −0.30 |
| blend 3+9+18 | 0.77 / 0.67 | 1.03 / 0.42 | −0.25 |
| uniform 12m | 0.83 / 0.42 | 1.19 / 0.29 | −0.13 |
| learned | 0.96 / 0.51 | 1.28 / 0.28 | −0.23 |
| blend 3+6+12 | 0.85 / 0.43 | 1.12 / 0.18 | −0.25 |
| blend 3+12 | 0.89 / 0.38 | 1.24 / 0.14 | −0.24 |
| **`GROUPING_V2` reversed** | 0.57 / **0.30** | 0.89 / **0.17** | −0.13 |
| learned reversed | 0.62 / 0.16 | 1.05 / −0.00 | −0.16 |

**All nine fit better and test worse on v2.** The v1 column reproduces the v1
log, which records uniform 12m at 0.82 / 0.38 and the three-speed grouping at
0.93 / 0.81 for this split; the small differences come from ending at 2026-03
rather than 2026-08.

**Exactly one row is fitted on the fit period: `learned`.** It re-estimates a
lookback per asset class from 1979–2012 data. Every other row is a constant —
both groupings, uniform 12m, the blends and the two reversals are the same
configuration in both halves — so for those rows the "fit" column is that fixed
strategy *measured* over 1979–2012, not fitted to it.

`GROUPING_V1` on v2 gives the same picture one row down, 0.55 against v1's 0.85.

### The fit-to-test drop is the period, not fitting

Every row falls from fit to test, and on v2 the fall looks like overfitting —
1.10 down to 0.61. It is not, and the bottom two rows are the proof: they are
**deliberately wrong** configurations, which nothing can have overfitted, and
they fall the furthest.

| configuration | v1 drop | v2 drop |
|---|---|---|
| v2 grouping | 0.09 | 0.49 |
| v1 grouping | 0.09 | 0.55 |
| blend 3+9+18 | 0.10 | 0.61 |
| `GROUPING_V2` reversed | 0.27 | 0.72 |
| uniform 12m | 0.41 | 0.90 |
| blend 3+6+12 | 0.42 | 0.94 |
| learned | 0.45 | **1.00** |
| learned reversed | 0.46 | **1.05** |
| blend 3+12 | 0.51 | **1.10** |
| **mean** | **0.31** | **0.82** |

Three things an overfitting story would require, none of which hold:

* **the most-fitted configurations should fall furthest.** The two largest falls
  on v2 are `blend 3+12` — two fixed numbers, nothing estimated — and `learned
  reversed`, which is wrong on purpose.
* **a deliberately wrong configuration should be unaffected.** Both reversals
  fall by 0.72 and 1.05.
* **fit-period ranking should predict test-period ranking.** Across
  configurations, fit and test Sharpe correlate **+0.68 on v1 and +0.03 on v2**.
  On v2 the fit period carries essentially no information about the test period
  *for any configuration*.

**v2 falls further than v1 (0.82 against 0.31) because both ends move.** Its fit
period is stronger — 1.11 against 0.82 on average, since v2 holds 26–49 markets
over 1979–2012 where v1 holds 4–35 — and its test period is weaker, 0.29 against
0.51, because the twenty added markets return 0.30 after 2012 (§11.3).

The period itself is the common factor, and it is not a surprise:
`docs/cta-primer.md` records the SG Trend index going sideways across 2011–2019,
with +27.3% in 2022, −3.3% in 2023 and +2.4% in 2024. The test window here spans
almost exactly that stretch.

**So read the table down a column, not across a row.** Within v2, 0.61 for the
grouping against 0.29 for uniform and 0.17 for the reversal is information. The
drop from 1.10 to 0.61 is not a property of the configuration at all.

## 11.2 Walk-forward, and why it disagrees with the split

| configuration | v1, 451 months | v2 from 1979, 446 | v2 full, 518 |
|---|---|---|---|
| v2 grouping | **1.06** | **0.92** | **0.89** |
| v1 grouping | 1.06 | 0.88 | 0.87 |
| uniform 12m | 0.74 | 0.86 | 0.88 |
| learned | 0.86 | 0.76 | 0.85 |
| learned, *reversed* | 0.53 | 0.48 | 0.66 |
| **grouping − uniform** | **+0.32** | +0.06 | **+0.01** |

The reversed row is the **learned** grouping reversed, not `GROUPING_V2`
reversed — that one scores 0.52 / 0.60 / 0.58 across the three columns. Both
collapse; they are different falsifications and the label used to hide it.

The split says the grouping is worth +0.43 on v1 and +0.32 on v2; the
walk-forward says +0.32 and +0.01. They are measuring different stretches of
time, and on v2 the grouping's edge changes sign by decade (§10.5): **−0.21**
before 2012, **+0.33** after. The split tests only the second half.

## 11.3 The whole difference is which markets are in the basket

Same window, same grouping, sleeve by sleeve, tested from 2012-02:

| sleeve | Sharpe |
|---|---|
| the 30 shared markets, **v1** data | 0.685 |
| the 30 shared markets, **v2** data | **0.695** |
| v2's shared markets truncated to v1's death dates | 0.698 |
| the **5 markets v1 has and v2 dropped** | **0.928** |
| the **20 markets v2 added** | **0.314** |

Construction accounts for **0.010** and the shrinkage of v1's basket — gold and
silver dying in 2022-11, US rates in 2025-04 — for **0.003**. Neither explains
anything. The entire gap is composition.

And the composition effect reverses between periods. Measured from 1979-01, so
that both sleeves cover the same years, the five dropped markets are the
**weakest** sleeve in either basket at **0.52** and the twenty additions return
**0.65**; over 2012–2026 the five return 0.928 and the twenty 0.314. (Over v2's
own full span from 1973 the twenty score 0.56, but that window is unavailable to
the v1-only sleeve, so it is not the comparison to quote.) Both baskets are dominated in this window by their own
exclusive markets, and each of those sleeves did the opposite of what it did over
the full sample. **One test window cannot separate the two baskets.**

## 11.4 A sampling test that does not answer the question

Drawing 1500 random 35-market subsets from v2 over the same window gives a mean
Sharpe of 0.582, sd 0.073, maximum 0.816. v1's 0.848 exceeds every draw.

That looks like decisive evidence of selection, and it is not — **five of v1's
markets are absent from v2 and cannot appear in any draw**, and those five are
precisely the sleeve carrying v1's result. The distribution shows only that v2's
fifty markets cannot assemble v1's number, which is a different statement. The
first reading of this result in the course of the work drew the wrong conclusion
from it, and the tool now prints the caveat above the percentile.

Nor is "selection" the right word even loosely. Those five markets entered the v1
basket because the continuous-series tables happened to carry them, years before
any of this analysis. **Luck concentrated in a sleeve we later removed** is the
accurate description, and their 0.52 over the full sample against 0.928 recently
is what luck looks like.

## 11.5 What changes and what does not

| | v1 | v2 |
|---|---|---|
| ranking of configurations | grouping > blends > uniform > learned > reversed | identical |
| reversing the grouping in use | 0.85 → 0.30 | 0.61 → 0.17 |
| more fitting → worse out of sample | yes | yes |
| fixed grouping beats refitting | yes | yes |

**Every methodological conclusion holds on both. Only the levels move.**

v2 is not worse data; it is a harder sample — fifty markets instead of
thirty-five, twenty of them added by an ex-ante liquidity rule rather than by
what happened to be available, and five thin markets removed that turned out to
have had an extraordinary recent run. v1's 0.85 and v2's 0.61 both sit inside the
band the v1 log itself gives for honest out-of-sample results, **0.61–0.87**. The
difference is that v1's number leans on five markets a liquidity screen removes
and v2's leans on none.
