# Quant Strategy Exploration II — Structural, Cross-Asset, Volatility & Microstructure

*Evidence-based education, not investment advice. Compiled from a multi-source, adversarially
verified deep-research pass (July 2026). Companion to [strategy-research.md](strategy-research.md),
which covers single-name US-equity reversal, momentum, value/quality, event/PEAD, and ML/alt-data
stock-picking — deliberately **not** repeated here.*

This round targets four territories the first report skipped, with an **education-first** lens
(best ideas to learn, even if they need instruments/data beyond CRSP/Compustat/IBES): **(1)
structural / non-forecasting edges, (2) cross-asset carry & trend, (3) volatility & derivatives,
(4) market microstructure.**

## How to read the verification tags

Each claim carries an honesty tag reflecting *how hard it was checked in this pass*:

- **[V] Verified** — survived adversarial verification (independent agents tried to refute it;
  a majority failed). Vote shown, e.g. `3-0`.
- **[E] Extracted** — pulled from a named primary source (peer-reviewed journal, Fed research,
  reputable practitioner) but **not independently re-verified** in this run. Treat as "the source
  says," pending your own check.

The most important meta-finding: **the two most famous structural edges here (the index effect and
the overnight drift) are documented as DECAYED or GONE.** They're now case studies in
post-publication decay, not live opportunities — which is exactly the honest lesson worth learning.

---

## Territory 1 — Structural / Non-Forecasting Edges

These are returns that come from predictable or forced trading — for example, index funds that
*have* to buy a stock when it joins an index — rather than from forecasting anything. The attraction
is that you don't need to predict earnings or prices; you just need to be on the right side of a flow
you can see coming. The problem is that this only works while the flow is still a surprise. Once the
timing is public and everyone expects it, other traders position ahead of it and the price moves
before the forced buyer arrives, so there is nothing left to capture. Most of the well-known examples
below have stopped working for exactly this reason. That makes them useful to study as clear cases of
how a structural edge ends.

### 1.1 The index-reconstitution ("index effect") — has decayed to about zero **[V, 3-0]**

- **The idea:** When a stock is added to the S&P 500, index funds must buy it (and must sell it on
  deletion). That forced, price-insensitive buying used to push the added stock up in the days around
  the change, so you could buy ahead of the index funds.
- **Evidence and current status:** Greenwood & Sammon, *"The Disappearing Index Effect"* (Journal of
  Finance 2025). The return on additions fell from **3.4% (1980s) → 7.6% (1990s) → 5.2% (2000s) →
  0.8% (2010–2020, no longer statistically different from zero)**; deletions moved from
  −4.6% / −16.6% / −12.3% to **−0.6% (also about zero)**.
- **Why this is striking:** The forced buying got *larger*, not smaller — the share of the market held
  by index funds rose from almost nothing to roughly 7–8%. So if forced buying alone moved prices, the
  effect should have grown. Instead it vanished. The reason is that index changes are now announced on
  a fixed schedule with public rules, so other traders buy the stock first and sell it to the index
  funds on the day they are required to buy. Predictable buying does not move the price; only
  unexpected buying does.

### 1.2 The index effect has reversed for stocks moving between the S&P 400 and S&P 500 **[V, 3-0]**

- **Finding:** Vijh & Wang (Financial Management 2022). During **2016–2020**, 74 stocks promoted from
  the S&P MidCap 400 to the S&P 500 *fell* **−2.48%** on the 3-day announcement, and 50 stocks demoted
  the other way *rose* **+1.37%** — the opposite of the old pattern. This reversed gradually from the
  2001–2015 evidence (promotions +1.49%).
- **Why:** By end-2020, institutions owned a larger share of S&P 400 stocks (86.0%) than of S&P 500
  stocks (78.9%). When a stock is promoted, S&P 500 funds buy it but S&P 400 funds sell it, and the
  selling is now the larger flow, so the net effect flipped.
- **Scope note:** Stocks added to the S&P 500 from *outside* any S&P index (not a promotion) still rose
  significantly (+4.16%). The reversal is specific to moves between the two indexes, which now make up
  most index changes (over 80% of additions, versus about 40% in the 1990s). This is also part of why
  1.1 faded.

### 1.3 The S&P 500 futures "overnight drift" — was real, and has gone to about zero since 2021 **[V, 3-0]**

- **The observation:** Historically, the best single hour of the 24-hour day for S&P 500 futures was
  **2:00–3:00 a.m. New York time** (when European markets open) — about **3.7% per year**, and before
  2021 this one hour accounted for **more than 60%** of the contract's total return.
- **Why it happened:** At the US close, more investors want to sell than buy, so the market makers who
  take the other side end up holding more inventory than they want. They are paid a small return for
  holding that inventory overnight until European buyers arrive and take it off their hands. The size
  of this return is, roughly, the size of the leftover imbalance times the riskiness of holding it,
  divided by how much capital is available to hold it. Ordinary news (economic data, Fed announcements,
  earnings) does *not* explain it.
- **It was never actually tradable by an outside trader:** after paying the bid-ask spread, the
  strategy's return went from a Sharpe of 1.1 down to **−0.5**. The people who earned it were the
  market makers, as a normal part of their business, not traders placing a separate bet.
- **Why it disappeared:** The NY Fed follow-up (*"The Disappearing Overnight Drift"*, 2026) finds the
  drift has **averaged about zero since 2021**. Importantly, the market was not calmer — volatility was
  roughly unchanged. What changed is that the leftover end-of-day imbalance shrank by about half,
  because automated market makers now split their orders into smaller pieces and pass much less
  inventory to others at the close. This is a change in trading technology, so it is unlikely to
  reverse. An ETF launched in 2022 to capture this drift closed about 14 months later.
- Source: Boyarchenko, Larsen & Whelan, *"The Overnight Drift"* (NY Fed Staff Report 917).
- **Note:** A stronger claim that the drift was robust in almost every year and month did *not* survive
  verification (refuted 0-3). Its historical existence is solid; claims that it was bulletproof are not.

### 1.4 Leveraged and inverse ETF daily rebalancing **[E — weaker sourcing]**

- **The mechanism:** A 2x or −1x ETF has to trade every day to keep its stated leverage: it buys more
  exposure after the market goes up and sells after it goes down, in the same direction as the day's
  move. This trading is concentrated in the **last 30–60 minutes** of the US session and is estimated
  at **$30–50 billion**, so its timing is predictable.
- **Feedback effect:** Because the fund buys after gains and sells after losses, a large down day forces
  large selling into an already-falling market, which can add to the move.
- **Current status:** Other traders are increasingly positioning ahead of this rebalancing window, which
  reduces what is left to capture. This item rests on weaker sources than 1.1–1.3.

### 1.5 Overnight versus intraday returns **[E]**

- **Finding (Lou, Polk & Skouras, *"A Tug of War"*):** Many well-known stock strategies earn their
  returns almost entirely during one part of the day and give some back during the other. A portfolio
  built on past overnight returns earns **+3.47% per month** overnight and **−3.02% per month** intraday.
  Of 14 strategies studied, 9 earn their entire return during the trading day, while momentum and
  short-term reversal earn theirs entirely overnight.
- The pattern is stable even when the signal is lagged by years, so it is not a short-lived data
  glitch — **but transaction costs remove most of the tradable profit.** It is more useful as a fact
  about *when* returns show up than as a strategy on its own.

### 1.6 How these edges ended, and which structural edges last

The examples above did not all stop working for the same reason. It helps to separate three cases,
because they carry different lessons.

1. **Competed away.** Traders learn the forced flow is coming and buy ahead of it, so the price adjusts
   before the forced buyer arrives. This is the index effect. The forced buying is larger than ever, but
   because the schedule and rules are public, it is no longer a surprise, and only a surprise moves
   prices.
2. **Never really tradable.** The return looked good on paper but did not survive trading costs, so
   there was never a profit for an outside trader to compete for. Parts of the overnight drift and the
   overnight/intraday patterns fall here.
3. **The underlying risk was removed.** There was a genuine payment for holding a risk, but the *amount*
   of risk that had to be held was reduced at the source, so the payment shrank with it. This is what
   happened to the overnight drift: the payment for holding overnight inventory did not fall because
   holding it became safer per unit; it fell because there was much less inventory to hold, once
   automated market makers changed how they trade. When the thing generating a premium is a temporary
   imbalance that better technology can shrink, the premium can disappear permanently.

Case 3 is worth stating carefully because it splits the "you get paid to bear risk others avoid" idea
into two parts: the *amount* of risk that must be held, and the *price* paid per unit of that risk. The
overnight drift died because the amount fell to nearly zero, even though the price per unit was
unchanged. A premium is fragile when the amount of forced risk-bearing is a side effect of how trading
is currently done, because that can be engineered away. It is more durable when the amount of risk is a
real feature of the world that cannot be reduced — for example, the risk that a trend reverses sharply,
or that a market crashes.

Two practical takeaways for judging any structural edge:

- **If the edge depends on flow that others can predict, it will not last.** As soon as the timing is
  known, someone positions ahead of it. Durability requires that the flow stays genuinely hard to
  anticipate — such as forced selling during a crisis (margin calls, fund redemptions, forced
  deleveraging), which does not happen on a public schedule.
- **To earn a risk-based premium, being willing to sit through the losses is not enough — you also
  have to survive long enough to see them turn around.** The largest payments for supplying liquidity
  come exactly when markets are under stress, which is also when your own funding is most likely to be
  pulled and your investors most likely to withdraw. So even if you are completely willing to hold the
  position, you can be forced out at the worst possible moment. Whether you can actually stay in depends
  on how your capital is structured: funding that cannot be withdrawn during the stress (long-term
  locked-up capital, or insurance premiums that keep coming in) lets you hold on; short-term borrowing
  that lenders can recall does not. This is why the same return is available to a well-funded firm but
  not to a trader using borrowed money that can be called away at the worst moment — the difference is
  the funding, not the courage.

---

## Territory 2 — Cross-Asset Carry & Trend (the capacity-rich workhorses)

If Territory 1's lesson is "transparent edges die," Territory 2's is the opposite: **diversified,
economically-grounded premia harvested across many asset classes have proven the most durable things
in quant** — though the headline Sharpes are in-sample/gross, and live net numbers are lower.

### 2.1 Time-series momentum / trend-following **[V, mixed]**

- **Idea:** An asset's own past **12-month** excess return positively predicts its next-month return —
  go long recent winners, short recent losers, size positions inversely to volatility, rebalance
  monthly. Applied across equity-index, bond, currency, and commodity futures.
- **Evidence:** Moskowitz, Ooi & Pedersen, *"Time Series Momentum"* (Journal of Financial Economics
  2012): positive 12-month TSM profits in **all 58** liquid futures (52/58 individually significant);
  diversified Sharpe **>1 in-sample (~2.5× the equity market)**, little correlation to standard factors.
  **[whole-universe finding V, 3-0]**
- **Two distinct critiques (an earlier draft wrongly merged them into one):**
  - *Kim, Tse & Wald* — the **volatility-scaling** critique: unscaled TSM portfolios perform far worse,
    so a large share of the profit comes from the inverse-volatility position sizing (a volatility-timing
    effect), not the trend signal. If right, the strategy still works but the *mechanism* is partly
    volatility timing — a different, separately documented effect.
  - *Huang, Li, Wang & Zhou* (JFE 2020, *"Is It There?"*) — a **statistical-power** critique: MOP's
    pooled regression forces one coefficient across all 58 assets; drop the pooling and asset-level
    predictability is largely indistinguishable from noise. This challenges **the signal itself**, which
    under our own durability test ("does the mechanism still exist?") deserves more than a footnote.
  - *The strongest answer to Huang et al. is out-of-sample, not an in-sample test:* Hurst, Ooi &
    Pedersen, *"A Century of Evidence on Trend-Following Investing"* (1880–2013), find trend profitable
    across a century and many markets the original authors never saw — hard to reconcile with "the
    1985–2009 signal was a pooling artifact." But that does **not** rebut Kim-Tse-Wald, because the
    century study also volatility-scales, so "how much is trend vs volatility timing" stays genuinely open.
- **What actually sustains it — crash risk cannot be the reason.** TSM performs *best* in the market's
  most extreme up and down moves (e.g., Q4 2008): it has a **crash-hedging payoff shape** **[V, 3-0]**.
  But you don't get *paid* to hold something that protects you in crashes — so the discomfort that
  sustains the premium must be the opposite: **long, trendless, choppy stretches where trend bleeds small
  losses while equities rise** — e.g. the roughly flat **2011–2019** CTA period while stocks compounded
  double digits. That is patience/career risk on a multi-year horizon, not drawdown risk, and it is what
  keeps the premium from being competed away.
- **Live numbers and the behavioral bar:** the Sharpe>1 is in-sample (1985–2009) and gross **[this
  figure only verified 2-1]**; **live CTA net Sharpes have run ~0.3–0.7 post-2009.** Using the drawdown
  arithmetic from earlier: at S=0.5 about **21.5%** of arbitrary 30-month windows end below cash; at
  S=0.3, about **32%** — roughly one in three. And because trend returns are negatively skewed, the true
  odds are a little worse than these Gaussian figures. At these Sharpe levels the endurance requirement,
  not the signal, is most of the difficulty.

### 2.2 Carry, everywhere **[V, 3-0]**

- **Idea:** A security's expected return decomposes into **carry** (the model-free, ex-ante return if
  prices don't move) plus expected price appreciation. Buy high-carry, sell low-carry — across global
  equities, bonds, commodities, Treasuries, credit, and options.
- **Evidence:** Koijen, Moskowitz, Pedersen & Vrugt, *"Carry"* (JFE 2018): long-high/short-low carry
  earns ~**0.8 annualized Sharpe** per asset class on average; a **diversified cross-asset carry
  portfolio ~1.1–1.4 in-sample.**
- **Tail risk, and why it should compress rather than die:** The three biggest global carry drawdowns
  (1972–75, 1980–82, **2008–09**) coincide with major global recessions — carry pays a steady return
  most of the time and loses heavily in crises, exactly when the holder's other assets and income are
  also impaired. That is the textbook shape of a **compensated risk premium**: paid to bear losses at
  the worst possible time. Under the durability test that predicts **compression, not death** — the
  reason it pays still exists (unlike the index effect's vanished mechanism).
- **Carry and trend have opposite convexity — this, not just low correlation, is why they are combined.**
  Carry behaves like **short volatility**: steady income, occasional large losses, negative skew. Trend
  behaves like **long volatility**: frequent small losses, occasional large gains. Holding both roughly
  balances the convexity of the book (connects to 2.4), which is the real reason the carry+trend
  combination is standard practice. **Caveat:** the balance is imperfect — a fast market reversal can
  whipsaw trend *and* trigger carry's crisis losses simultaneously (e.g. March 2020), so both legs can
  lose together in exactly the fastest crises.

### 2.3 Value and momentum, everywhere **[V, 3-0]**

- **Idea:** Value and cross-sectional momentum premia exist consistently across **eight** markets/asset
  classes (US/UK/Europe/Japan stocks, equity-index futures, government bonds, currencies, commodities) —
  not just US single names.
- **What "value" actually means here (it is not one thing):** unlike carry, value has *no* model-free
  definition — you must pick a proxy for fundamental worth. AMP use **book-to-market** for stocks and
  country equity indices, but for **currencies, bonds, and commodities** value is the **negative of the
  ~5-year past return** (cheap = fell a lot over five years). So in three of five asset classes "value"
  is **long-horizon reversal**, the mirror of momentum's 12-month continuation. Read honestly, "value and
  momentum everywhere" is largely a statement about the **term structure of return autocorrelation** —
  continuation under a year, reversal over several years — one of the most robust stylized facts in asset
  pricing. That reframing *helps* the durability case for the non-equity value leg: rooted in
  under-/over-reaction, it is about as durable as a behavioral effect gets. But it is a narrower claim
  than "buying fundamentally cheap assets works everywhere," which is what the word "value" connotes.
- **Why combine (with a caveat on independence):** Value and momentum are **negatively correlated
  (~−0.5 to −0.6)** within and across asset classes, so a 50/50 combination has a materially higher
  Sharpe than either alone, and they correlate *more* across asset classes than passive exposures do (a
  common global factor). **But part of that −0.5 is mechanical:** where value = negative 5-year return
  and momentum = positive 12-month return, a recent rally raises momentum and lowers value through the
  shared *current price*, so the two are built to offset. The non-mechanical part is bounded by the
  **stock-level** estimate — where value is genuine book-to-market with no past-return construction — and
  *that* correlation is also strongly negative, so the offset is not purely an artifact. The honest
  reading: real economic content, but "two independent anomalies that beautifully hedge" overstates the
  independence.
- **The proposed mechanism (worth stating, per the durability test):** Asness, Moskowitz & Pedersen
  (AMP), *"Value and Momentum Everywhere"* (2013), tie the common structure to **funding-liquidity
  risk** — momentum loads *positively* on funding-liquidity shocks, value *negatively*. Links to
  Territory 1's funding point: if part of the momentum premium is compensation for funding-stress
  exposure, the natural holder is again someone whose balance sheet survives that stress.
- **But the loading and the crash are two different statistical objects — don't merge them.** The AMP
  loading is an *unconditional average* covariance across four decades and eight markets: a modest,
  pervasive tilt (momentum is a bit weaker in weeks when funding worsens). The **momentum crash** is a
  *conditional, nonlinear* event: after large market declines momentum's beta turns sharply negative and
  it loses on the rebound. They are causally linked — beaten-down losers get pushed below fundamentals
  by fire-sales during the crunch, then snap back on recovery — but statistically distinct, and the
  crash dominates the realized tail. The tell: momentum's worst episode, **spring 2009, happened while
  funding liquidity was *improving*** (TARP, QE, tightening spreads). The crash is the *delayed unwind*
  of the prior crunch, not a same-time liquidity event; sizing off the loading alone would not have
  saved you in 2009.
- **This splits the two "momenta" by failure mode.** Time-series momentum (2.1) and cross-sectional
  momentum (here) charge for *different* discomforts: **TSM's pain is whipsaw and long bull-market
  underperformance** — and it had a *good* 2008, going short as the market fell; **cross-sectional
  momentum's pain is the crash at the turn** — negative skew concentrated in recovery quarters, its
  reckoning arriving in 2009, six months after TSM's good year. Collapsing them into one line understates
  how different the tails are. (The sharp rebound-crash is clearest for *equity* cross-sectional
  momentum — Daniel-Moskowitz; AMP's cross-asset momentum has related but milder tails.)
- **Caveat on the mechanism — "dominates the tail" is not "is what you're paid for."** If the crash were
  the compensated risk, you could not remove it and keep the premium — yet **risk-managed momentum**
  (Barroso-Santa-Clara constant-volatility scaling; Daniel-Moskowitz dynamic weighting) largely *does*:
  scale down in high-volatility states, the crash shrinks, and the Sharpe holds or improves. That points
  to the crash being substantially a **manageable, non-priced tail** rather than the source of the
  premium — the same amount-vs-price-of-risk split as Territory 1. So: momentum's premium is *partly*
  funding-liquidity compensation, its tail is *dominated* by the rebound crash, and whether that crash is
  a **priced risk** or an **avoidable mistake** is genuinely unresolved (the overlay evidence leans
  "avoidable"). Because the best implementations *are* volatility-managed, "the momentum premium" in
  practice bundles signal with risk overlay — so the Kim-Tse-Wald question from 2.1 reappears here.
- **Caveat (it is one proxy in one asset class):** The severe **2018–2020 drawdown** was concentrated in
  **equity book-to-market** specifically — the 5-year-reversal versions of value in other asset classes
  don't share a stale-accounting problem. And whether equity value's drawdown reflected a **broken proxy**
  (intangibles and buybacks distorting book equity) or a temporary **re-rating** (growth simply getting
  more expensive, which partly mean-reverted in 2021–22) is itself debated — AQR's analyses found
  intangible adjustments explained little of it. So "value suffered a drawdown" is a claim about
  book-to-market, not about cheapness as such. (These remain in-sample correlations, not a live guarantee.)

### 2.4 Managed-futures crisis alpha — real, but conditional on crisis *speed* **[V, medium]**

- **Finding:** Asif, Frommel & Mende (International Review of Financial Analysis 2022): CTAs earn
  positive gains in most sectors during crises via two mechanisms — **(1)** diversification across many
  futures markets (gains in trending markets offset the crisis market), and **(2)** rapid exposure
  reduction to the crisis market (**<15 days** on average). Real episodes: 2008 Barclay CTA Index ~+14%
  vs S&P −37%; 2022 SG Trend ~+27% vs S&P −18%.
- **Corrected conditional (an earlier draft had this backwards):** what decides whether trend helps is
  **the speed of the crisis, not which asset class crashes.** Trend delivers crisis alpha when the move
  unfolds over **months** — slow, sustained, and directional enough for a 12-month-lookback,
  monthly-rebalanced system to establish the position. It **fails or whipsaws when the crisis completes
  in weeks.** Concretely: **2022 was the worst bond-market crisis in decades and was trend's *best* year**
  (slow, cross-asset selloff), while **March 2020 was an equity crisis but hard for many CTAs** because
  the crash and recovery finished faster than the system could get short. A rule keyed to asset class
  ("bad in bond crises") predicts 2022 exactly wrong; a rule keyed to speed gets it right.

### 2.5 What this Territory shows as a whole

- **Publication decay hit these strategies too — and that is the strongest evidence *for* the
  Territory 1 vs 2 distinction, not against it.** MOP published 2012, AMP 2013, KMPV 2018; live net
  Sharpes settled well below the in-sample gross figures. But they **compressed and stabilized** instead
  of going to zero, in the *same* post-publication environment that killed the index effect. Same
  exposure to publication, opposite outcome — exactly what a mechanism-based classification predicts:
  the reasons these premia pay (bearing losses in recessions and funding stress, tolerating trendless
  years) still exist, whereas the index effect's mechanism (unanticipated forced flow) was destroyed.
- **"Capacity-rich" is relative, not absolute.** These strategies hold hundreds of positions in deep
  futures markets, so they are capacity-rich next to anything in Territory 1. But CTA assets run into
  the hundreds of billions, and the fall from in-sample Sharpe >1 to live 0.3–0.7 is **not** fully
  explained by transaction costs — part is plausibly the premium's own capacity being consumed. Capacity
  is the barrier that erodes **slowest** here, not one that is absent.

---

## Territory 3 — Volatility & Derivatives **[E throughout — extracted, not re-verified]**

*These claims come from named primary sources (CFA Institute / Financial Analysts Journal, CBOE, AQR,
peer-reviewed studies) but were outside this run's top-25 verified set. Treat as "the source says."*

### 3.1 The Variance Risk Premium (VRP)

- **Idea:** Implied variance (what options price in) systematically exceeds subsequent realized
  variance, so **sellers of variance/volatility are compensated** — a short-variance position earns a
  significant negative alpha not explained by CAPM or Fama-French. From 1990–2018, average VIX implied
  vol (19.3%) exceeded average S&P realized vol (15.1%) by **4.2 percentage points.**
- **Mechanism:** Investors pay up for protection against volatility spikes (insurance premium); the
  seller collects it. The premium is synthesizable **model-free** from a static portfolio of options
  across strikes (the variance-swap replication), documented across 5 indices and 35 stocks
  (Carr-Wu-style evidence).
- **Why it matters:** The VRP is the economic engine under most of the strategies below.

### 3.2 Put-writing & covered calls (PutWrite vs BuyWrite)

- **The record:** Over 32+ years the CBOE S&P 500 PutWrite Index (PUT) matched the S&P 500's compound
  return (9.54% vs 9.80%) at **far lower volatility** (9.95% vs 14.93%) → **Sharpe 0.65 vs 0.49.**
- **But the edge faded:** Over the more recent **2006–2018** sub-period, PUT's Sharpe (0.50) was
  essentially equal to the S&P 500 (0.51). And it does **not** remove tail risk — PUT still drew down
  **−32.7%** in 2008–09.
- **Subtle but important (AQR, *PutWrite vs BuyWrite*):** PutWrite beat covered-call BuyWrite (BXM) by
  ~1.1%/yr (1986–2015), but by put-call parity the two are economically equivalent — the gap is a
  **mechanical artifact** of a ~4-hour/month expiration-morning equity-timing difference (a regression
  on morning/afternoon S&P returns explains **94%** of the difference). On non-expiration days the two
  correlate 0.97–0.98. An equal-weight combination removes the unintended timing bet. *Lesson: index
  construction details can masquerade as "alpha."*

### 3.3 "Volmageddon" — the short-vol tail (5 Feb 2018)

- **What happened:** Short-volatility ETPs lost **>90% in a single day**. XIV (VelocityShares) and SVXY
  (ProShares) — inverse VIX short-term futures products — were destroyed.
- **Mechanism (capacity/crowding failure):** As vol spiked, the products' short VIX-futures notional
  grew, so to stay neutral they had to **buy** VIX futures into the spike, pushing futures higher and
  forcing more buying — a mechanical feedback loop amplified by their large share of the VIX-futures
  market.
- **Lesson:** The VRP is real *on average* but has a brutal, fat left tail; the risk **is the whole
  story**, and it is worst exactly when market concentration and volatility are simultaneously high.
  Source: *"Volmageddon and the Failure of Short Volatility Products"* (Financial Analysts Journal 2021).

*(Dispersion trading — index vol vs single-name vol — and skew/tail-hedging economics were in scope but
returned no substantive verified or extracted claims this pass. Flagged as a gap, not as "weak.")*

---

## Territory 4 — Market Microstructure **[E throughout — extracted, not re-verified]**

The blunt verdict: **most short-horizon microstructure edge is a low-latency arms race inaccessible to
a daily/swing trader** — but the *concepts* (price impact, order-flow imbalance) are essential for
understanding execution costs you implicitly pay.

### 4.1 Order-Flow Imbalance (OFI) and linear price impact

- **Finding (Cont, Kukanov & Stoikov 2014):** OFI — the net change in best-bid/ask queue sizes from
  limit orders, market orders, and cancellations — explains short-horizon mid-price changes **linearly**
  with an average **R² ≈ 65%** across 50 US stocks (NYSE TAQ), using a single parameter. The impact
  slope is **inversely proportional to depth**, so impact is explainable from observable quantities
  alone (no unobservable information-asymmetry parameter).
- OFI treats a market sell and a same-size cancel-buy identically (both shrink the bid queue). It's more
  robust than trade-volume measures; the famous concave "square-root" law is argued to be an aggregation
  artifact. **Use:** this is the workhorse *execution/cost* model, not an alpha signal per se.

### 4.2 Latency arbitrage is HFT-only

- **Finding (Aquilina, Budish & O'Neill, Quarterly Journal of Economics 2022):** Latency-arb races are
  ~**one per minute per symbol** (FTSE 100), last **5–10 microseconds**, and are ~20% of volume. They
  impose a ~**0.5 bp tax** on trading (~$5bn/yr globally). The **top six firms win >80%** of races.
- **Lesson:** This speed alpha is structurally **unavailable** to non-colocated traders — it's a tax you
  pay, not an edge you can capture. It's a *speed contest over public information* (Budish-Cramton-Shim),
  distinct from information-based microstructure (Kyle; Glosten-Milgrom).

### 4.3 Overnight vs intraday (see also 1.5)

- The overnight/intraday tug-of-war is a genuine, persistent decomposition of where returns accrue, but
  **transaction costs substantially erode** any strategy built to exploit it directly.

---

## The Honest Base Rate

- **McLean & Pontiff (Journal of Finance 2016):** across 97 published predictors, portfolio returns are
  **26% lower out-of-sample** (post-sample, pre-publication) and **58% lower post-publication.** **[E]**
- This is the lens for everything above. Territory 1 (index effect, overnight drift) *is* this decay,
  observed in real time. Territory 2's premia have decayed **less** — plausibly because they're
  diversified across dozens of markets, grounded in risk/institutional stories (not just behavioral
  mispricing), and capacity-rich — but their live net Sharpes are still materially below the in-sample
  headlines, and each carries a real recession/whipsaw tail.

## What this means for us (and what's testable with the toolkit)

| Strategy | Verdict | Testable with our data? |
|---|---|---|
| Index effect / migrations | **Decayed / inverted** — study, don't trade | Partially — we have CRSP + S&P 500 membership; could replicate the announcement CARs with `event_car` |
| Overnight drift | **Gone post-2021** — cautionary tale | No — needs intraday/futures data we don't have |
| Leveraged-ETF rebalancing | Live but crowding; weakest evidence | No — needs intraday flow/close data |
| **Time-series momentum / trend** | **Most durable; learn deeply** | **Yes** — needs multi-asset futures return series (not in CRSP); could prototype on liquid ETFs as a proxy |
| **Carry (cross-asset)** | Durable, recession tail | Partially — needs futures/FX/bond data; equity dividend-yield carry is doable |
| Value & momentum everywhere | Durable combo | Cross-sectional equity momentum already in the toolkit; "everywhere" needs multi-asset data |
| Variance risk premium / put-writing | Real premium, fat tail | No — needs options data |
| OFI / latency arb | Concepts only; HFT-inaccessible | No — needs tick/order-book data |

**Recommendation for "worth to try" (given our data):** the single most learnable-*and*-buildable idea
is **time-series momentum / trend-following**, prototyped on a basket of liquid ETFs spanning equities,
bonds, commodities, and currencies (as futures proxies) — it exercises the durable, best-documented
premium, has genuine crisis convexity, and its core machinery (volatility-scaled positions, monthly
rebalance) is a small extension of the existing `MomentumStrategy` / `performance` modules. Everything
in Territories 3–4 is "learn now, trade later" — it needs options or tick data and, for latency arb,
infrastructure that is structurally out of reach.

## Open questions / gaps in this pass

- Territory 3 (VRP, put-writing, Volmageddon) is **extracted, not adversarially verified** — worth a
  focused verification pass before relying on the numbers. Dispersion and skew/tail-hedging returned
  nothing substantive.
- Best current estimates of **net-of-cost, out-of-sample Sharpe and capacity** for carry/trend/value-
  momentum after crowding — the in-sample headlines overstate the live edge.
- Which *other* structural flows (target-date and month-end rebalancing, closing-auction dynamics)
  remain live now that the index effect and overnight drift have decayed.

## References

**Structural / non-forecasting**
- Greenwood & Sammon, *The Disappearing Index Effect*, Journal of Finance 2025 (NBER w30748).
- Vijh & Wang, *The Reversal of the Index Effect for S&P 500 Migrations*, Financial Management 2022.
- Boyarchenko, Larsen & Whelan, *The Overnight Drift*, NY Fed Staff Report 917; and *The Disappearing
  Overnight Drift*, NY Fed Liberty Street Economics, July 2026.
- Lou, Polk & Skouras, *A Tug of War: Overnight vs Intraday Expected Returns*.

**Cross-asset carry & trend**
- Moskowitz, Ooi & Pedersen, *Time Series Momentum*, JFE 2012.
- Huang, Li, Wang & Zhou, *Time Series Momentum: Is It There?*, JFE 2020 (the vol-scaling critique).
- Koijen, Moskowitz, Pedersen & Vrugt, *Carry*, JFE 2018.
- Asness, Moskowitz & Pedersen, *Value and Momentum Everywhere*, Journal of Finance 2013.
- Asif, Frommel & Mende, *The Crisis Alpha of Managed Futures: Myth or Reality?*, IRFA 2022.

**Volatility & derivatives**
- *Volmageddon and the Failure of Short Volatility Products*, Financial Analysts Journal 2021.
- Bondarenko et al., CBOE PutWrite (PUT) index research.
- AQR, *PutWrite versus BuyWrite: Yes, Put-Call Parity Holds Here Too*.
- Carr & Wu–style variance-risk-premium evidence (SSRN 1701685).

**Microstructure**
- Cont, Kukanov & Stoikov, *The Price Impact of Order Book Events*, J. Financial Econometrics 2014.
- Aquilina, Budish & O'Neill, *Quantifying the High-Frequency Trading "Arms Race"*, QJE 2022.

**Base rate**
- McLean & Pontiff, *Does Academic Research Destroy Stock Return Predictability?*, Journal of Finance 2016.
