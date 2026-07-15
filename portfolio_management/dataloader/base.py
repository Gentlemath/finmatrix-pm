"""Loader base class and output-normalization helpers.

Every price-capable loader can expose a common ``get_prices`` method that
returns a *canonical price panel*:

    - a ``pandas.DataFrame``
    - indexed by a ``DatetimeIndex`` named ``"date"``, sorted ascending
    - one column per symbol (plain string columns, never a MultiIndex)
    - float values = adjusted close price

That is exactly the shape ``PlotAnalyzer.compute_returns`` and the rest of the
EDA/TSM pipeline expect, so any loader that returns it plugs straight in.
"""

from abc import ABC, abstractmethod
from typing import Optional, Sequence, Union

import pandas as pd


class BaseLoader(ABC):
    """Interface for loaders that can produce a canonical price panel."""

    @abstractmethod
    def get_prices(
        self,
        symbols: Union[str, Sequence[str]],
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Return a canonical price panel (see module docstring)."""
        raise NotImplementedError


def as_symbol_list(symbols: Union[str, Sequence[str]]) -> list:
    """Normalize a single symbol or an iterable of symbols to a list of str."""
    if isinstance(symbols, str):
        return [symbols]
    return [str(s) for s in symbols]


def pivot_to_panel(
    df: pd.DataFrame,
    date_col: str,
    symbol_col: str,
    value_col: str,
) -> pd.DataFrame:
    """Reshape a long/tidy frame into a canonical wide price panel.

    Args:
        df: Long frame with one row per (date, symbol).
        date_col: Column holding the observation date.
        symbol_col: Column holding the security identifier.
        value_col: Column holding the price/value to place in the panel.
    """
    for col in (date_col, symbol_col, value_col):
        if col not in df.columns:
            raise KeyError(f"Column {col!r} not found in frame with columns {list(df.columns)}.")

    panel = df.pivot_table(index=date_col, columns=symbol_col, values=value_col, aggfunc="last")
    return _finalize_panel(panel)


def flatten_yfinance(df: pd.DataFrame, field: str = "Close") -> pd.DataFrame:
    """Reduce a yfinance ``download`` frame to a canonical price panel.

    yfinance returns a column MultiIndex of ``(field, ticker)`` for multiple
    tickers (and sometimes even for one). This selects ``field`` and flattens
    the columns down to plain ticker names.
    """
    if isinstance(df.columns, pd.MultiIndex):
        # Field may sit on either level depending on yfinance version/args.
        if field in df.columns.get_level_values(0):
            out = df.xs(field, axis=1, level=0)
        elif field in df.columns.get_level_values(1):
            out = df.xs(field, axis=1, level=1)
        else:
            raise KeyError(f"Field {field!r} not present in yfinance columns.")
    else:
        if field in df.columns:
            out = df[[field]]
        else:
            out = df
    out = out.copy()
    return _finalize_panel(out)


def _finalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Apply the canonical-panel invariants: datetime index, sorted, float."""
    panel.index = pd.to_datetime(panel.index)
    panel.index.name = "date"
    panel = panel.sort_index()
    panel.columns = [str(c) for c in panel.columns]
    return panel.astype("float64")
