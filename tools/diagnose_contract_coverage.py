"""Why does a built series start later than its class says it should?

    python tools/diagnose_contract_coverage.py 2442 3893

``build_market`` drops contracts with no ``lasttrddate`` -- the roll rule needs
an expiry to compare against -- while ``survey_ds_classes.py`` reports a class's
price coverage straight from the price table with no such requirement. So a
class can advertise history the builder cannot use, and the gap shows up as a
series that simply starts late.

This splits each class's contracts into those the builder keeps and those it
drops, and reports the price coverage of each group, so the loss is attributed
rather than guessed at. Read-only.
"""

import argparse

import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_contracts import (
    CONTRACT_MARKETS, SCHEMA)


def sweep() -> None:
    """Which classes silently lose contracts to a missing lasttrddate?

    Cheap: contract metadata only. A class with none is unaffected by the
    truncation and does not need rebuilding.
    """
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        df = loader.raw_sql(f"""
            select clscode,
                   count(*) as n,
                   count(*) filter (where lasttrddate is null) as n_missing,
                   min(startdate) as first_listed
            from {SCHEMA}.wrds_contract_info
            where clscode in %(c)s
            group by clscode
        """, params={"c": tuple(int(c) for c in CONTRACT_MARKETS)})
    finally:
        loader.close()
    df["clscode"] = pd.to_numeric(df["clscode"]).astype("int64")
    for c in ("n", "n_missing"):
        df[c] = pd.to_numeric(df[c]).astype("int64")
    df["label"] = df["clscode"].map(lambda c: CONTRACT_MARKETS[c][1])
    df["first_listed"] = pd.to_datetime(df["first_listed"])
    df = df.sort_values("n_missing", ascending=False)

    hit = df[df["n_missing"] > 0]
    print(f"{'label':<14}{'clscode':>8}{'contracts':>11}{'missing':>9}"
          f"{'pct':>7}  first listed")
    for _, r in df.iterrows():
        mark = "  <-- needs rebuild" if r["n_missing"] else ""
        print(f"{r['label']:<14}{r['clscode']:>8}{r['n']:>11}"
              f"{r['n_missing']:>9}{r['n_missing'] / r['n'] * 100:>6.0f}%"
              f"  {r['first_listed']:%Y-%m}{mark}")
    print(f"\n{len(hit)} of {len(df)} classes affected.")
    if len(hit):
        labels = ",".join(sorted(hit["label"]))
        print("rebuild with:\n  python examples/cache_futures_data_v2_wrds.py"
              f" --refresh --only {labels}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clscodes", nargs="*", type=int)
    ap.add_argument("--all", action="store_true",
                    help="sweep every class in CONTRACT_MARKETS for missing "
                         "expiry dates (contract metadata only, no prices)")
    opts = ap.parse_args()
    if opts.all:
        sweep()
        return
    if not opts.clscodes:
        raise SystemExit(__doc__)

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        for code in opts.clscodes:
            info = loader.raw_sql(f"""
                select futcode, dsmnem, contrname, isocurrcode,
                       startdate, lasttrddate
                from {SCHEMA}.wrds_contract_info
                where clscode = %(c)s
            """, params={"c": int(code)})
            print(f"\n=== clscode {code} ===")
            if info.empty:
                print("  no contracts")
                continue
            for c in ("startdate", "lasttrddate"):
                info[c] = pd.to_datetime(info[c])
            info["kept"] = info["lasttrddate"].notna()

            cov = loader.raw_sql(f"""
                select futcode, count(*) as n,
                       min(date_) as first_px, max(date_) as last_px
                from {SCHEMA}.wrds_fut_contract
                where futcode in %(f)s and settlement is not null
                group by futcode
            """, params={"f": tuple(int(f) for f in info["futcode"])})
            cov["futcode"] = pd.to_numeric(cov["futcode"])
            for c in ("first_px", "last_px"):
                cov[c] = pd.to_datetime(cov[c])
            info["futcode"] = pd.to_numeric(info["futcode"])
            df = info.merge(cov, on="futcode", how="left")

            for kept, g in df.groupby("kept"):
                tag = "KEPT (has lasttrddate)" if kept else "DROPPED (no lasttrddate)"
                px = g.dropna(subset=["first_px"])
                print(f"  {tag}: {len(g)} contracts, {len(px)} with prices")
                if len(px):
                    print(f"      prices {px['first_px'].min():%Y-%m} .. "
                          f"{px['last_px'].max():%Y-%m}, "
                          f"{int(px['n'].sum()):,} contract-days")
                    print(f"      example names: "
                          f"{', '.join(px['contrname'].astype(str).unique()[:3])}")
                    early = px.nsmallest(3, "first_px")
                    for _, r in early.iterrows():
                        print(f"        {str(r['dsmnem']):<10} "
                              f"{r['first_px']:%Y-%m-%d} .. {r['last_px']:%Y-%m-%d}"
                              f"  startdate={r['startdate']:%Y-%m-%d}"
                              if pd.notna(r["startdate"]) else
                              f"        {str(r['dsmnem']):<10} "
                              f"{r['first_px']:%Y-%m-%d} .. {r['last_px']:%Y-%m-%d}"
                              f"  startdate=NaT")
            miss = df[~df["kept"] & df["first_px"].notna()]
            if len(miss):
                print(f"  => dropping {len(miss)} priced contracts costs "
                      f"{miss['first_px'].min():%Y-%m} .. {miss['last_px'].max():%Y-%m}")
    finally:
        loader.close()


if __name__ == "__main__":
    main()
