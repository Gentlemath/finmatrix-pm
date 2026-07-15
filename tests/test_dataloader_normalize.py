"""Tests for the loader normalization helpers in dataloader/base.py."""

import pandas as pd
import pytest

from portfolio_management.dataloader.base import (
    as_symbol_list,
    flatten_yfinance,
    pivot_to_panel,
)


class TestAsSymbolList:
    def test_single_string_becomes_list(self):
        assert as_symbol_list("AAPL") == ["AAPL"]

    def test_iterable_is_stringified(self):
        assert as_symbol_list(["AAPL", "MSFT"]) == ["AAPL", "MSFT"]
        assert as_symbol_list([10107, 10108]) == ["10107", "10108"]


class TestPivotToPanel:
    def test_long_to_wide(self):
        long = pd.DataFrame(
            {
                "date": ["2020-01-02", "2020-01-02", "2020-01-03", "2020-01-03"],
                "sym": ["AAA", "BBB", "AAA", "BBB"],
                "px": [10.0, 20.0, 11.0, 19.0],
            }
        )
        panel = pivot_to_panel(long, "date", "sym", "px")
        assert list(panel.columns) == ["AAA", "BBB"]
        assert isinstance(panel.index, pd.DatetimeIndex)
        assert panel.index.name == "date"
        assert panel.loc["2020-01-03", "AAA"] == 11.0

    def test_missing_column_raises(self):
        df = pd.DataFrame({"date": [], "sym": []})
        with pytest.raises(KeyError):
            pivot_to_panel(df, "date", "sym", "px")


class TestFlattenYfinance:
    def test_multiindex_field_on_level0(self):
        cols = pd.MultiIndex.from_product([["Close", "Open"], ["AAPL", "MSFT"]])
        idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
        df = pd.DataFrame([[1, 2, 3, 4], [5, 6, 7, 8]], index=idx, columns=cols)
        panel = flatten_yfinance(df, field="Close")
        assert list(panel.columns) == ["AAPL", "MSFT"]
        assert panel.loc["2020-01-02", "AAPL"] == 1.0

    def test_single_level_columns(self):
        idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
        df = pd.DataFrame({"Close": [1.0, 2.0], "Open": [0.5, 1.5]}, index=idx)
        panel = flatten_yfinance(df, field="Close")
        assert list(panel.columns) == ["Close"]

    def test_missing_field_raises(self):
        cols = pd.MultiIndex.from_product([["Open"], ["AAPL"]])
        df = pd.DataFrame([[1]], index=pd.to_datetime(["2020-01-02"]), columns=cols)
        with pytest.raises(KeyError):
            flatten_yfinance(df, field="Close")

    def test_panel_is_sorted_and_float(self):
        idx = pd.to_datetime(["2020-01-03", "2020-01-02"])  # out of order
        df = pd.DataFrame({"Close": [2, 1]}, index=idx)
        panel = flatten_yfinance(df, field="Close")
        assert list(panel.index) == list(pd.to_datetime(["2020-01-02", "2020-01-03"]))
        assert panel["Close"].dtype == "float64"
