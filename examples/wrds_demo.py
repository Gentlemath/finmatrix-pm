"""Try the WRDS data loader against a live WRDS connection.

Run this in YOUR terminal -- it needs network access and your WRDS account:

    export WRDS_USERNAME=your_wrds_username
    python examples/wrds_demo.py

On the first connection the wrds package prompts for your WRDS password and
offers to create a ~/.pgpass file so later runs don't prompt again.

A quick tour of the CIZ-native WRDSLoader. Each call runs independently and
failures are reported per-section, so it doubles as a smoke test against your
WRDS instance; whatever prints [FAILED] needs its table/column names adjusted
(the CIZ_* constants in WRDSLoader, or use describe_table to inspect).
"""

import os

from portfolio_management.dataloader import create_data_loader


def _try(label, fn):
    """Run one dataset call, print the result, and keep going on failure."""
    print(f"\n=== {label} ===")
    try:
        result = fn()
        print(result)
        return result
    except Exception as exc:
        print(f"[FAILED] {label}: {type(exc).__name__}: {exc}")
        return None


def main() -> None:
    if not os.environ.get("WRDS_USERNAME"):
        raise SystemExit(
            "Set your WRDS username first, e.g.:\n"
            "    export WRDS_USERNAME=your_wrds_username\n"
            "then rerun:  python examples/wrds_demo.py"
        )

    # Connecting prompts for your password on the first run (or uses ~/.pgpass).
    loader = create_data_loader("wrds")
    try:
        # CIZ monthly returns for AAPL 2025 (permno resolved by ticker).
        _try(
            "CIZ monthly returns (AAPL, 2025)",
            lambda: loader.get_crsp_monthly(
                permnos=loader.permnos_for_tickers(["AAPL"]),
                start="2025-01-01", end="2025-12-31",
            ).head(),
        )
        _try(
            "Total-return price panel (AAPL, MSFT)",
            lambda: loader.get_prices(
                ["AAPL", "MSFT"], start="2023-01-01", end="2023-06-30", by="ticker"
            ).tail(),
        )
        _try(
            "S&P 500 universe panels (2024) -> shapes",
            lambda: {
                name: obj.shape
                for name, obj in zip(
                    ("returns", "membership", "market_caps"),
                    loader.get_sp500_universe(start="2024-01-01", end="2024-12-31"),
                )
            },
        )
        _try(
            "Compustat annual (AAPL)",
            lambda: loader.get_compustat_annual(tickers=["AAPL"], start="2020-01-01").head(),
        )
        _try(
            "CCM link (gvkey 001690 = Apple)",
            lambda: loader.get_ccm_link(gvkeys=["001690"]),
        )
        _try(
            "CIZ schema: describe_table('crsp', 'msf_v2')",
            lambda: loader.describe_table("crsp", "msf_v2"),
        )
    finally:
        loader.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()
