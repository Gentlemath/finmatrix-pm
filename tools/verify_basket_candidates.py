"""Verify candidate changes to the futures basket. READ-ONLY.

    python tools/verify_basket_candidates.py
    python tools/verify_basket_candidates.py --corr

Settles what has to be settled before anything is rebuilt. It reads
``local_data/futures_returns_monthly_wrds.csv`` and writes NOTHING.

1. TRUE COVERAGE. A continuous series emits rows past the date its prices stop
   (pitfall 4 in ds_futures.py), so counting ``_name_='Value_'`` rows overstates
   history. Coverage here requires a non-null settlement, which is what
   ``fetch_series`` keeps -- so these dates are what a rebuild would get.

2. IS EACH SPLICE VALID? Datastream stopped its CBT/CME-prefixed continuous
   series on 2015-07-10, and its CME GLOBEX ones on 2021-03-26, carrying the
   same markets on under other prefixes. Where an old and a new series overlap,
   monthly returns should agree almost exactly; if they do not, they are not the
   same instrument and must not be joined. A pair with NO overlap cannot be
   validated at all -- a result, not a failure: that splice would be an act of
   faith.

3. DOES DENOMINATION MATTER FOR THE METALS? A yen-priced gold future is gold
   times the yen, additive in log returns::

       r(TOCOM gold, JPY) = r(gold, USD) + r(USD per JPY)

   so the currency is a unit rather than an exposure -- but only if a yen series
   covering the whole span exists to divide it back out. Both signs are reported
   because the quote convention is the sort of thing to verify, not assume, and
   both roll treatments are reported because masking the roll day costs each
   series one real day per roll and two series roll on DIFFERENT days.

``--corr`` adds the section-G gate: each candidate's mean |correlation| against
the markets already in the panel. The basket averages 0.24; above that a
candidate dilutes effective breadth rather than adding to it.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management.dataloader import create_data_loader
from portfolio_management.dataloader.ds_futures import (
    SCHEMA, VALUE_ROW, clean_prices, fetch_series, mask_roll_returns,
    resolve_series, to_monthly)

PANEL = Path("local_data/futures_returns_monthly_wrds.csv")
MIN_OVERLAP = 24
BASELINE_CORR = 0.24

# Old series -> the successor that carried the market on.
SPLICES = [
    ("US30Y", "CUSCS00", "CZBCS00"),
    ("US10Y", "CTYCS00", "CZNCS00"),
    ("US5Y", "CFVCS00", "CZFCS00"),
    ("US2Y", "CTUCS00", "CZTCS00"),
    ("JPYUSD", "IJYCS00", "IJGCS00"),
    ("CADUSD", "ICDCS00", "ICFCS00"),
    ("GBPUSD", "IBPCS00", "IDPCS00"),
    ("GOLDusd", "CKICS00", "CZGCS00"),   # expected: no overlap
    ("SLVRusd", "CAGCS00", "CZICS00"),   # expected: no overlap
    # USD successors on exchanges that never withdrew -> no currency overlay
    ("GOLD_DG", "CZGCS00", "DDGCS00"),
    ("SLVR_DG", "CZICS00", "DDSCS00"),
    ("GOLD_TW", "CZGCS00", "TGDCS00"),
]

# (label, TOCOM series in yen, COMEX series in USD, column in the panel).
# The COMEX leg is refetched rather than read from the panel so the unmasked
# comparison has an unmasked counterparty on BOTH sides.
METALS = [("GOLD", "JAUCS00", "CZGCS00", "GOLD"),
          ("SILVER", "JSVCS00", "CZICS00", "SILVER")]
FX_JPY = "IJGCS00"

ADDS = {
    "MMWCS00": "WHEAT_US", "JCNCS00": "CORN_TKY", "LNGCS00": "NATGAS_UK",
    "SACCS00": "WHEAT_ZAR", "CUCCS00": "EURUSD", "ISPCS00": "SP500",
    "JAUCS00": "GOLD_TOCOM", "JSVCS00": "SILVER_TOCOM",
    "DDGCS00": "GOLD_DGCX", "DDSCS00": "SILVER_DGCX",
    "AGDCS00": "AUS10Y", "CDGCS00": "CAN10Y",
}
EXTRA = ["ISFCS00", "IADCS00", "CYGCS00", "CYICS00", "CGDCS00", "TGDCS00"]


def candidates() -> list:
    out = list(ADDS) + EXTRA + [FX_JPY]
    for _, old, new in SPLICES:
        out += [old, new]
    return sorted(set(out))


def coverage(loader, codes) -> pd.DataFrame:
    """Per series: observations and span, counting only priced days."""
    df = loader.raw_sql(f"""
        select v.calcseriescode, count(*) as n_px,
               min(v.date_) as first_px, max(v.date_) as last_px
        from {SCHEMA}.wrds_fut_series v
        where v.calcseriescode in %(c)s
          and v._name_ = %(nm)s
          and v.settlement is not null
        group by v.calcseriescode
    """, params={"c": tuple(int(c) for c in codes), "nm": VALUE_ROW})
    if df.empty:
        return df
    df["calcseriescode"] = pd.to_numeric(df["calcseriescode"]).astype("int64")
    df["n_px"] = pd.to_numeric(df["n_px"]).astype("int64")
    for c in ("first_px", "last_px"):
        df[c] = pd.to_datetime(df[c])
    return df.set_index("calcseriescode")


def monthly(loader, code: int, mask: bool = True) -> pd.Series:
    """Monthly returns; ``mask=True`` is how ``build_panels`` builds them.

    With ``mask=False`` the roll-day return is kept. That number is spurious --
    it compares two different contracts (pitfall 2) -- but masking costs each
    series one real day per roll, and two series rolling on different days lose
    DIFFERENT days, which is disagreement we create ourselves.
    """
    got = fetch_series(loader, int(code))
    if got.empty:
        return pd.Series(dtype="float64")
    px, _, _ = clean_prices(got)
    if mask:
        ret, _, _ = mask_roll_returns(px)
    else:
        ret = px["px"].pct_change()
    m = to_monthly(ret.to_frame("r"))["r"]
    m.index = m.index.to_period("M")
    return m.dropna()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corr", action="store_true",
                    help="also gate candidates on correlation to the panel")
    opts = ap.parse_args()

    if not PANEL.exists():
        raise SystemExit(f"need {PANEL} for the comparisons (read-only)")
    panel = pd.read_csv(PANEL, index_col=0, parse_dates=True)
    panel.index = panel.index.to_period("M")
    print(f"panel (read-only): {panel.shape[0]} months x {panel.shape[1]} "
          f"markets, {panel.index.min()} .. {panel.index.max()}\n")

    wanted = candidates()
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        info = resolve_series(loader, wanted)
        code_of = dict(zip(info["dsmnem"], info["calcseriescode"]))
        ccy_of = dict(zip(info["dsmnem"], info["isocurrcode"]))
        name_of = dict(zip(info["dsmnem"], info["calcseriesname"]))
        gone = sorted(set(wanted) - set(code_of))
        if gone:
            print(f"!! not in wrds_cseries_info: {gone}\n")
        cov = coverage(loader, list(code_of.values()))

        print("=" * 74)
        print("1. TRUE COVERAGE  (priced days only)")
        print("=" * 74)
        print(f"  {'dsmnem':<10}{'ccy':>5}{'obs':>8}{'first':>10}"
              f"{'last':>12}  name")
        for mn in sorted(code_of, key=lambda m: str(name_of.get(m, ""))):
            c = code_of[mn]
            if c not in cov.index:
                print(f"  {mn:<10}{str(ccy_of.get(mn)):>5}{0:>8}"
                      f"{'--':>10}{'--':>12}  NO PRICED DAYS")
                continue
            r = cov.loc[c]
            first, last = f"{r['first_px']:%Y-%m}", f"{r['last_px']:%Y-%m-%d}"
            print(f"  {mn:<10}{str(ccy_of.get(mn)):>5}{r['n_px']:>8}"
                  f"{first:>10}{last:>12}  {str(name_of.get(mn))[:34]}")

        need = {FX_JPY}
        for _, old, new in SPLICES:
            need |= {old, new}
        for _, a, b, _ in METALS:
            need |= {a, b}
        if opts.corr:
            need |= set(ADDS)
        need &= set(code_of)
        nomask_need = ({FX_JPY} | {a for _, a, _, _ in METALS}
                       | {b for _, _, b, _ in METALS}) & set(code_of)

        print(f"\npulling {len(need)} series (+{len(nomask_need)} unmasked) "
              f"...")
        series, nomask = {}, {}
        for mn in sorted(need):
            series[mn] = monthly(loader, code_of[mn])
        for mn in sorted(nomask_need):
            nomask[mn] = monthly(loader, code_of[mn], mask=False)
    finally:
        loader.close()

    print("\n" + "=" * 74)
    print("2. SPLICE VALIDITY  (monthly returns on the overlap)")
    print("=" * 74)
    print(f"  {'market':<9}{'old':<9}{'new':<9}{'n':>5}{'corr':>7}{'beta':>7}"
          f"{'volOld':>8}{'volNew':>8}  verdict")
    for label, old, new in SPLICES:
        a, b = series.get(old), series.get(new)
        if a is None or b is None or a.empty or b.empty:
            print(f"  {label:<9}{old:<9}{new:<9}{'--':>5}  series missing")
            continue
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        if len(j) < MIN_OVERLAP:
            gap = (f"gap {a.index.max()} -> {b.index.min()}"
                   if a.index.max() < b.index.min() else "")
            print(f"  {label:<9}{old:<9}{new:<9}{len(j):>5}{'':>29}"
                  f"  NO OVERLAP, unverifiable  {gap}")
            continue
        corr = j["a"].corr(j["b"])
        beta = np.polyfit(j["b"], j["a"], 1)[0] if j["b"].std() > 0 else np.nan
        ok = ("same instrument" if corr > 0.99
              else "SUSPECT" if corr > 0.95 else "NOT THE SAME")
        print(f"  {label:<9}{old:<9}{new:<9}{len(j):>5}{corr:>7.3f}"
              f"{beta:>7.2f}{j['a'].std() * np.sqrt(12) * 100:>7.1f}%"
              f"{j['b'].std() * np.sqrt(12) * 100:>7.1f}%  {ok}")
    print("  corr > 0.99 with beta ~ 1.00 and matching vol means the two are\n"
          "  the same instrument on different roll dates, and can be joined.")

    print("\n" + "=" * 74)
    print("3. DENOMINATION TEST FOR THE METALS")
    print("=" * 74)
    fx = series.get(FX_JPY, pd.Series(dtype="float64"))
    if fx.empty:
        print(f"  {FX_JPY} has no data -- cannot test the identity")
    else:
        print(f"  yen series {FX_JPY}: {len(fx)} months, "
              f"{fx.index.min()} .. {fx.index.max()}")
        print("  NOTE: that end date is also the last month in which the "
              "metals\n  could be converted to USD at all.\n")
        print(f"  {'metal':<8}{'roll':<8}{'n':>5}{'local':>8}{'r+fx':>8}"
              f"{'r-fx':>8}{'beta':>7}{'volLoc':>8}{'volUSD':>8}"
              f"{'corrFX':>8}")
        for label, tocom, comex, _ in METALS:
            for tag, src in (("masked", series), ("raw", nomask)):
                t, f, c = src.get(tocom), src.get(FX_JPY), src.get(comex)
                if any(x is None or x.empty for x in (t, f, c)):
                    print(f"  {label:<8}{tag:<8}  a series is missing")
                    continue
                j = pd.concat([t.rename("t"), f.rename("f"), c.rename("c")],
                              axis=1).dropna()
                if len(j) < MIN_OVERLAP:
                    print(f"  {label:<8}{tag:<8}{len(j):>5}  too short")
                    continue
                plus = (1 + j["t"]) * (1 + j["f"]) - 1
                minus = (1 + j["t"]) / (1 + j["f"]) - 1
                beta = (np.polyfit(j["c"], plus, 1)[0]
                        if j["c"].std() > 0 else np.nan)
                print(f"  {label:<8}{tag:<8}{len(j):>5}"
                      f"{j['t'].corr(j['c']):>8.3f}{plus.corr(j['c']):>8.3f}"
                      f"{minus.corr(j['c']):>8.3f}{beta:>7.2f}"
                      f"{j['t'].std() * np.sqrt(12) * 100:>7.1f}%"
                      f"{j['c'].std() * np.sqrt(12) * 100:>7.1f}%"
                      f"{j['f'].corr(j['c']):>8.3f}")
        print("\n  'local' is TOCOM as-is; 'r+fx'/'r-fx' apply the yen the two"
              "\n  possible ways -- whichever nears 1.00 is the convention AND"
              "\n  confirms the contract is the same metal. 'masked' vs 'raw'"
              "\n  isolates how much of any shortfall is our own roll masking"
              "\n  dropping a different day from each series.")

        print("\n  refetch vs panel (should be ~1.0000: confirms this script"
              "\n  rebuilds the basket the way build_panels did)")
        for label, _, comex, col in METALS:
            c = series.get(comex)
            if c is None or c.empty or col not in panel.columns:
                continue
            j = pd.concat([c.rename("new"), panel[col].rename("old")],
                          axis=1).dropna()
            d = (j["new"] - j["old"]).abs().max() * 1e4
            print(f"    {label:<8}{comex:<10}n={len(j):<5}"
                  f"corr={j['new'].corr(j['old']):.4f}  max|diff|={d:.1f}bp")

    if opts.corr:
        print("\n" + "=" * 74)
        print("4. CORRELATION GATE  (mean |corr| vs markets already in panel)")
        print("=" * 74)
        print(f"  baseline {BASELINE_CORR:.2f} -- above it a candidate dilutes"
              f" breadth")
        print(f"\n  {'candidate':<14}{'n':>5}{'mean|corr|':>12}"
              f"{'max|corr|':>11}  closest market")
        for mn, label in sorted(ADDS.items(), key=lambda kv: kv[1]):
            s = series.get(mn)
            if s is None or s.empty:
                print(f"  {label:<14}  no data")
                continue
            j = pd.concat([s.rename("x"), panel], axis=1).dropna(subset=["x"])
            n = int(j["x"].notna().sum())
            c = j.corr()["x"].drop("x").dropna()
            if c.empty or n < MIN_OVERLAP:
                print(f"  {label:<14}{n:>5}  overlap too short")
                continue
            flag = ("  <-- above baseline" if c.abs().mean() > BASELINE_CORR
                    else "")
            print(f"  {label:<14}{n:>5}{c.abs().mean():>12.3f}"
                  f"{c.abs().max():>11.3f}  {c.abs().idxmax()}{flag}")


if __name__ == "__main__":
    main()
