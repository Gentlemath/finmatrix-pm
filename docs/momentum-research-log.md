# Momentum research log

Findings from backtesting the `MomentumStrategy` on a **survivorship-bias-free**
S&P 500 universe (CRSP CIZ, 1990–2025). Only aggregate results are recorded here;
the underlying CRSP data is licensed and lives in the gitignored `local_data/`.

## Setup

- **Universe**: point-in-time S&P 500 members (`crsp.msp500list_v2`) — includes
  names later removed or delisted, so no survivorship bias.
- **Returns**: CIZ monthly (`crsp.msf_v2`), delisting return already folded into
  `mthret`.
- **Signal**: 11-month cumulative return, skip the most recent month
  (`lookback=11`, `gap=1`); monthly rebalance.
- **Portfolios**: value-weighted deciles. "Long-short" = D10 − D1; "long-only" =
  top decile (D10).
- **Reproduce**: `examples/momentum_demo.py` (live WRDS) or build panels from a
  cached pull and call `MomentumStrategy(...).backtest(...)`.

## Headline: momentum is regime-dependent, not a free lunch

Long-short deciles (gross, value-weighted):

| Period | Ann. return | Sharpe | Max drawdown |
|---|---|---|---|
| 1991–1999 | +16.6% | 0.83 | −27% |
| 2000–2009 | −5.6% | 0.07 | −73% |
| 2010–2019 | +2.9% | 0.26 | −24% |
| 2020–2025 | −1.6% | 0.08 | −57% |
| pre-2009 | +10.8% | 0.50 | −61% |
| 2009–2025 | −4.9% | −0.06 | −73% |
| **Full 1991–2025** | **+2.9%** | **0.25** | **−73%** |

The premium was strong in the 1990s and has been dead-to-negative since the 2008
financial crisis.

## The momentum crash (the defining risk)

Long-short calendar-year returns around the crisis:

- **2008: +80.8%** — short the collapsing losers → huge win in the bear market.
- **2009: −65.1%** — the market bottomed (Mar 2009) and beaten-down losers
  rebounded violently; being short them wiped out a year's book.

That single reversal is the −73% max drawdown. It is the classic **"momentum
crash"** (Daniel–Moskowitz 2016): momentum earns small, steady gains, then loses
catastrophically when the market sharply reverses. Consequences:

- **Negative skew / crash risk** is intrinsic — it is what the premium pays for.
- Long-short market **beta ≈ −0.54**: implicitly short high-beta losers, so it
  loses precisely in sharp recoveries.
- Post-2009 yearly returns are a coin flip with big swings (2015 +33%, 2016 −24%,
  2023 −32%, 2024 +42%) — no reliable sign.

## Long-only ≈ market + a fading tilt

| Period | Long-only | Cap-wtd S&P 500 | Excess |
|---|---|---|---|
| 1991–1999 | +33.4% | +20.9% | +12.5% |
| 2000–2009 | +0.9% | −0.8% | +1.7% |
| 2010–2019 | +13.5% | +13.5% | ~0% |
| 2020–2025 | +18.7% | +15.2% | +3.5% |
| Full | +15.3% | +11.3% | +4.0% |

Long-only momentum has **β ≈ 1.0, R² ≈ 0.58** — it *is* the market — with a
**modest, time-varying alpha (~4%/yr full sample, IR ≈ 0.34)** that was large in
the 1990s and essentially vanished in the 2010s. Most of the return is just being
long equities. Do not mistake the bull market for a momentum edge.

## Transaction costs finish off the weak periods

Long-short annualized return, net of proportional cost (per side):

| Period | 0 bps | 10 bps | 20 bps |
|---|---|---|---|
| pre-2009 | +10.8% | +8.9% | +7.0% |
| 2010–2019 | +2.9% | +1.2% | −0.6% |
| Full | +2.9% | +1.1% | −0.6% |

One-way turnover is ~8.6×/yr (long-short) / ~4×/yr (long-only). The 1990s edge was
big enough to survive costs; the thin post-2009 premium is not — it turns negative
around 15–20 bps.

## Takeaways

1. **Regime-dependent** — worked pre-2009, died after.
2. **Crash risk / negative skew** — small gains then catastrophic reversals (2009: −65%).
3. **Negative market beta** (long-short) — loses in sharp recoveries.
4. **Long-only ≈ beta + a fading tilt** — not evidence of a standalone edge.
5. **Turnover-sensitive** — costs erase the weak modern premium.

## Methodological notes

- Survivorship-bias-free data matters: today's-members backtests overstate returns
  (~2 pp/yr on a buy-and-hold basis in this sample). See the survivorship experiment
  in the loader/strategy history.
- CAPM alpha is *arithmetic* (mean-based). The long-short's positive arithmetic
  alpha coexists with a poor compounded return (+2.9%/yr) and a −73% drawdown —
  arithmetic alpha is not money in the bank.
- Returns are indexed by the **realized (holding) month** so they align with the
  benchmark/risk-free; an earlier off-by-one (formation-month) labeling produced
  nonsensical CAPM betas and is now regression-tested against.

## References

- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*.
- Daniel & Moskowitz (2016), *Momentum Crashes*.
