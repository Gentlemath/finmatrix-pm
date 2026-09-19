"""Survey Datastream futures CLASSES by name, with real price coverage.

    python tools/survey_ds_classes.py "S&P 500"
    python tools/survey_ds_classes.py EURO --live-after 2026-04 --min-months 120
    python tools/survey_ds_classes.py YEN  --live-after 2026-04 --exclude EUROYEN,STOXX

A bare name can match hundreds of classes -- "EURO" returns 296, most of them
STOXX sector indices, European electricity and Eurodollar interest-rate futures.
Filter before reading:

    --live-after YYYY-MM  keep classes still priced on or after this date. Use
                          2026-04 to drop everything that died before the CME
                          withdrawal, which is the practical floor for a market
                          worth adding.
    --min-months N        keep classes with at least N months of price history.
    --ccy A,B             restrict to these quote currencies.
    --exclude A,B         drop classes whose name contains any of these.
    --limit N             print at most N rows (default 40).

Why this exists rather than searching the continuous-series table: a market has
several classes (``clscode``) and a continuous series pins it to exactly ONE.
Six basket markets were found pointing at a deprecated class while a live one
existed for the same instrument, and the US Treasuries were invisible because
the live classes sit under a SECOND naming family -- "... US T-NOTE COMP."
rather than "... US TREASURY NOTE". Searching by the basket's own name can never
find those. This queries the contract table instead, so it sees every class.

Read the output with the identity rule in mind:

    same currency AND same mnemonic family  -> same instrument, a real upgrade
    different currency or different prefix  -> a DIFFERENT market, not an upgrade

Matching on name alone flags ICE UK gas (GBP, LNG) as an "upgrade" to NYMEX
Henry Hub (USD, NNG), and Tokyo corn (JPY, JCN) as one to MATIF corn (EUR, PCO).

Read-only. The price aggregate is the expensive part, so it is done in a second
pass over only the classes the name filter matched.
"""

import argparse
from datetime import date

import pandas as pd

from portfolio_management.dataloader import create_data_loader

SCHEMA = "tr_ds_fut"
MIN_CONTRACTS = 5          # ignore classes with almost nothing in them


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", help="substring matched against contrname")
    ap.add_argument("--live-after", metavar="YYYY-MM",
                    help="keep classes still priced on or after this date")
    ap.add_argument("--min-months", type=int, default=0,
                    help="keep classes with at least this much price history")
    ap.add_argument("--ccy", help="comma-separated quote currencies to keep")
    ap.add_argument("--exclude", help="comma-separated substrings to drop")
    ap.add_argument("--limit", type=int, default=40, help="max rows to print")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    pattern = args.pattern

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        # pass 1: candidate classes from the contract table (463k rows, cheap)
        cand = loader.raw_sql(f"""
            select clscode,
                   min(isocurrcode)              as ccy,
                   count(distinct futcode)       as n_contracts,
                   min(contrname)                as contrname,
                   string_agg(distinct left(dsmnem, 3), ',')  as mnem_prefixes,
                   min(startdate)                as first_listed,
                   max(lasttrddate)              as last_trade
            from {SCHEMA}.wrds_contract_info
            where upper(contrname) like %(p)s
            group by clscode
            having count(distinct futcode) >= %(n)s
            order by clscode
        """, params={"p": f"%{pattern.upper()}%", "n": MIN_CONTRACTS})
        if cand.empty:
            print(f"no class matches '{pattern}'")
            return
        cand["clscode"] = pd.to_numeric(cand["clscode"]).astype("int64")

        # pass 2: actual price coverage, only for the matched classes
        cov = loader.raw_sql(f"""
            select i.clscode,
                   min(v.date_) as first_px,
                   max(v.date_) as last_px,
                   count(*)     as n_px
            from {SCHEMA}.wrds_contract_info i
            join {SCHEMA}.wrds_fut_contract v on v.futcode = i.futcode
            where i.clscode in %(c)s
            group by i.clscode
        """, params={"c": tuple(int(x) for x in cand["clscode"])})
        cov["clscode"] = pd.to_numeric(cov["clscode"]).astype("int64")
    finally:
        loader.close()

    df = cand.merge(cov, on="clscode", how="left")
    for c in ("first_px", "last_px"):
        df[c] = pd.to_datetime(df[c])
    df["stale_d"] = (pd.Timestamp(date.today()) - df["last_px"]).dt.days
    df["months"] = ((df["last_px"] - df["first_px"]).dt.days / 30.44).round()

    total = len(df)
    if args.live_after:
        df = df[df["last_px"] >= pd.Timestamp(args.live_after)]
    if args.min_months:
        df = df[df["months"].fillna(0) >= args.min_months]
    if args.ccy:
        keep = {c.strip().upper() for c in args.ccy.split(",")}
        df = df[df["ccy"].astype(str).str.upper().isin(keep)]
    if args.exclude:
        drop = [c.strip().upper() for c in args.exclude.split(",")]
        name = df["contrname"].astype(str).str.upper()
        df = df[~name.apply(lambda n: any(d in n for d in drop))]

    df = df.sort_values(["months", "last_px"], ascending=False)
    shown = df.head(args.limit)

    filt = []
    if args.live_after:
        filt.append(f"priced >= {args.live_after}")
    if args.min_months:
        filt.append(f">= {args.min_months} months")
    if args.ccy:
        filt.append(f"ccy in {args.ccy}")
    if args.exclude:
        filt.append(f"not matching {args.exclude}")
    print(f"=== classes matching '{pattern}': {len(df)} of {total}"
          + (f"  [{'; '.join(filt)}]" if filt else "") + " ===")
    if len(df) > len(shown):
        print(f"  (showing the {len(shown)} longest; raise --limit for more)")
    print(f"  {'clscode':>8}{'ccy':>5}{'mnem':>7}{'contracts':>11}{'months':>8}"
          f"{'first px':>11}{'last px':>11}{'stale':>8}  contrname")
    for _, r in shown.iterrows():
        first = f"{r['first_px']:%Y-%m}" if pd.notna(r["first_px"]) else "--"
        last = f"{r['last_px']:%Y-%m-%d}" if pd.notna(r["last_px"]) else "--"
        stale = f"{int(r['stale_d'])}d" if pd.notna(r["stale_d"]) else "--"
        mon = f"{int(r['months'])}" if pd.notna(r["months"]) else "--"
        print(f"  {r['clscode']:>8}{str(r['ccy']):>5}{str(r['mnem_prefixes'])[:6]:>7}"
              f"{int(r['n_contracts']):>11}{mon:>8}{first:>11}{last:>11}{stale:>8}"
              f"  {str(r['contrname'])[:44]}")

    live = df[df["stale_d"] <= 30]
    print(f"\n  {len(live)} of {len(df)} shown classes are priced within 30 days;"
          f" the rest stop earlier (CME classes all end 2026-04-03).")
    print("  Identity rule: same ccy AND same mnem prefix = same instrument.")
    print("  Anything else is a different market -- an addition, not an upgrade.")


if __name__ == "__main__":
    main()
