"""Cache the rebuilt 51-market futures basket from WRDS Datastream.

Run in YOUR terminal (needs your WRDS account). Licensed data -- local_data/ is
gitignored; do not commit the output.

    python examples/cache_futures_data_v2_wrds.py
    python examples/cache_futures_data_v2_wrds.py --only GOLD,SILVER
    python examples/cache_futures_data_v2_wrds.py --assemble-only
    python examples/cache_futures_data_v2_wrds.py --refresh          # re-pull

This does NOT overwrite the previous dataset. It writes ``*_v2`` files beside
it so the two can be compared, because the two are built differently and the
difference is measurable (see below).

Successor to ``cache_futures_data_wrds.py``, which reads Datastream's own
continuous series for all 35 markets. Half of this basket cannot be built that
way: the continuous-series tables stopped carrying CME Group (COMEX 2022-11,
CBOT 2025-04, NYMEX 2026-04) and the live classes have no continuous series at
all. So 27 series are built from CONTRACT-level data by
``portfolio_management.dataloader.ds_contracts`` and 27 are read from
continuous series by ``ds_futures``; three markets splice components together.
Registries, roll rule and the reasoning all live in ``ds_contracts`` -- read
that docstring before changing anything here.

What the rebuild buys, market by market: panel start 1979-01 -> 1973-01, a US
equity index where there was none, six FX majors in place of a dollar index and
one thin cross, livestock as a new asset class, US rates and precious metals
alive to 2026 instead of dying in 2022/2025, and the world's most liquid grains
in place of three thin ones.

TWO CONSTRUCTIONS IN ONE PANEL, and what that costs. The contract-built markets
carry their roll-day returns; the continuous ones have that day masked. Measured
on markets where both exist: monthly correlation 0.95-0.985, volatility higher
by 0.3-0.5 percentage points for the built series, and mean-return differences
that sit inside sampling error (|t| < 2 everywhere). So the cost is a small
volatility discrepancy, not a return discrepancy -- but it is a real one, and
``source`` in the meta file records which construction each market used.

Pulling is RESUMABLE. Each built market is cached under
local_data/futures_v2_parts/ and skipped if already there, because the contract
tables run to roughly 8 million rows and a failure at market 40 should not
restart from market 1.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_contracts import (
    CONTINUOUS_MARKETS, CONTRACT_MARKETS, DROPPED, SPLICES, build_market,
    final_markets, splice_returns)
from portfolio_management.dataloader.ds_futures import (
    build_panels, effective_breadth, to_monthly)

OUT = Path("local_data")
PARTS = OUT / "futures_v2_parts"
DAILY_FILE = "futures_returns_daily_v2.csv"
MONTHLY_FILE = "futures_returns_monthly_v2.csv"
META_FILE = "futures_basket_meta_v2.csv"
MIN_MONTHS_FOR_BREADTH = 60


def part_paths(label: str):
    return PARTS / f"{label}.csv", PARTS / f"{label}.json"


def load_part(label: str):
    csv, js = part_paths(label)
    if not (csv.exists() and js.exists()):
        return None, None
    s = pd.read_csv(csv, index_col=0, parse_dates=True).iloc[:, 0]
    return s.rename(label), json.loads(js.read_text())


def save_part(label: str, daily: pd.Series, diag: dict) -> None:
    csv, js = part_paths(label)
    daily.rename("r").to_csv(csv)
    # roll_true / roll_gap are per-roll arrays and runs is a list of tuples;
    # keep the summary numbers that the meta file reports, not the raw arrays.
    keep = {k: v for k, v in diag.items()
            if k not in ("roll_true", "roll_gap", "runs")}
    rt, rg, runs = diag.get("roll_true"), diag.get("roll_gap"), diag.get("runs")
    # Medians as well as means: the gap is a CROSS-contract comparison, so a
    # single bad settlement on a contract we are rolling away from distorts the
    # mean without touching any return. CHFUSD's gap mean is +8.81% against a
    # peer group of -0.38%..+0.63%, while its returns are clean (its two
    # extremes are the 2011 and 2015 Swiss National Bank floor events).
    if rt is not None and len(rt):
        keep["roll_true_mean"] = float(rt.mean())
        keep["roll_true_median"] = float(np.median(rt))
    if rg is not None and len(rg):
        keep["roll_gap_mean"] = float(rg.mean())
        keep["roll_gap_median"] = float(np.median(rg))
    if runs:
        hold = [r[2] for r in runs]
        keep["hold_median_m"] = float(pd.Series(hold).median())
        keep["hold_max_m"] = float(max(hold))
    js.write_text(json.dumps(keep, indent=1, sort_keys=True))


def build_contract_markets(loader, wanted: set, refresh: bool):
    """Build (or load from cache) every contract-level component series.

    ``wanted`` decides what is REBUILT, never what is assembled: every cached
    part is loaded regardless, or a ``--only`` run would quietly write a panel
    containing just the handful of markets it rebuilt.
    """
    series, diags = {}, {}
    print(f"contract-level: {len(CONTRACT_MARKETS)} series "
          f"({len(wanted)} eligible to rebuild)")
    for code, (cls, label, _) in sorted(CONTRACT_MARKETS.items()):
        if not (refresh and label in wanted):
            cached, diag = load_part(label)
            if cached is not None:
                series[label], diags[label] = cached, diag
                print(f"  {label:<14} cached   {len(cached):>6} days")
                continue
            if label not in wanted:
                print(f"  {label:<14} MISSING  not cached, and --only "
                      f"excludes it")
                continue
        daily, diag = build_market(loader, code)
        if daily.empty:
            print(f"  {label:<14} FAILED   {diag.get('error', 'unknown')}")
            continue
        save_part(label, daily, diag)
        series[label] = daily.rename(label)
        _, diags[label] = load_part(label)
        print(f"  {label:<14} built    {len(daily):>6} days  "
              f"{daily.index.min():%Y-%m} .. {daily.index.max():%Y-%m}  "
              f"rank {diag.get('rank_med', float('nan')):.0f}, "
              f"{diag.get('share_med', 0) * 100:.0f}% of OI")
    return series, diags


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated labels to build")
    ap.add_argument("--refresh", action="store_true",
                    help="re-pull built markets even if cached")
    ap.add_argument("--assemble-only", action="store_true",
                    help="use cached parts, do not touch WRDS for them")
    ap.add_argument("--partial", action="store_true",
                    help="write the panel even if markets are missing")
    opts = ap.parse_args()

    markets = final_markets()
    print(f"target basket: {len(markets)} markets, "
          f"{len(CONTRACT_MARKETS)} contract-level series + "
          f"{len(CONTINUOUS_MARKETS)} continuous series, "
          f"{len(SPLICES)} spliced\n")

    all_built = {v[1] for v in CONTRACT_MARKETS.values()}
    wanted = all_built
    if opts.only:
        wanted = {x.strip() for x in opts.only.split(",")}
        unknown = wanted - all_built - set(CONTINUOUS_MARKETS)
        if unknown:
            raise SystemExit(f"unknown labels: {sorted(unknown)}")
        wanted &= all_built

    PARTS.mkdir(parents=True, exist_ok=True)
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        if opts.assemble_only:
            series, diags = {}, {}
            for _, label, _ in CONTRACT_MARKETS.values():
                cached, diag = load_part(label)
                if cached is not None:
                    series[label], diags[label] = cached, diag
            print(f"contract-level: {len(series)} series loaded from cache")
        else:
            series, diags = build_contract_markets(loader, wanted, opts.refresh)

        print(f"\ncontinuous: {len(CONTINUOUS_MARKETS)} series")
        cdaily, _, cmeta = build_panels(loader, CONTINUOUS_MARKETS,
                                        verbose=True)
    finally:
        loader.close()

    # -- assemble ---------------------------------------------------------
    frames = [pd.DataFrame(series)] if series else []
    frames.append(cdaily)
    daily = pd.concat(frames, axis=1).sort_index()

    for name, (cls, parts) in SPLICES.items():
        have = [p for p in parts if p in daily.columns]
        if not have:
            continue
        joined = splice_returns({p: daily[p] for p in have}, parts)
        daily = daily.drop(columns=have)
        daily[name] = joined
        print(f"spliced {name} <- {' then '.join(have)}: "
              f"{joined.notna().sum()} days")

    missing = sorted(set(markets) - set(daily.columns))
    extra = sorted(set(daily.columns) - set(markets))
    if extra:
        print(f"!! {len(extra)} unexpected column(s): {extra}")
    if missing and not opts.partial:
        # A warning that does not stop the write is no protection: an earlier
        # --only run clobbered a complete 51-market panel with 32 markets.
        raise SystemExit(
            f"\n!! {len(missing)} of {len(markets)} markets missing: "
            f"{missing}\n"
            f"Refusing to overwrite {OUT / DAILY_FILE} with an incomplete "
            f"panel.\nBuild them first, or pass --partial to write anyway.")
    if missing:
        print(f"\n!! writing a PARTIAL panel, {len(missing)} missing: "
              f"{missing}")

    order = sorted(daily.columns, key=lambda c: (markets.get(c, "?"), c))
    daily = daily[order]
    monthly = to_monthly(daily)

    # -- meta -------------------------------------------------------------
    cmeta_by_label = cmeta.set_index("label")
    rows = []
    for col in daily.columns:
        s = daily[col].dropna()
        src_parts = SPLICES[col][1] if col in SPLICES else [col]
        built_parts = [p for p in src_parts if p in diags]
        row = {
            "label": col, "asset_class": markets.get(col, "?"),
            "source": ("contract" if built_parts and len(built_parts) == len(src_parts)
                       else "mixed" if built_parts else "continuous"),
            "components": "+".join(src_parts) if len(src_parts) > 1 else "",
            "days": len(s), "first": s.index.min(), "last": s.index.max(),
        }
        if built_parts:
            d = diags[built_parts[0]]
            row.update({
                "ccy": d.get("ccy"), "n_contracts": d.get("n_contracts"),
                "oi_present": d.get("oi_present"),
                "rolls": d.get("n_rolls"),
                "roll_gap_mean": d.get("roll_gap_mean"),
                "roll_gap_median": d.get("roll_gap_median"),
                "roll_true_mean": d.get("roll_true_mean"),
                "roll_true_median": d.get("roll_true_median"),
                "oi_rank_med": d.get("rank_med"),
                "oi_share_med": d.get("share_med"),
                "hold_median_m": d.get("hold_median_m"),
            })
        elif col in cmeta_by_label.index:
            m = cmeta_by_label.loc[col]
            row.update({"ccy": m.get("isocurrcode"), "rolls": m.get("rolls"),
                        "roll_ok": m.get("roll_ok"),
                        "bad_zero": m.get("bad_zero"),
                        "bad_spike": m.get("bad_spike")})
        rows.append(row)
    meta = pd.DataFrame(rows).sort_values(["asset_class", "first"])

    OUT.mkdir(exist_ok=True)
    daily.to_csv(OUT / DAILY_FILE)
    monthly.to_csv(OUT / MONTHLY_FILE)
    meta.to_csv(OUT / META_FILE, index=False)

    print(f"\ndaily   {daily.shape[0]:>6} days   x {daily.shape[1]} markets"
          f" -> {OUT / DAILY_FILE}")
    print(f"monthly {monthly.shape[0]:>6} months x {monthly.shape[1]} markets"
          f" -> {OUT / MONTHLY_FILE}")
    print(f"meta    {meta.shape[0]:>6} rows              -> {OUT / META_FILE}")
    print(f"span: {monthly.index.min():%Y-%m} .. {monthly.index.max():%Y-%m}")
    print("by source: "
          + ", ".join(f"{k} {v}" for k, v in
                      meta['source'].value_counts().sort_index().items()))
    print("by class:  "
          + ", ".join(f"{k} {v}" for k, v in
                      meta['asset_class'].value_counts().sort_index().items()))

    live = monthly.loc[:, monthly.notna().sum() >= MIN_MONTHS_FOR_BREADTH]
    n, corr, breadth = effective_breadth(live)
    print(f"\nbreadth: {n} markets with >= {MIN_MONTHS_FOR_BREADTH} months, "
          f"mean |pairwise corr| {corr:.2f}, effective breadth {breadth:.1f}")
    print("  (35-market basket: 0.24 / previously reported; 10-ETF basket: 3.4)")

    print(f"\ndropped from the old basket ({len(DROPPED)}):")
    for mn, why in sorted(DROPPED.items(), key=lambda kv: kv[1]):
        print(f"  {mn:<10} {why}")


if __name__ == "__main__":
    main()
