"""Package entrypoint for data loaders."""

from . import ds_futures
from .base import BaseLoader
from .data_loader import (
    AKShareLoader,
    AlphaVantageLoader,
    BaoStockLoader,
    CSVDataLoader,
    FREDLoader,
    TushareLoader,
    YFinanceLoader,
    create_data_loader,
)
from .wrds_loader import WRDSLoader

__all__ = [
    "BaseLoader",
    "ds_futures",
    "CSVDataLoader",
    "YFinanceLoader",
    "AlphaVantageLoader",
    "FREDLoader",
    "AKShareLoader",
    "BaoStockLoader",
    "TushareLoader",
    "WRDSLoader",
    "create_data_loader",
]
