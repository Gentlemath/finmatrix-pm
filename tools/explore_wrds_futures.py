"""Discover what futures data YOUR WRDS subscription actually includes.

WRDS entitlements vary by institution, so there is no universal answer — this
lists what your account can see. Read-only; safe to run repeatedly.

It queries information_schema directly rather than the wrds package's
list_libraries(), which needs the very slow load_library_list() metadata pass.

Trend-following (Moskowitz-Ooi-Pedersen) is built on futures across equity-index,
bond, currency and commodity markets. The ETF basket in cache_etf_data.py is a
proxy for that; real futures would extend BOTH constraints the trend research log
identifies — a 20.5-year span (ETFs did not exist earlier) and an effective
breadth of only 3.4.
"""

import sys

from portfolio_management.dataloader import create_data_loader

# libraries whose names hint at futures / commodities / derivatives
HINTS = ["fut", "cme", "comm", "crb", "deriv", "cftc", "bloom", "datastream",
         "tfn", "optionm", "frb", "bond"]


def main() -> None:
    pattern = sys.argv[1] if len(sys.argv) > 1 else None

    loader = create_data_loader("wrds", autoconnect=False)
    loader.db.connect()
    try:
        schemas = loader.raw_sql("""
            select table_schema, count(*) as n_tables
            from information_schema.tables
            where table_schema not in ('information_schema', 'pg_catalog')
            group by table_schema order by table_schema
        """)
        print(f"{len(schemas)} accessible schemas\n")

        if pattern:
            print(f"=== tables matching '{pattern}' ===")
            hits = loader.raw_sql("""
                select table_schema, table_name
                from information_schema.tables
                where table_schema not in ('information_schema', 'pg_catalog')
                  and (table_name ilike %(p)s or table_schema ilike %(p)s)
                order by table_schema, table_name
            """, params={"p": f"%{pattern}%"})
            print(hits.to_string(index=False) if not hits.empty else "  (none)")
            print("\nInspect one with:\n"
                  "  loader.describe_table('<schema>', '<table>')")
            return

        print("=== schemas whose name suggests futures/derivatives ===")
        m = schemas[schemas["table_schema"].str.contains("|".join(HINTS), case=False)]
        print(m.to_string(index=False) if not m.empty else "  (none by name)")

        print("\n=== schemas that look like FUTURES PRICE data ===")
        fut = schemas[schemas["table_schema"].str.contains("fut", case=False)]
        print(fut.to_string(index=False) if not fut.empty else "  (none)")

        # list the tables inside each futures schema (skipping _old mirrors)
        for sch in fut["table_schema"]:
            if sch.endswith("_old"):
                continue
            tbls = loader.raw_sql("""
                select table_name,
                       (select count(*) from information_schema.columns c
                        where c.table_schema = t.table_schema
                          and c.table_name = t.table_name) as n_cols
                from information_schema.tables t
                where table_schema = %(s)s
                order by table_name
            """, params={"s": sch})
            print(f"\n  --- {sch} ({len(tbls)} tables) ---")
            print("  " + tbls.to_string(index=False).replace("\n", "\n  "))

        print("\nall accessible schemas:")
        print(", ".join(schemas["table_schema"].tolist()))
        print("\nNext:  python tools/explore_wrds_futures.py <pattern>")
    finally:
        loader.close()


if __name__ == "__main__":
    main()
