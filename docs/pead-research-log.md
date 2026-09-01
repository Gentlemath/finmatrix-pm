# PEAD research log

Findings from the post-earnings-announcement-drift event study on **S&P 500
announcers, 1985–2026** (CRSP CIZ daily + Compustat quarterly + IBES). Only
aggregate results are recorded here; the underlying data is licensed and lives in
the gitignored `local_data/`.

## Setup

Two constructions are run side by side, so the effect of a better surprise
measure can be separated from the effect of a better benchmark:

| | **A — baseline** | **B — upgrade** |
|---|---|---|
| Surprise | Compustat SUE (seasonal random walk) | IBES analyst SUE: (actual − consensus median) / dispersion |
| Abnormal return | market-adjusted | size-decile-adjusted (`benchmark_col`) |
| Event date | Compustat `rdq` | IBES `anndats` |
| Events | 116,869 | 115,917 |

- **Windows**: announcement `[0,+1]` and drift `[+2,+63]` trading days, both in
  event time relative to the announcement.
- **Portfolios**: SUE quintiles; the reported figure is the **Q5 − Q1 spread** in
  percent.
- **Reproduce**: `examples/pead_event_study.py` (baseline + size split) and
  `examples/pead_analyst_study.py` (A vs B + figure). Both read cached CSVs and
  run offline; `examples/cache_pead_data.py` / `cache_ibes_data.py` fetch inputs.

## Definitions

Reference for the terms used throughout this log.

### SUE — Standardized Unexpected Earnings

The **surprise** in an announcement: how far actual earnings landed from what was
expected, scaled by how noisy that firm's surprises normally are. Two versions are
compared here.

**Baseline — seasonal random walk** (`strategy/pead.py`,
`standardized_unexpected_earnings`):

```
sue = (eps_q - eps_{q-4}) / rolling_std(eps_q - eps_{q-4})
```

"Expected" is *the same fiscal quarter one year earlier* (`q-4`), which handles
seasonality — a retailer's Q4 is compared with last year's Q4, not with Q3. The
numerator is the surprise in dollars per share; dividing by the trailing 8-quarter
standard deviation of that same seasonal difference expresses it in **standard
deviations of surprise**, so a stable utility beating by 5c and a volatile tech
firm beating by 5c are not treated as equally surprising.

**Upgrade — analyst SUE** (`analyst_sue`):

```
sue = (actual - consensus_median) / dispersion
```

using the last consensus before the announcement. Analysts already incorporate
last year, the industry, and company guidance, so their consensus is a far better
proxy for *market* expectations than last year's earnings. That is why panel B's
announcement spread is more than double panel A's.

The standardizing step is what makes the number comparable across firms — and
therefore rankable.

### Quintiles

Each month, all announcing firms are sorted by SUE and cut into five equal-sized
groups (`examples/pead_analyst_study.py`, `quintile_within_month`):

- **Q1** — lowest fifth: the biggest negative surprises
- **Q5** — highest fifth: the biggest positive surprises

Two design points. The sort happens **within each calendar month**
(`groupby("ym")`), so firms are always ranked against their contemporaries and no
drift creeps in from SUE levels changing across decades. And it is a **relative**
ranking, not an absolute threshold: Q5 means "the best fifth of surprises this
month", so buckets stay equally populated whether it was a strong or weak quarter
overall.

**Q5 - Q1** is then the return on a portfolio long the best-surprise fifth and
short the worst — the number the era tables report.

### CAR — Cumulative Abnormal Return

The event-window return with a benchmark subtracted, accumulated over the window.
The "abnormal" part is the point: a stock rising 3% tells you little until you know
what comparable stocks did. Both adjustments below define what "comparable" means.

### Market adjustment (panel A)

Subtract the market's return that day:

```
abnormal = stock_return - market_return
```

Simple, but it assumes every stock should move one-for-one with the market, and it
leaves any size tilt sitting inside the "abnormal" return.

### Size adjustment (panel B)

Subtract the return of the stock's own **size decile** instead
(`examples/pead_analyst_study.py`, `size_benchmark`):

```
abnormal = stock_return - (equal-weighted return of its size decile that day)
```

This is a **characteristic-matched** benchmark, and it is the better one because
size predicts returns on its own. If smaller firms both have larger surprises and
outperform, a market-only adjustment credits part of that outperformance to PEAD
when it is really the size effect.

Two implementation details that matter:

- Deciles are formed on **prior-month** market cap and held for the following
  month (`mo["ym"] = mo["ym"] + 1`), so there is no look-ahead from using a
  capitalization not yet observable.
- The benchmark is recomputed **per day**, so it tracks the size cohort through the
  whole event window rather than applying one static adjustment.

This is also the reason A and B are not a clean one-variable comparison: B changes
the surprise measure *and* the benchmark at once.

## Headline: the drift decayed, the announcement reaction grew

**A — Compustat SUE + market-adjust** (Q5−Q1, %):

| Era | n | announce [0,+1] | drift [+2,+63] |
|---|---|---|---|
| 1985–1994 | 22,161 | 1.13 | **2.31** |
| 1995–2000 | 19,902 | 0.89 | 0.72 |
| 2001–2006 | 19,923 | 1.21 | 1.04 |
| 2007–2015 | 27,742 | 2.03 | 1.06 |
| 2016–2026 | 27,141 | **2.35** | 0.92 |

**B — IBES SUE + size-adjust** (Q5−Q1, %):

| Era | n | announce [0,+1] | drift [+2,+63] |
|---|---|---|---|
| 1985–1994 | 26,093 | 1.53 | 2.45 |
| 1995–2000 | 18,346 | 3.81 | **3.29** |
| 2001–2006 | 17,460 | 5.02 | 0.52 |
| 2007–2015 | 26,823 | **5.99** | 0.41 |
| 2016–2026 | 26,735 | 5.31 | 0.65 |

The two windows move in **opposite directions**. The announcement reaction roughly
doubles in A (1.13 → 2.35) and more than triples in B (1.53 → 5.31), while the
drift falls by roughly 60% in A and by about 80% in B from its peak. Information
that used to leak out over the following quarter is now impounded in the first two
days.

The decay is **not** a smooth trend — it is a break. In A the drift drops between
1985–1994 and 1995–2000; in B it survives the 1990s (3.29% in 1995–2000, the
highest of any era) and then collapses after 2000, from 3.29% to 0.52%. That
timing lines up with Reg FD (2000) and decimalization (2001), and with the general
spread of algorithmic execution — but this study identifies a break, not a cause.

## The widening announcement spread is mostly *bad* news

The Q5−Q1 spread collapses two quintiles that have not moved together. Mean
announcement CAR (%) by era and quintile:

**A — Compustat SUE + market-adjust, announce [0,+1]:**

| Era | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| 1985–1994 | −0.40 | −0.22 | 0.09 | 0.58 | 0.73 |
| 1995–2000 | −0.13 | −0.24 | 0.48 | 0.56 | 0.76 |
| 2001–2006 | −0.26 | −0.30 | 0.46 | 0.82 | 0.95 |
| 2007–2015 | −0.86 | −0.32 | 0.29 | 0.87 | 1.16 |
| 2016–2026 | **−1.24** | −0.23 | 0.33 | 0.53 | **1.11** |

**B — IBES SUE + size-adjust, announce [0,+1]:**

| Era | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| 1985–1994 | −0.61 | −0.23 | 0.11 | 0.45 | 0.92 |
| 1995–2000 | −1.44 | −0.45 | 0.23 | 1.00 | 2.36 |
| 2001–2006 | −2.25 | −0.66 | 0.47 | 1.42 | 2.77 |
| 2007–2015 | −2.95 | −0.86 | 0.49 | 1.43 | 3.04 |
| 2016–2026 | **−2.84** | −0.59 | 0.37 | 1.15 | **2.47** |

Decomposing the change from the first era to the last:

| | Q1 move | Q5 move | spread change | Q1 share |
|---|---|---|---|---|
| A baseline | −0.84 | +0.38 | +1.22 | **69%** |
| B upgrade | −2.23 | +1.55 | +3.78 | **59%** |

Roughly two thirds of the baseline's widening comes from **bad news being punished
harder**, not from good news being rewarded more — the Q5 reaction is nearly flat
across four decades (0.73% → 1.11%) while Q1 triples. The market's response
function has become markedly asymmetric.

The **drift** decay, in contrast, is symmetric: in A, Q5 falls 0.61pp (1.26 → 0.65)
while Q1 rises 0.78pp (−1.05 → −0.27); B behaves the same way. Both tails converge
on zero together. So the two headline movements have different characters — the
drift simply disappeared at both ends, while the announcement reaction rotated
toward the downside.

Both eras' most recent column also shows a small retreat from the 2007–2015 peak
in B (Q5 3.04 → 2.47, Q1 −2.95 → −2.84), which may be the beginning of a plateau
or may be noise; one era is not enough to say.

## The analyst-SUE upgrade sharpens the signal — and shrinks what's left to trade

Switching from a seasonal-random-walk SUE to analyst-based SUE more than doubles
the modern announcement spread (2.35% → 5.31%). Analysts' consensus is a much
better proxy for what the market expected than last year's same-quarter earnings.

But the better measure leaves *less* drift, not more: B's modern drift (0.41–0.65%)
is below A's (0.92–1.06%). Sharpening the surprise measure concentrates the
response into the announcement window. Read carefully, that is a caution for
trading: the part you can measure best is the part you cannot capture, because it
happens in the two days around an event you must already be positioned for.

## Size: the drift survives where arbitrage is hardest

Splitting the baseline at median market cap (Q5−Q1, %):

| Era | large announce | large drift | small announce | small drift |
|---|---|---|---|---|
| 1985–1994 | 0.72 | 1.53 | 1.33 | **2.64** |
| 1995–2000 | 0.24 | 0.33 | 1.54 | 1.00 |
| 2001–2006 | 0.99 | 0.97 | 1.45 | 1.70 |
| 2007–2015 | 1.37 | 1.08 | 2.71 | 1.27 |
| 2016–2026 | 1.48 | **0.61** | 3.13 | **1.41** |

In the modern era small firms retain **2.3× the drift** of large ones (1.41% vs
0.61%) and more than double the announcement reaction. This is the classic
limits-to-arbitrage pattern: the effect persists where it is costliest to trade.

Note the ceiling on this result — "small" here means *below-median S&P 500*, which
is still a large, liquid, heavily-covered firm. The genuine small-cap universe,
where PEAD is documented to be strongest, is outside this sample entirely, so
these figures are a **lower bound** on the effect in the broad market.

## The effect is ordered, not a tail artifact

Full-sample drift CAR by SUE quintile (%):

| | Q1 | Q2 | Q3 | Q4 | Q5 | monotone |
|---|---|---|---|---|---|---|
| A baseline | −0.53 | −0.51 | −0.22 | +0.00 | +0.67 | yes |
| B upgrade | −0.56 | −0.48 | −0.26 | +0.19 | +0.83 | yes |

Both constructions are monotone across all five quintiles. The spread is a real
ordering in the surprise variable, not one extreme bucket doing all the work.

This holds **pooled over the full sample**; it does not hold era by era. In A's
drift, 1995–2000 has Q2 at −1.53 against Q1 at −0.19, and 2007–2015 has Q2 through
Q4 within 0.2pp of each other in no particular order. The extremes (Q1, Q5) are
ordered consistently; the middle buckets are noise at era resolution. Read the
era x quintile tables for the tails, not the middle.

## Takeaways

1. **The drift decayed; the announcement reaction did not.** Faster impounding,
   not a vanished effect — the information is still there, it just arrives sooner.
2. **The decay is a post-2000 break**, sharpest in the analyst-SUE construction,
   not a gradual fade.
3. **Better surprise measure ⇒ bigger announcement spread, smaller drift.**
   Measurement quality moves return from the tradeable window to the untradeable one.
4. **Size is the surviving dimension** — modern drift is 2.3× larger in
   below-median-cap S&P 500 firms, consistent with limits to arbitrage.
5. **The widening announcement spread is asymmetric** — ~69% (A) / ~59% (B) of it
   comes from Q1, i.e. bad news punished harder, while Q5's reaction is nearly flat
   across four decades in the baseline. The drift decay, by contrast, is symmetric.
6. **Monotone in SUE** for both constructions pooled, though only the extreme
   quintiles are reliably ordered within any single era.
7. **Nothing here is net of costs.** A 0.6–0.9% quintile spread over 62 trading
   days is gross, on a 100-name long-short rebalanced every quarter. Costs are not
   a detail at this magnitude — they are the whole question.

## Methodological notes

- **Universe caveat dominates.** S&P 500 announcers are the most liquid, most
  analyst-covered, most arbitraged stocks in the market — precisely where PEAD
  should be weakest. Every number here understates the broad-market effect.
- **Event date matters**: A uses Compustat `rdq`, B uses IBES `anndats`. They
  disagree for some announcements, which is part of why the event counts differ
  (116,869 vs 115,917) and why the two panels are not strictly comparable
  event-for-event.
- **Benchmark choice is not neutral**: B changes *both* the surprise measure and
  the benchmark (size-decile rather than market). The A-vs-B gap therefore mixes
  two changes and should not be read as the analyst-SUE effect alone.
- **No risk adjustment beyond market/size**, and no standard errors on the era
  spreads — these are mean CARs, so era-to-era differences of a few tenths of a
  percent should not be over-read.
- The full-sample quintile table pools all eras and so is dominated by the
  post-2007 observations, which are roughly half the sample.

## References

- Ball & Brown (1968), *An Empirical Evaluation of Accounting Income Numbers*.
- Bernard & Thomas (1989), *Post-Earnings-Announcement Drift: Delayed Price
  Response or Risk Premium?*
- Livnat & Mendenhall (2006), *Comparing the Post-Earnings Announcement Drift for
  Surprises Calculated from Analyst and Time Series Forecasts*.
- Chordia, Goyal, Sadka, Sadka & Shivakumar (2009), *Liquidity and the
  Post-Earnings-Announcement Drift*.
- McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return
  Predictability?*
