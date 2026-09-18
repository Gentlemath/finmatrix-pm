"""Cache a daily US equity benchmark and risk-free rate from CRSP.

Run in YOUR terminal (needs your WRDS account). Licensed data -- local_data/ is
gitignored; do not commit the output.

    python examples/cache_equity_benchmark_wrds.py --probe      # look, pull nothing
    python examples/cache_equity_benchmark_wrds.py              # pull and save

WHY THIS EXISTS. Both equity benchmarks available so far start too late:

  * the SPY ETF at 2006-02, so `--start 1979-12` silently began the equity
    comparison twenty-seven years late;
  * v2's own SP500 futures at 1982-04, nine years after the trend panel, which
    excludes the 1973-74 bear market -- the episode a crisis-alpha argument
    most wants.

CRSP's index files are daily and reach 1925. Daily matters for three of the four
things a benchmark is used for: volatility (estimable from short windows),
drawdowns (a month-end series cannot see an intramonth trough, so every maxDD in
the demos is understated), and crisis correlation (a question about days). It
does NOT sharpen the Sharpe t-statistics -- SE ~ 1/sqrt(years) has no frequency
term.

EXCESS VERSUS TOTAL RETURN, which is the whole reason rf is pulled too. The trend
leg is an excess return: futures are self-financing and earn no collateral
interest. `sprtrn` and `vwretd` are TOTAL returns. Subtracting a CONSTANT cash
rate is not good enough across 1980s double-digit rates and the 2010s zero bound
-- and getting this wrong is silent, as it was in trend_portfolio_demo.py, where
cash was subtracted from the futures series that never contained it and cost the
equity Sharpe 0.11. So this writes rf alongside and forms the excess return
date by date.

WHAT IS PULLED. Index tables carry several return series; we keep sprtrn (the
S&P 500, closest to what the demos call SPY), vwretd (value-weighted, all listed
US stocks, WITH distributions) and vwretx (the same WITHOUT them -- their
difference is the dividend contribution, which is most of the long-run gap).
The risk-free column name is discovered rather than assumed: the Fama files use
names like tdyld/tmytm that vary by table, and the printout shows the magnitude
so an annualised-versus-daily mixup is visible rather than silent.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management.dataloader import create_data_loader

OUT = Path("local_data")
START = "1925-01-01"

# CIZ-style query views, with the classic tables as fallback. Both were present
# in the --discover sweep; whichever reaches further back wins.
INDEX_TABLES = {
    "daily": [("crsp.wrds_dailyindexret_query", "dlycaldt"), ("crsp.dsi", "date")],
    "monthly": [("crsp.wrds_monthlyindexret_query", "mthcaldt"), ("crsp.msi", "date")],
}
# Fama-French first: its `rf` is an actual period RETURN, already the object we
# need. The CRSP Fama files are the fallback and give YIELDS (tdyld, tmytm),
# which must be converted -- one more place to be silently wrong.
RF_TABLES = {
    "daily": [("ff.factors_daily", "date", "rf", None),
              ("crsp.tfz_dly_rf2", "caldt", "tdyld", "tdduratn")],
    "monthly": [("ff.factors_monthly", "date", "rf", None),
                ("crsp.tfz_mth_rf", "mcaldt", "tmytm", "tmduratn")],
}
KEEP = ["sprtrn", "vwretd", "vwretx"]
# Fama-French's market factor is the value-weighted US market EXCESS return --
# already net of cash, so it needs neither conversion nor subtraction, and it is
# the one series here that reaches 2026-07. The CRSP index stops 2025-12, which
# would otherwise truncate the comparison seven months short of v1's panel.
FF_EXTRA = ["mktrf"]
# Candidate rate columns in the Fama risk-free files, best first. tdyld is a
# DAILY yield; tmytm is an ANNUALISED yield in percent. The scale check below
# tells them apart from the data instead of trusting this comment.
RF_COLS = ["tdyld", "tmytm", "tmretnua", "tdretnua", "rf"]


def columns_of(loader, table: str) -> list:
    schema, name = table.split(".", 1)
    c = loader.raw_sql("""
        select column_name from information_schema.columns
        where table_schema = %(s)s and table_name = %(t)s
        order by ordinal_position
    """, params={"s": schema, "t": name})
    return list(c["column_name"])


def span(loader, table: str, datecol: str):
    """(first, last, n) for a table, or None if it cannot be read."""
    try:
        r = loader.raw_sql(
            f"select min({datecol}) a, max({datecol}) b, count(*) n from {table}")
        return r.iloc[0]["a"], r.iloc[0]["b"], int(r.iloc[0]["n"])
    except Exception as e:                      # noqa: BLE001 - report, don't die
        print(f"    {table}: unreadable ({str(e).splitlines()[0][:60]})")
        return None


def pick_index_table(loader, freq: str, probe_only: bool):
    """Choose the candidate index table with the widest coverage."""
    best = None
    for table, datecol in INDEX_TABLES[freq]:
        s = span(loader, table, datecol)
        if s is None:
            continue
        cols = columns_of(loader, table)
        have = [c for c in KEEP if c in cols]
        print(f"    {table:<42}{str(s[0])[:10]} .. {str(s[1])[:10]}  "
              f"{s[2]:>8,} rows   has: {', '.join(have) or 'NONE'}")
        # Earliest start wins; on a tie take the later END. Both families start
        # 1925-12-31, so the tie-break is what picks the CIZ views (through
        # 2025) over the classic tables (2024) -- a free extra year.
        if have:
            if best is None:
                best = (table, datecol, s[0], have, s[1])
            elif s[0] < best[2] or (s[0] == best[2] and s[1] > best[4]):
                best = (table, datecol, s[0], have, s[1])
    if best is None and not probe_only:
        raise SystemExit(f"no usable {freq} index table")
    return best


def pick_rf(loader, freq: str):
    """Find a risk-free series, preferring a true return over a yield.

    Where a table holds several bills keyed by kytreasnox, the shortest is the
    one we want for cash -- and the duration column says which that is. The key
    numbers do NOT: the monthly file uses 2000001/2000002 (the familiar Fama
    30- and 90-day pair) while the daily file uses 2000061/2000062/2000063,
    whose ordering carries no guarantee about maturity.
    """
    for table, datecol, rate, dur in RF_TABLES[freq]:
        cols = columns_of(loader, table)
        if rate not in cols:
            print(f"    {table:<42}no '{rate}' column -- skipping")
            continue
        s = span(loader, table, datecol)
        if s is None:
            continue
        kind = "period RETURN" if dur is None else f"YIELD (convert via {rate})"
        print(f"    {table:<42}{str(s[0])[:10]} .. {str(s[1])[:10]}  {kind}")
        key = None
        if "kytreasnox" in cols and dur:
            d = loader.raw_sql(f"""
                select kytreasnox, avg({dur}) as dur, count(*) as n
                from {table} group by kytreasnox order by dur
            """)
            for _, r in d.iterrows():
                print(f"      kytreasnox {int(r['kytreasnox'])}  "
                      f"mean {dur} {r['dur']:.1f} days  {int(r['n']):,} rows")
            key = int(d.iloc[0]["kytreasnox"])
            print(f"      -> shortest maturity is {key} "
                  f"({d.iloc[0]['dur']:.1f} days), chosen BY DURATION not by key order")
        return table, datecol, rate, key
    print(f"    no usable {freq} risk-free table")
    return None


def fetch(loader, table, datecol, cols, where="", freq=None) -> pd.DataFrame:
    """Read a table, and for monthly data snap the index to month END.

    The sources disagree about how to stamp a month: CRSP uses the last day
    (1925-12-31), Fama-French the first (1926-07-01). Joining them raw matches
    nothing -- it produced 2,402 rows from two 1,201-row inputs and left every
    excess-return column NaN, which the summary then hid by skipping series with
    under 100 observations. Month-end also matches the futures panel, whose
    index runs 1973-01-31, 1973-02-28, ...
    """
    sel = ", ".join([datecol] + cols)
    df = loader.raw_sql(
        f"select {sel} from {table} where {datecol} >= %(s)s {where} "
        f"order by {datecol}", params={"s": START})
    df = df.rename(columns={datecol: "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    if freq == "monthly":
        df.index = df.index.to_period("M").to_timestamp("M")
    return df


def build(loader, freq: str, probe_only: bool):
    print(f"\n  {freq} index:")
    idx = pick_index_table(loader, freq, probe_only)
    print(f"  {freq} risk-free:")
    rf = pick_rf(loader, freq)
    if probe_only or idx is None:
        return None

    table, datecol, _, have, _end = idx
    px = fetch(loader, table, datecol, have, freq=freq)

    if rf is not None:
        rtab, rdate, rate, key = rf
        where = f"and kytreasnox = {key}" if key is not None else ""
        extra = [c for c in FF_EXTRA if c in columns_of(loader, rtab)]
        rdf = fetch(loader, rtab, rdate, [rate] + extra, where, freq=freq)
        rdf = rdf[~rdf.index.duplicated()]
        r = rdf[rate]
        # Scale check: a DAILY rate is ~1e-4, an ANNUALISED PERCENT is ~5.
        # Deciding from the data beats trusting the column name.
        med = float(np.nanmedian(r.abs()))
        per_year = 252 if freq == "daily" else 12
        if med > 0.5:                     # percent per year -> per period
            r, note = r / 100.0 / per_year, f"annualised % (median {med:.2f})"
        elif med > 0.01:                  # decimal per year -> per period
            r, note = r / per_year, f"annualised decimal (median {med:.4f})"
        else:
            note = f"already per-period (median {med:.6f})"
        print(f"      rate scale: {note} -> per-{'day' if freq == 'daily' else 'month'}"
              f" median {float(np.nanmedian(r.abs())):.6f}")
        # OUTER join, not left: mktrf extends past the CRSP index and we want
        # those months, with the CRSP columns simply NaN there.
        px = px.join(r.rename("rf"), how="outer")
        for c in extra:
            px = px.join(rdf[c], how="outer")
        for c in have:
            px[f"{c}_excess"] = px[c] - px["rf"]
        # A join that matched nothing looks exactly like a successful one until
        # you count rows, so count them: overlap should be nearly the whole of
        # the shorter input, never zero.
        overlap = int(px[["rf"] + have].notna().all(axis=1).sum())
        print(f"      join: {len(px):,} rows, {overlap:,} with both index and rf"
              f" ({overlap / min(len(r), len(px)) * 100:.0f}% of the shorter input)")
        if overlap < 0.5 * min(len(r), len(px)):
            raise SystemExit("index and rf dates do not align -- refusing to write")
    return px


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true",
                    help="show tables, columns and coverage; pull nothing")
    opts = ap.parse_args()

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        out = {f: build(loader, f, opts.probe) for f in ("daily", "monthly")}
    finally:
        loader.close()
    if opts.probe:
        print("\nprobe only -- nothing written. Re-run without --probe to pull.")
        return

    OUT.mkdir(exist_ok=True)
    for freq, df in out.items():
        if df is None:
            continue
        f = OUT / f"equity_benchmark_{freq}.csv"
        df.to_csv(f)
        print(f"\n{freq}: {len(df):,} rows x {df.shape[1]} cols -> {f}")
        print(f"  {df.index.min():%Y-%m-%d} .. {df.index.max():%Y-%m-%d}")
        print(f"  columns: {', '.join(df.columns)}")
        ann = 252 if freq == "daily" else 12
        print(f"  {'series':<16}{'n':>8}{'ann.ret':>10}{'ann.vol':>10}")
        for c in df.columns:
            s = df[c].dropna()
            if len(s) < 100:
                continue
            print(f"  {c:<16}{len(s):>8,}{s.mean() * ann * 100:>9.2f}%"
                  f"{s.std() * np.sqrt(ann) * 100:>9.2f}%")
        print("  (sprtrn ~10%/yr total, vwretd similar, vwretx lower by the "
              "dividend yield,\n   rf ~3-4%/yr. mktrf and the _excess columns "
              "are already net of cash --\n   those are what the trend leg must "
              "be compared against.)")


if __name__ == "__main__":
    main()
