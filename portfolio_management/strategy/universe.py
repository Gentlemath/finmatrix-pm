"""Build point-in-time universe panels for survivorship-bias-free backtests.

CRSP gives index membership as spells (one row per security with a start and
end date). These helpers turn that, plus tidy monthly returns, into the aligned
panels the strategy consumes:

    - returns panel  (DatetimeIndex x security)
    - membership panel (boolean; True where the security is in the index)
    - market-cap panel (for value weighting)
"""

from typing import Optional, Sequence

import pandas as pd

from ..dataloader.base import pivot_to_panel


def build_membership(
    constituents: pd.DataFrame,
    dates: Sequence,
    id_col: str = "permno",
    start_col: str = "start",
    end_col: str = "ending",
) -> pd.DataFrame:
    """Build a boolean membership panel from index-constituent spells.

    Args:
        constituents: One row per membership spell, with an id and start/end
            dates (an open/NaT end date is treated as "still a member").
        dates: The dates (rows) the panel should span.
        id_col, start_col, end_col: Column names in ``constituents``.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(list(dates))).sort_values()
    ids = sorted(constituents[id_col].unique())
    membership = pd.DataFrame(False, index=dates, columns=ids)
    membership.index.name = "date"

    for spell in constituents.itertuples(index=False):
        cid = getattr(spell, id_col)
        start = pd.Timestamp(getattr(spell, start_col))
        raw_end = getattr(spell, end_col)
        end = pd.Timestamp(raw_end) if pd.notna(raw_end) else dates[-1]
        in_window = (dates >= start) & (dates <= end)
        membership.loc[in_window, cid] = True

    return membership


def panels_from_crsp(
    monthly: pd.DataFrame,
    constituents: Optional[pd.DataFrame] = None,
    date_col: str = "date",
    id_col: str = "permno",
    ret_col: str = "ret",
    mktcap_col: str = "mktcap",
    start_col: str = "start",
    end_col: str = "ending",
):
    """Turn tidy CRSP monthly rows (+ optional constituents) into panels.

    Column names are parameterized so CIZ-native frames plug in directly
    (e.g. ``date_col="mthcaldt"``, ``ret_col="mthret"``, ``start_col="mbrstartdt"``).

    Returns a tuple ``(returns, membership, market_caps)`` where ``membership``
    is ``None`` if no constituents are given and ``market_caps`` is ``None`` if
    the market-cap column is absent.
    """
    monthly = monthly.copy()
    returns = pivot_to_panel(monthly, date_col, id_col, ret_col)

    # Prefer a precomputed mktcap column; otherwise derive it from |prc| * shrout.
    market_caps = None
    if mktcap_col in monthly.columns:
        market_caps = pivot_to_panel(monthly, date_col, id_col, mktcap_col)
    elif {"prc", "shrout"}.issubset(monthly.columns):
        monthly[mktcap_col] = monthly["prc"].abs() * monthly["shrout"]
        market_caps = pivot_to_panel(monthly, date_col, id_col, mktcap_col)

    membership = None
    if constituents is not None:
        membership = build_membership(
            constituents, returns.index,
            id_col=id_col, start_col=start_col, end_col=end_col,
        )
        # Align columns to the returns panel (string labels from pivot).
        membership.columns = [str(c) for c in membership.columns]
        membership = membership.reindex(
            index=returns.index, columns=returns.columns, fill_value=False
        )

    return returns, membership, market_caps
