# Trading-strategy research log — what survives net of costs

Evidence synthesis for a **research/institutional US-equity trader at a
days-to-weeks (swing) horizon** who can short and use modest leverage. Compiled
2026-07-22 from a multi-source literature search with adversarial fact-checking.

> **This is educational evidence, not investment advice.** "Replicated
> historically" does **not** mean "profitable net of costs today." Nearly every
> headline number below is monthly-horizon and gross (or only partly net of
> costs); none directly proves net-of-cost survival at a high-turnover
> days-to-weeks horizon, which is strictly harder.

**Confidence tiers used below:** **[V]** = claim independently verified this run
(3-vote adversarial check); **[S]** = drawn from a primary source but not
re-verified (treat as weaker).

---

## 0. Bottom line

At a days-to-weeks horizon, **turnover is the whole game**. The strategies most
native to this horizon — short-term reversal, pairs/statistical arbitrage — are
precisely the ones most vulnerable to transaction costs, capacity limits, and
crowding. Net of realistic frictions, the credible surviving edges are **thinner,
lower-capacity, and more fragile** than any in-sample backtest suggests. The
dominant tail risk is not slow decay but **crowding + leverage** unwinding
violently (August 2007). The honest base rate across the literature is that most
published anomalies weaken markedly out of sample.

---

## 1. The base rate: how often do published edges actually survive?

### 1a. The replication debate is real and methodology-driven

Two camps reach opposite conclusions **from the same data**, differing mainly in
how they treat tiny stocks and multiple testing:

**Pessimists (most anomalies are fragile):**
- **Hou, Xue & Zhang, "Replicating Anomalies" (RFS 2020) [V]** — replicate 447
  anomalies with **NYSE breakpoints + value-weighting** (so microcaps can't drive
  the result): **286 (64%) are insignificant at the 5% level; 380 (85%) fail a
  t = 3 hurdle.** In the trading-frictions/liquidity category specifically,
  **95 of 102 (93%)** are insignificant.
- **Harvey, Liu & Zhu (RFS 2016) [V]** — under multiple-testing corrections,
  **80–158 of 316 factors are likely false discoveries**; they argue a new factor
  should clear roughly **t > 3**, not 2.
- **Chordia, Goyal & Saretto (RFS 2020) [V]** — data-mine ~2.1 million trading
  strategies; **only 17 survive** strict multiple-testing thresholds.

**Optimists (most factors replicate):**
- **Jensen, Kelly & Pedersen, "Is There a Replication Crisis in Finance?"
  (JF 2023) [V]** — the majority of factors replicate, cluster into **13
  economically coherent themes** (10 of 13 enter the tangency portfolio
  significantly), and hold up **out-of-sample across 93 countries (~82%
  replication)**. Under a Bayesian joint framework, many *correlated* factors
  **strengthen** rather than weaken the evidence. (This is the same JKP dataset
  the toolkit's `contrib_global_factor` momentum work drew on.)
- **Chen & Zimmermann, "Publication Bias in Asset Pricing Research" (2022) [V]** —
  publication-bias corrections explain only **~10–15%** of in-sample means;
  false-discovery rate **below 10%**; predictability persists out of sample.

**Why they diverge:** JKP use capped value-weights + Bayesian shrinkage; HXZ use
NYSE breakpoints + all-firm value-weighting + strict significance. Treat the base
rate as an **active debate, not settled** — and note **neither camp establishes
net-of-cost survival at a days-to-weeks horizon.**

### 1b. Post-publication decay — the one thing everyone agrees on [V]

- **McLean & Pontiff (JF 2016)** across 97 predictors: anomaly long-short returns
  are **~26% lower out-of-sample** and **~58% lower after publication.** The extra
  post-publication drop is concentrated in **easy-to-arbitrage, high-volume
  stocks** → favors a **mispricing/arbitrage (crowding)** explanation over a
  risk-based one. Publishing an edge helps arbitrage it away.
- **Brogaard, Nguyen, Putniņš & Zhang (2023) [V]** corroborate: anomaly
  profitability turned to *increasing losses* over time, attributed to academic
  publication + decimalization.

*(This is exactly what we measured for US momentum ourselves: a strong pre-2009
premium that decayed after the factor became famous and heavily traded.)*

---

## 2. Family-by-family

### 2.1 Short-term reversal (cross-sectional mean-reversion)

- **Idea:** buy last week's/month's losers, short the winners — prices
  over-react short-term and snap back.
- **Evidence [V]:** Jegadeesh (1990) is explicitly among the anomalies that
  **fail** HXZ's microcap-robust replication; it survives mainly in
  **equal-weighted (microcap-heavy)** tests. Mechanistically it is **compensation
  for liquidity provision**, not mispricing alpha (Nagel 2012; JBF 2022): the
  contrarian earns by *supplying immediacy* to forced sellers/buyers, and the
  payoff is predictable with the VIX (it's a risk premium for providing liquidity
  in stress). Damningly, on average **mutual funds' cost of immediacy exceeds
  their liquidity-provision returns by ~1.9%/yr.**
- **Cost & capacity:** the highest-turnover family; costs dominate; you are
  competing with market-makers/HFT for the same liquidity-provision payment.
- **Verdict for you:** ❌ Not free alpha. Only viable with HFT-grade execution
  costs; otherwise you *pay* the premium you're trying to earn.

### 2.2 Pairs trading / statistical arbitrage

- **Idea:** trade the spread between two historically co-moving securities,
  betting on convergence.
- **Evidence [V]:** Do & Faff (2012) — after commissions, market impact, and
  short fees, refined-industry pairs remain profitable only at **~30 bps/month**
  risk-adjusted (and that is a **1963–2009 full-sample** figure dominated by
  pre-2002 data; profitability largely evaporated after ~2002/decimalization).
  Chen et al. (Mgmt Sci 2019) — return-difference pairs earn ~**1.4%** in the
  **first month** after divergence, then **reverse to losses** beyond month one,
  with declining profitability recently.
- **Cost & capacity:** low capacity, concentrated in smaller/well-matched pairs,
  short-lived and high-turnover.
- **Verdict for you:** ⚠️ Heavily decayed; only the most refined, low-capacity
  implementations survive net of costs.

### 2.3 Momentum with crash control

- **Idea:** plain momentum works but crashes catastrophically in sharp reversals
  (we saw −65% in 2009); "crash control" scales exposure down when momentum is
  risky.
- **Evidence:**
  - Plain price momentum & earnings momentum **replicate but "much lower than
    originally reported"** — e.g. SUE earnings momentum ~**0.46%/month (t=3.48)**
    [V].
  - **Barroso & Santa-Clara (JFE 2015) [S]:** scaling momentum by the inverse of
    its recent realized volatility ("risk-managed momentum") **nearly doubles the
    Sharpe ratio and virtually eliminates crashes.**
  - **Daniel & Moskowitz "Momentum Crashes" (JFE 2016) [S]:** a dynamic
    (vol-scaled) momentum that forecasts momentum's conditional mean/variance
    **roughly doubles alpha and Sharpe**; crashes cluster in post-bear "panic"
    states.
  - **Residual momentum (Blitz, Huij & Martens) [S]:** ranking on
    factor-*residual* returns cuts volatility ~2× — US 1986–2008 conventional
    momentum 16.1% p.a. @ 21.6% vol (ratio 0.74) vs residual momentum 13.1% @
    10.3% vol (ratio **1.28**).
- **Cost & capacity:** monthly-horizon, moderate turnover; the crash-control
  results are **in-sample** and don't establish post-2010 net-of-cost survival.
- **Verdict for you:** ⚠️ The most durable family, and crash control is a genuine
  in-sample improvement — but it's monthly (not swing), still crash-prone, and the
  premium has decayed (our own finding). Worth **testing net of costs**, not
  taking on faith.

### 2.4 Value / quality / profitability / multifactor & factor timing

- **Idea:** fundamental factors (cheapness, profitability, quality), combined; and
  *timing* factors (lean in when a factor looks cheap/strong).
- **Evidence [V]:** the base-rate debate (§1) applies. On **factor timing** the
  verdict is clear and sobering: **median out-of-sample R² ~0.75%, ~2 pp/yr
  improvement over buy-and-hold, correct sign only ~56% of the time** (Neuhierl
  et al., "Timing the Factor Zoo"). A claim that timing works broadly across
  300+ factors with 39 signals was **refuted (0-3)**. Asness ("The Siren Song of
  Factor Timing", 2016) argues valuation-spread timing is largely illusory once
  you already hold the factor.
- **Cost & capacity:** lower turnover than reversal/pairs (better for costs), but
  this is a **weeks-to-months+** style, not swing.
- **Verdict for you:** ⚠️ Static multifactor exposure is the most capacity-robust
  thing here, but it's not a days-to-weeks strategy; **factor timing is marginal**
  — don't expect a reliable standalone edge from it.

### 2.5 Event-driven short-horizon signals (PEAD, reconstitution, revisions)

- **Idea:** trade the drift after scheduled events — post-earnings-announcement
  drift (PEAD), index add/deletes, analyst-revision momentum.
- **Evidence:** **PEAD is essentially dead for tradeable stocks [S]:** Martineau
  "Rest in Peace Post-Earnings-Announcement Drift" (2022) — PEAD began
  disappearing from **non-microcap** stocks around **2001** and was **~zero for
  large caps by 2006**; prices now largely react *at* the announcement, leaving no
  drift to harvest. HXZ [V] confirm the surviving earnings-momentum spread is
  small (~0.46%/mo, §2.3).
- **Cost & capacity:** the drift that remains is in **microcaps** — low capacity,
  high relative costs.
- **Verdict for you:** ❌ for large-cap PEAD. Other event signals (reconstitution,
  revisions) weren't verified in this run — an evidence gap.

### 2.6 Machine learning & alternative data

- **Idea:** let flexible models / novel data find return predictability.
- **Evidence [S]:** Avramov, Cheng & Metzker (Mgmt Sci 2023) — ML (incl.
  deep-learning) return predictability **concentrates in hard-to-arbitrage
  stocks**; **excluding microcaps, distressed, and high-volatility episodes
  attenuates it considerably.** More sophisticated ML strategies can net
  ~**1.4%/month** out-of-sample despite >50% turnover — **but only while holding
  those hard-to-trade names.** (Gu-Kelly-Xiu is the canonical "ML adds OOS
  predictability" reference; not fully verified here.)
- **Cost & capacity:** the "alpha" lives disproportionately where trading is
  expensive/constrained; net-of-cost survival at scale is contested.
- **Verdict for you:** ⚠️ Real out-of-sample signal exists, but it's concentrated
  exactly where you can't cheaply trade — easy to overfit, hard to bank net of
  costs.

---

## 3. The dominant crash mechanism: crowding + leverage [V]

**Khandani & Lo, "What Happened to the Quants in August 2007?" (JFM 2011).** In
the week of Aug 6, 2007, quant long/short and short-term-reversal/market-neutral
books suffered unprecedented losses with **no model failure**. The "Unwind
Hypothesis": a large crowded market-neutral portfolio was force-liquidated
(deleveraged), its price impact hammered *similarly-constructed* books in a
feedback loop, compounded by market-makers pulling risk capital. **For a leveraged
short-horizon trader, this — not slow alpha decay — is the tail risk to design
against.**

---

## 4. Practical implications

1. **Don't treat the swing-horizon reversal/stat-arb "edge" as alpha.** The
   evidence says it's liquidity-provision compensation you'd likely be *paying*,
   not earning, without HFT-grade costs.
2. **The most defensible systematic edges sit at weeks-to-months, not days.** Even
   there, assume roughly half the backtest survives and stress costs + crowding.
3. **Test, don't trust — and this toolkit can:**
   - Reproduce **PEAD decay** on CRSP/Compustat (does it really vanish for large
     caps post-2006?).
   - Add **vol-scaling / residual momentum** to `MomentumStrategy` and check
     whether crash control survives net of the cost model.
   - Measure the **turnover × cost break-even** for any short-reversal signal
     before believing a Sharpe ratio.
4. **Budget for capacity and crowding explicitly.** Every survivor here is
   low-capacity; the base rate is decay.

---

## 5. References

- Hou, Xue & Zhang — *Replicating Anomalies* (RFS 2020; NBER w23394)
- Harvey, Liu & Zhu — *…and the Cross-Section of Expected Returns* (RFS 2016)
- Chordia, Goyal & Saretto — *p-hacking in asset pricing* (RFS 2020)
- Jensen, Kelly & Pedersen — *Is There a Replication Crisis in Finance?* (JF 2023)
- Chen & Zimmermann — *Publication Bias in Asset Pricing Research* (2022)
- McLean & Pontiff — *Does Academic Research Destroy Stock Return Predictability?* (JF 2016)
- Brogaard, Nguyen, Putniņš & Zhang — *anomaly decay drivers* (2023, working paper)
- Nagel — *Evaporating Liquidity* (RFS 2012); *Short-term reversals & liquidity provision* (JBF 2022)
- Do & Faff — *Are Pairs Trading Profits Robust to Trading Costs?* (JFR 2012)
- Chen, et al. — *pairs / return-difference reversal* (Management Science 2019)
- Daniel & Moskowitz — *Momentum Crashes* (JFE 2016; NBER w20439)
- Barroso & Santa-Clara — *Momentum Has Its Moments* (JFE 2015)
- Blitz, Huij & Martens — *Residual Momentum* (2011)
- Neuhierl, Randl, Reschenhofer & Zechner — *Timing the Factor Zoo* (JF)
- Asness — *The Siren Song of Factor Timing* (JPM 2016)
- Martineau — *Rest in Peace Post-Earnings-Announcement Drift* (Critical Finance Review 2022)
- Avramov, Cheng & Metzker — *Machine Learning vs. Economic Restrictions* (Management Science 2023)
- Gu, Kelly & Xiu — *Empirical Asset Pricing via Machine Learning* (RFS 2020)
- Khandani & Lo — *What Happened to the Quants in August 2007?* (JFM 2011)

## 6. Caveats & verification

- **[V]** findings passed a 3-vote adversarial check; **[S]** findings are
  single-source and weaker. Four claims were **refuted** and excluded (incl.
  "factor timing works broadly across 300+ factors" and a specific 30–50% decay
  figure).
- Headline numbers are largely **monthly and gross/partly-net** — none proves
  net-of-cost survival at a days-to-weeks horizon.
- The crash-control (§2.3), PEAD-death (§2.5), and ML (§2.6) specifics are tier
  **[S]**.
- Not investment advice.
