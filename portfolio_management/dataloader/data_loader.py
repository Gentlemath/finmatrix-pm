"""Data loading module for portfolio management."""

import os
from pathlib import Path
from typing import Dict, Optional, Sequence, Union

import pandas as pd

from .base import BaseLoader, as_symbol_list, flatten_yfinance


class CSVDataLoader:
    """Load and manage CSV data files."""

    def __init__(self, data_dir: str = "local_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_csv(self, filename: str) -> pd.DataFrame:
        """Load CSV data file."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return pd.read_csv(filepath)

    def save_csv(self, df: pd.DataFrame, filename: str) -> None:
        """Save DataFrame to CSV."""
        filepath = self.data_dir / filename
        df.to_csv(filepath, index=False)
        print(f"Data saved to {filepath}")

    def list_csv_files(self) -> pd.Series:
        """List CSV files in the data directory."""
        return pd.Series([p.name for p in self.data_dir.glob("*.csv")])


class YFinanceLoader(BaseLoader):
    """Load price and simple fundamentals using yfinance."""

    def __init__(self):
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError(
                "yfinance is required for YFinanceLoader. Install it with `pip install yfinance`."
            ) from exc

        self.yf = yf

    def history(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1d",
        auto_adjust: bool = True,
        prepost: bool = False,
    ) -> pd.DataFrame:
        """Get historical price data for a ticker."""
        return self.yf.download(
            tickers=ticker,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=auto_adjust,
            prepost=prepost,
            threads=True,
        )

    def get_prices(
        self,
        symbols: Union[str, Sequence[str]],
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Return a canonical price panel (adjusted close) for one or more tickers."""
        tickers = as_symbol_list(symbols)
        raw = self.history(" ".join(tickers), start=start, end=end)
        # auto_adjust=True (the history() default) already yields adjusted prices.
        return flatten_yfinance(raw, field="Close")

    def get_info(self, ticker: str) -> pd.DataFrame:
        """Get available fundamental info for a ticker."""
        ticker_obj = self.yf.Ticker(ticker)
        info = ticker_obj.info or {}
        return pd.DataFrame([info])

    def get_simple_fundamentals(self, ticker: str) -> Dict[str, Optional[object]]:
        """Return basic fundamental metrics for a ticker."""
        info = self.get_info(ticker).iloc[0].to_dict()
        fields = [
            "symbol",
            "shortName",
            "industry",
            "sector",
            "marketCap",
            "trailingPE",
            "forwardPE",
            "dividendYield",
            "beta",
            "earningsPerShare",
        ]
        return {field: info.get(field) for field in fields}


class AlphaVantageLoader:
    """Load global equity and fundamental data from Alpha Vantage."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Alpha Vantage requires ALPHAVANTAGE_API_KEY in environment or api_key argument.")

        try:
            from alpha_vantage.timeseries import TimeSeries
            from alpha_vantage.fundamentaldata import FundamentalData
        except ImportError as exc:
            raise ImportError(
                "alpha_vantage is required for AlphaVantageLoader. "
                "Install it with `pip install alpha_vantage`."
            ) from exc

        self.TimeSeries = TimeSeries
        self.FundamentalData = FundamentalData
        self.ts = self.TimeSeries(key=self.api_key, output_format="pandas")
        self.fd = self.FundamentalData(key=self.api_key, output_format="pandas")

        try:
            from alpha_vantage.searchfunction import SearchFunction

            self.SearchFunction = SearchFunction(key=self.api_key, output_format="pandas")
        except Exception:
            self.SearchFunction = None

    def get_price(
        self,
        symbol: str,
        interval: str = "Daily",
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """Get price data for a global symbol."""
        method_name = f"get_{interval.lower()}"
        if not hasattr(self.ts, method_name):
            raise ValueError("Alpha Vantage price interval must be one of Daily, Weekly, Monthly.")

        method = getattr(self.ts, method_name)
        data, _ = method(symbol=symbol, outputsize=outputsize)
        return data

    def get_global_quote(self, symbol: str) -> pd.DataFrame:
        """Get the latest quote for a global equity symbol."""
        data, _ = self.ts.get_quote_endpoint(symbol)
        return data

    def get_fundamentals(self, symbol: str) -> pd.DataFrame:
        """Get company fundamentals from Alpha Vantage."""
        data, _ = self.fd.get_company_overview(symbol)
        return data

    def search_symbol(self, keywords: str) -> pd.DataFrame:
        """Search for global equities by keyword."""
        if self.SearchFunction is None:
            raise RuntimeError(
                "Alpha Vantage symbol search is unavailable. "
                "Upgrade alpha_vantage or use a newer release."
            )
        data, _ = self.SearchFunction.symbol_search(keywords)
        return data


class FREDLoader:
    """Load macroeconomic data from FRED."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED requires FRED_API_KEY in environment or api_key argument.")

        try:
            from fredapi import Fred
        except ImportError as exc:
            raise ImportError(
                "fredapi is required for FREDLoader. Install it with `pip install fredapi`."
            ) from exc

        self.fred = Fred(api_key=self.api_key)

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """Retrieve an economic time series from FRED."""
        return self.fred.get_series(
            series_id,
            observation_start=start_date,
            observation_end=end_date,
        )

    def get_series_info(self, series_id: str) -> Dict[str, object]:
        """Retrieve metadata for a FRED series."""
        return self.fred.get_series_info(series_id)


class AKShareLoader:
    """Load China market data from AKShare."""

    def __init__(self):
        try:
            import akshare as ak
        except ImportError as exc:
            raise ImportError(
                "akshare is required for AKShareLoader. Install it with `pip install akshare`."
            ) from exc

        self.ak = ak

    def china_stock_spot(self) -> pd.DataFrame:
        """Get current China A-share market spot prices."""
        return self.ak.stock_zh_a_spot()

    def china_stock_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get daily price data for a China A-share symbol."""
        return self.ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

    def china_fundamentals(self, symbol: str) -> pd.DataFrame:
        """Get fundamentals for a China stock symbol."""
        if hasattr(self.ak, "stock_zh_a_fundamental"):
            return self.ak.stock_zh_a_fundamental(symbol=symbol)

        if hasattr(self.ak, "stock_financial_analysis_indicator"):
            return self.ak.stock_financial_analysis_indicator(symbol=symbol)

        raise RuntimeError("AKShare fundamentals API is unavailable for this package version.")


class BaoStockLoader:
    """Load China A-share data as a backup via BaoStock."""

    def __init__(self):
        try:
            import baostock as bs
        except ImportError as exc:
            raise ImportError(
                "baostock is required for BaoStockLoader. Install it with `pip install baostock`."
            ) from exc

        self.bs = bs

    def _login(self):
        lg = self.bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"BaoStock login failed: {lg.error_msg}")

    def _logout(self):
        self.bs.logout()

    def get_daily_price(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjustflag: str = "2",
    ) -> pd.DataFrame:
        """Get historical daily price data for a BaoStock code."""
        self._login()
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag"
        rs = self.bs.query_history_k_data_plus(
            code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag,
        )
        if rs.error_code != "0":
            self._logout()
            raise RuntimeError(f"BaoStock query failed: {rs.error_msg}")

        data = []
        while rs.next():
            data.append(rs.get_row_data())

        self._logout()
        return pd.DataFrame(data, columns=rs.fields)


class TushareLoader:
    """Load China fundamentals using Tushare."""

    def __init__(self, token: Optional[str] = None):
        try:
            import tushare as ts
        except ImportError as exc:
            raise ImportError(
                "tushare is required for TushareLoader. Install it with `pip install tushare`."
            ) from exc

        self.token = token or os.environ.get("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("Tushare requires TUSHARE_TOKEN in environment or token argument.")

        ts.set_token(self.token)
        self.pro = ts.pro_api()

    def get_fundamentals(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get fundamentals for a China equity via Tushare."""
        query = {"ts_code": ts_code}
        if start_date:
            query["start_date"] = start_date
        if end_date:
            query["end_date"] = end_date
        return self.pro.fina_indicator(**query)

    def get_stock_basic(self, exchange: str = "SSE", list_status: str = "L") -> pd.DataFrame:
        """Get basic stock listings from Tushare."""
        return self.pro.stock_basic(exchange=exchange, list_status=list_status)

    def get_company_info(self, ts_code: str) -> pd.DataFrame:
        """Get company profile information from Tushare."""
        return self.pro.stock_company(ts_code=ts_code)


def _wrds_loader(**kwargs):
    """Lazily import WRDSLoader so the wrds package is only needed on demand."""
    from .wrds_loader import WRDSLoader

    return WRDSLoader(**kwargs)


DATA_SOURCE_CLASSES = {
    "csv": CSVDataLoader,
    "yfinance": YFinanceLoader,
    "alpha_vantage": AlphaVantageLoader,
    "fred": FREDLoader,
    "akshare": AKShareLoader,
    "baostock": BaoStockLoader,
    "tushare": TushareLoader,
    "wrds": _wrds_loader,
}


def create_data_loader(source: str, **kwargs):
    """Create a data loader instance by source name."""
    source_key = source.strip().lower()
    if source_key not in DATA_SOURCE_CLASSES:
        raise ValueError(
            f"Unknown data source: {source}. Supported sources: {list(DATA_SOURCE_CLASSES)}")
    return DATA_SOURCE_CLASSES[source_key](**kwargs)
