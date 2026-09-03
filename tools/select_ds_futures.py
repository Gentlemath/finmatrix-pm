"""Find the liquid macro futures in tr_ds_fut. Vocabulary first, then whitelist.

Two lessons already learned the hard way:

1. Keyword search on product words fails — "SWISS FRANC" matches Budapest (HUF)
   and Warsaw (PLN) listings, "GOLD" matches an S&P/TSX gold *equity* index.
2. Exchange prefix alone cannot classify asset class — EUREX lists index futures,
   Bund/Bobl/Schatz AND hundreds of single-stock futures. Classifying by exchange
   mislabels all of them.

So: mode `vocab` (default) prints the actual exchange-prefix vocabulary with
counts, and mode `<PREFIX>` dumps every series name under that prefix. Look at
real names before whitelisting anything.

KEY: dsmnem encodes everything. It is [MARKET]CS[NN]:
  CS00..CS05  front contract under six roll conventions (00 month-start,
              01 after last trading day, 02 weighted volume, 03 volume switch,
              04 price index, 05 average of all futures)
  CS21/31/51/70  the 2nd/3rd/5th/7th nearest contract, NOT the front one
  ...C.01        Reuters Continuation Record, a separate family

So the reliable filter is dsmnem matching ^[A-Z]+CS0[0-5]$ — it keeps front-month
continuations and drops deferred-contract and Reuters variants automatically.
That is far more robust than matching product names. Roll method must still be
CONSISTENT across the basket or the assets are not comparable.
"""

import re
import sys

import pandas as pd

from portfolio_management.dataloader import create_data_loader

SCHEMA = "tr_ds_fut"
ROLL = 3


def load(loader, roll: int) -> pd.DataFrame:
    info = loader.raw_sql(f"""
        select calcseriescode, clscode, dsmnem, calcseriesname,
               isocurrcode, rollmethodcode
        from {SCHEMA}.wrds_cseries_info
        where rollmethodcode = %(r)s
    """, params={"r": roll})
    info["name_u"] = info["calcseriesname"].fillna("").str.upper()
    alive = info[~info["name_u"].str.contains("DEAD")].copy()
    # front-month continuations only: [MARKET]CS0n, not CS21/CS51/Reuters .01
    front = alive["dsmnem"].fillna("").str.match(r"^[A-Z]+CS0[0-5]$")
    return alive[front].copy()


# (exchange prefix, regex on the product name) for the liquid macro contracts.
# Exchange alone is not enough: EUREX/LIFFE/HKFE list hundreds of single-stock
# futures alongside the index and bond contracts.
MACRO = {
    "equity index": [
        ("CME", r"S&P 500|NASDAQ"), ("EUREX", r"\bDAX\b|EURO STOXX 50"),
        ("LIFFE", r"FTSE 100"), ("OSX", r"NIKKEI 225"), ("SGX", r"NIKKEI|MSCI"),
        ("SFE", r"SPI 200"), ("HKFE", r"HANG SENG INDEX"), ("TSE", r"TOPIX"),
        ("KSE", r"KOSPI 200"), ("CFE", r"VIX"),
    ],
    "bond / rate": [
        ("ECBOT", r"T-NOTE|T-BOND|FED FUNDS"),
        ("EUREX", r"EURO BUND|EURO BOBL|EURO SCHATZ|EURO BUXL"),
        ("LIFFE", r"LONG GILT|EURIBOR|SHORT STERLING"),
        ("SGX", r"JGB"), ("TSE", r"T-BOND"), ("SFE", r"T-BOND|BANK BILL"),
        ("CME", r"EURODOLLAR"),
    ],
    "currency": [
        ("CME", r"EURO|YEN|POUND|FRANC|DOLLAR|PESO|REAL"),
        ("FINEX", r"DOLLAR INDEX|EURO|YEN|POUND|FRANC"),
        ("ICE", r"DOLLAR INDEX|EURO|YEN|POUND|FRANC"),
    ],
    "energy": [
        ("NYM", r"CRUDE|NATURAL GAS|HEATING OIL|GASOLINE|RBOB"),
        ("NYMEX", r"CRUDE|NATURAL GAS|HEATING OIL|GASOLINE"),
        ("ICE", r"BRENT|GASOIL|WTI"),
    ],
    "metals": [
        ("LME", r"COPPER|ALUMINIUM|ZINC|NICKEL|LEAD|TIN"),
        ("NYL", r"GOLD|SILVER|COPPER|PLATINUM"),
        ("TOCOM", r"GOLD|SILVER|PLATINUM|RUBBER"),
        ("NYM", r"GOLD|SILVER|PLATINUM|PALLADIUM"),
    ],
    "agriculture": [
        ("CSCE", r"SUGAR|COFFEE|COCOA"),
        ("LIFFE", r"SUGAR|COFFEE|COCOA|WHEAT"),
        ("MATIF", r"WHEAT|RAPESEED|CORN|MAIZE"),
        ("ECBOT", r"CORN|WHEAT|SOYBEAN|OATS"),
        ("MGE", r"WHEAT"), ("NYCE", r"COTTON|ORANGE"),
        ("NYBOT", r"COTTON|SUGAR|COFFEE|COCOA"),
    ],
}


def macro_mode(alive, roll: int) -> None:
    """Apply the whitelist and report both hits and gaps."""
    rows, gaps = [], []
    for asset_class, rules in MACRO.items():
        print(f"=== {asset_class} ===")
        for pref, pattern in rules:
            hit = alive[alive["name_u"].str.startswith(pref.upper())
                        & alive["name_u"].str.contains(pattern, regex=True)]
            if hit.empty:
                gaps.append(f"{pref}: {pattern}")
                print(f"  {pref:<8}{pattern[:34]:<36}(none)")
                continue
            print(f"  {pref:<8}{pattern[:34]:<36}{len(hit)} found")
            for _, h in hit.sort_values("calcseriesname").iterrows():
                print(f"      {int(h['calcseriescode']):>6}  {h['dsmnem']:<10}"
                      f"{h['isocurrcode']:<5}{h['calcseriesname']}")
                rows.append({"asset_class": asset_class, "code": int(h["calcseriescode"]),
                             "mnem": h["dsmnem"], "ccy": h["isocurrcode"],
                             "name": h["calcseriesname"], "roll": roll})
        print()

    if gaps:
        print(f"=== {len(gaps)} rules matched nothing (real gaps) ===")
        for g in gaps:
            print(f"  {g}")
    if rows:
        out = pd.DataFrame(rows).drop_duplicates(subset=["code"])
        out.to_csv("local_data/ds_futures_basket.csv", index=False)
        print(f"\n{len(out)} distinct series -> local_data/ds_futures_basket.csv")
        print(out.groupby("asset_class").size().to_string())


def find_mode(pattern: str) -> None:
    """Unfiltered search: every roll method, dead series included.

    The other modes filter to alive front-month CS0x series, which is right for
    building a basket but wrong for answering "does this contract exist at all".
    Use this to settle that question before concluding something is missing.
    """
    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        hit = loader.raw_sql(f"""
            select calcseriescode, dsmnem, calcseriesname, isocurrcode,
                   rollmethodcode
            from {SCHEMA}.wrds_cseries_info
            where upper(calcseriesname) like %(p)s
            order by calcseriesname
        """, params={"p": f"%{pattern.upper()}%"})
    finally:
        loader.close()

    if hit.empty:
        print(f"'{pattern}' matches nothing anywhere in wrds_cseries_info.")
        return
    hit["dead"] = hit["calcseriesname"].str.upper().str.contains("DEAD")
    hit["front"] = hit["dsmnem"].fillna("").str.match(r"^[A-Z]+CS0[0-5]$")
    print(f"'{pattern}': {len(hit)} series  "
          f"({int((~hit['dead']).sum())} alive, "
          f"{int(hit['front'].sum())} front-month CS0x)\n")
    print(f"  {'code':>7} {'mnem':<10}{'roll':>5} {'st':<6}{'ccy':<5}name")
    for _, h in hit.iterrows():
        st = ("DEAD" if h["dead"] else "ok") + ("" if h["front"] else "*")
        rm = int(h["rollmethodcode"]) if pd.notna(h["rollmethodcode"]) else -1
        print(f"  {int(h['calcseriescode']):>7} {str(h['dsmnem']):<10}{rm:>5} "
              f"{st:<6}{str(h['isocurrcode']):<5}{h['calcseriesname']}")
    print("\n  * = not a front-month CS0x series (deferred contract or Reuters record)")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "vocab"
    roll = int(sys.argv[2]) if len(sys.argv) > 2 else ROLL

    if arg == "find":
        if len(sys.argv) < 3:
            raise SystemExit("usage: find <pattern>")
        find_mode(sys.argv[2])
        return

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        alive = load(loader, roll)
    finally:
        loader.close()
    print(f"roll {roll}: {len(alive):,} alive series\n")

    if arg == "macro":
        macro_mode(alive, roll)
        return

    if arg == "vocab":
        # exchange token = text before the first '-' or ' ' in the name
        alive["exch"] = alive["name_u"].apply(
            lambda s: re.split(r"[-\s]", s, maxsplit=1)[0] if s else "?")
        vc = alive["exch"].value_counts()
        print("=== exchange-prefix vocabulary, front-month series only ===")
        for k, v in vc[vc >= 3].items():
            print(f"  {k:<16}{v:>6}")
        print(f"\n({(vc < 3).sum()} prefixes with <3 series omitted)")
        print(f"\nDump one:   python {sys.argv[0]} <PREFIX> [roll]")
        print(f"Whitelist:  python {sys.argv[0]} macro [roll]")
        return

    hit = alive[alive["name_u"].str.startswith(arg.upper())]
    print(f"=== {arg.upper()}: {len(hit)} series ===")
    if hit.empty:
        print("  (none — check the vocabulary listing)")
        return
    for _, h in hit.sort_values("calcseriesname").iterrows():
        print(f"  {int(h['calcseriescode']):>6}  {h['dsmnem']:<10}"
              f"{h['isocurrcode']:<5}{h['calcseriesname']}")
    out = f"local_data/ds_fut_{arg.upper().strip('-')}.csv"
    hit.drop(columns=["name_u"]).to_csv(out, index=False)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
