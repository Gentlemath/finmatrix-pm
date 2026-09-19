"""Diagnose contract-level continuous series before they are cached. READ-ONLY.

    python tools/build_contract_series.py                 # every target
    python tools/build_contract_series.py 1508 2441
    python tools/build_contract_series.py 1508 --roll calendar --buffer 15

All construction logic and the market registry live in
``portfolio_management.dataloader.ds_contracts`` so that this tool and
``examples/cache_futures_data_v2_wrds.py`` cannot drift apart -- an earlier
duplicate of BASKET in two files had already diverged before it was noticed.

What to read in the output:

  liquidity   a real front month ranks 1st by open interest and holds a large
              share of it. Rank 11 with 0.3% of the day's open interest is a
              serial month that barely trades, and its settlements are derived
              rather than traded.
  roll pace   should reproduce the market's OWN contract cycle without being
              told it: quarterly bonds 3.0 months, gold's Feb/Apr/Jun/Aug/Dec
              2.4, cotton 3.1 with 5-month runs where it skips a thin October.
  roll gap    what a continuous series prints on a roll day and masking throws
              away. Sign follows the curve; gap minus our roll-day return is
              the calendar spread, so the two cross-check.
  vs CS00     0.98 is the CEILING, not a defect: building clscode 3725 and
              comparing it to ISPCS00, which is DERIVED from 3725, gives 0.9796
              on identical contracts. Mean differences are printed with a
              standard error because on a 30%-vol market they look large while
              sitting inside sampling error.
  splice      built against built, like for like, so 0.98 does not apply and
              0.99+ is expected of two contracts on the same underlying.
"""

import argparse

import numpy as np
import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_contracts import (
    BUFFER_DAYS, CONTRACT_MARKETS, ROLL_RULE, SPLICES, WINDOW_MONTHS,
    build_market)
from portfolio_management.dataloader.ds_futures import (
    clean_prices, fetch_series, mask_roll_returns, resolve_series, to_monthly)

MIN_OVERLAP = 24


def reference_monthly(loader, mnemonics) -> dict:
    """Monthly returns of the CS00 series used as validation references."""
    out = {}
    if not mnemonics:
        return out
    info = resolve_series(loader, sorted(mnemonics))
    for _, r in info.iterrows():
        raw = fetch_series(loader, int(r["calcseriescode"]))
        if raw.empty:
            continue
        px, _, _ = clean_prices(raw)
        ret, _, _ = mask_roll_returns(px)
        m = to_monthly(ret.to_frame("r"))["r"]
        m.index = m.index.to_period("M")
        out[r["dsmnem"]] = m.dropna()
    return out


def to_month(daily: pd.Series) -> pd.Series:
    m = to_monthly(daily.to_frame("r"))["r"]
    m.index = m.index.to_period("M")
    return m.dropna()


def show_market(label: str, code: int, daily: pd.Series, diag: dict,
                opts) -> None:
    print(f"\n{'=' * 74}\n{label}  clscode {code}  (roll={opts.roll}, "
          f"buffer={opts.buffer}d, window={opts.window}m)\n{'=' * 74}")
    if "error" in diag:
        print(f"  {diag['error']}")
        return
    print(f"  {diag['n_contracts']} contracts, {diag['n_contract_days']:,} "
          f"priced contract-days, ccy {diag['ccy']}, open interest on "
          f"{diag['oi_present'] * 100:.0f}%")
    monthly = to_month(daily)
    span = (daily.index.max() - daily.index.min()).days / 365.25
    print(f"  built: {len(daily):,} daily, {len(monthly)} monthly, "
          f"{monthly.index.min()} .. {monthly.index.max()}")
    print(f"  {diag['n_rolls']} rolls over {span:.1f} years = one every "
          f"{span * 12 / max(diag['n_rolls'], 1):.1f} months")
    rt, rg = diag["roll_true"], diag["roll_gap"]
    if len(rt):
        print(f"  roll-day return WE capture:   mean {rt.mean() * 100:+.3f}% "
              f"(n={len(rt)})")
    if len(rg):
        print(f"  roll GAP the CS00 series shows: mean {rg.mean() * 100:+.3f}%"
              f"  <- what masking discarded")
    if len(rt) and len(rg):
        print(f"  => calendar spread {(rg.mean() - rt.mean()) * 100:+.3f}%"
              f"  (positive = contango)")
    print(f"  ann vol {daily.std() * np.sqrt(252) * 100:.1f}%")
    if diag.get("share_med") is not None:
        print(f"  liquidity of the contract we held: median rank "
              f"{diag['rank_med']:.0f}, median {diag['share_med'] * 100:.1f}% "
              f"of the day's open interest")
        print(f"      rank 1 on {diag['pct_rank1'] * 100:.0f}% of days; under "
              f"5% of OI on {diag['pct_share_lt5'] * 100:.0f}% of days")
    hold = np.array([r[2] for r in diag["runs"]])
    long_holds = [r for r in diag["runs"] if r[2] > 4.5]
    print(f"  holding period (months): median {np.median(hold):.1f}, p90 "
          f"{np.percentile(hold, 90):.1f}, max {hold.max():.1f}; "
          f"{len(long_holds)} runs > 4.5m")
    for st, c, ln in long_holds[:5]:
        print(f"      {st:%Y-%m-%d}  futcode {c}  held {ln:.1f} months")
    if len(long_holds) > 5:
        print(f"      ... and {len(long_holds) - 5} more")


def compare_reference(label: str, monthly: pd.Series, refmn: str,
                      ref: dict) -> None:
    if refmn not in ref:
        print(f"\n  {refmn} unavailable -- built series unvalidated")
        return
    j = pd.concat([monthly.rename("mine"), ref[refmn].rename("cs00")],
                  axis=1).dropna()
    print(f"\n  vs {refmn} on the overlap:")
    if len(j) < MIN_OVERLAP:
        print(f"    only {len(j)} months -- not comparable")
        return
    beta = (np.polyfit(j["cs00"], j["mine"], 1)[0]
            if j["cs00"].std() > 0 else np.nan)
    d = j["mine"] - j["cs00"]
    se = d.std() / np.sqrt(len(d))
    t = d.mean() / se if se > 0 else np.nan
    print(f"    n={len(j)}  corr={j['mine'].corr(j['cs00']):.4f}  "
          f"beta={beta:.2f}")
    print(f"    ann vol  mine {j['mine'].std() * np.sqrt(12) * 100:.1f}%   "
          f"cs00 {j['cs00'].std() * np.sqrt(12) * 100:.1f}%")
    print(f"    ann mean mine {j['mine'].mean() * 12 * 100:+.2f}%   cs00 "
          f"{j['cs00'].mean() * 12 * 100:+.2f}%   diff {d.mean() * 12 * 100:+.2f}%"
          f"  (SE {se * 12 * 100:.2f}%, t={t:+.2f})")
    if abs(t) < 2.0:
        print("    the difference is inside sampling error -- no bias to "
              "explain")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clscodes", nargs="*", type=int)
    ap.add_argument("--roll", choices=("oi", "calendar"), default=ROLL_RULE)
    ap.add_argument("--buffer", type=int, default=BUFFER_DAYS,
                    help="days before last trade date a contract is dropped")
    ap.add_argument("--window", type=int, default=WINDOW_MONTHS,
                    help="only consider contracts expiring within N months")
    opts = ap.parse_args()
    codes = opts.clscodes or sorted(CONTRACT_MARKETS)
    unknown = [c for c in codes if c not in CONTRACT_MARKETS]
    if unknown:
        raise SystemExit(f"not in CONTRACT_MARKETS: {unknown}")

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    built = {}
    try:
        wanted = {CONTRACT_MARKETS[c][2] for c in codes
                  if CONTRACT_MARKETS[c][2]}
        ref = reference_monthly(loader, wanted)
        for code in codes:
            cls, label, refmn = CONTRACT_MARKETS[code]
            daily, diag = build_market(loader, code, opts.roll, opts.buffer,
                                       opts.window)
            show_market(label, code, daily, diag, opts)
            if daily.empty:
                continue
            monthly = to_month(daily)
            built[label] = monthly
            if refmn:
                compare_reference(label, monthly, refmn, ref)
    finally:
        loader.close()

    pairs = [(n, p) for n, (_, p) in SPLICES.items()
             if sum(x in built for x in p) >= 2]
    if pairs:
        print(f"\n{'=' * 74}\nSPLICE CHECK (built vs built, like for like)"
              f"\n{'=' * 74}")
        for name, parts in pairs:
            a, b = [x for x in parts if x in built][:2]
            j = pd.concat([built[a].rename("a"), built[b].rename("b")],
                          axis=1).dropna()
            print(f"  {name}: {a} vs {b}")
            if len(j) < MIN_OVERLAP:
                print(f"    only {len(j)} months of overlap -- cannot verify")
                continue
            corr = j["a"].corr(j["b"])
            beta = (np.polyfit(j["b"], j["a"], 1)[0]
                    if j["b"].std() > 0 else np.nan)
            union = built[a].combine_first(built[b])
            print(f"    overlap n={len(j)}  {j.index.min()} .. {j.index.max()}")
            print(f"    corr={corr:.4f}  beta={beta:.2f}   ann vol "
                  f"{j['a'].std() * np.sqrt(12) * 100:.1f}% / "
                  f"{j['b'].std() * np.sqrt(12) * 100:.1f}%")
            print(f"    {'JOINABLE' if corr > 0.99 else 'SUSPECT -- do not join'}"
                  f"   joined spans {union.index.min()} .. "
                  f"{union.index.max()} ({len(union)} months)")

    if built:
        print(f"\n{'=' * 74}\nSUMMARY\n{'=' * 74}")
        print(f"  {'market':<14}{'months':>8}{'first':>10}{'last':>10}"
              f"{'annVol':>9}{'annRet':>9}")
        for label, m in built.items():
            print(f"  {label:<14}{len(m):>8}{str(m.index.min()):>10}"
                  f"{str(m.index.max()):>10}"
                  f"{m.std() * np.sqrt(12) * 100:>8.1f}%"
                  f"{m.mean() * 12 * 100:>8.2f}%")


if __name__ == "__main__":
    main()
