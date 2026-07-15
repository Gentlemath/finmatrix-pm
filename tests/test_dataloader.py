"""Tests for the data-loading layer.

These tests are network-free: they exercise the factory, the local CSV loader,
and the API-key validation paths, but never call remote providers.
"""

import pandas as pd
import pytest

from portfolio_management.dataloader import (
    AlphaVantageLoader,
    CSVDataLoader,
    FREDLoader,
    TushareLoader,
    YFinanceLoader,
    create_data_loader,
)


class TestFactory:
    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown data source"):
            create_data_loader("not_a_real_source")

    def test_source_name_is_case_insensitive_and_stripped(self, tmp_path):
        loader = create_data_loader("  CSV  ", data_dir=str(tmp_path))
        assert isinstance(loader, CSVDataLoader)

    def test_csv_dispatch(self, tmp_path):
        loader = create_data_loader("csv", data_dir=str(tmp_path))
        assert isinstance(loader, CSVDataLoader)

    def test_yfinance_dispatch(self):
        # Constructor only imports yfinance (installed); it makes no network call.
        loader = create_data_loader("yfinance")
        assert isinstance(loader, YFinanceLoader)


class TestCSVDataLoader:
    def test_init_creates_directory(self, tmp_path):
        target = tmp_path / "nested" / "data"
        CSVDataLoader(data_dir=str(target))
        assert target.exists()

    def test_save_load_roundtrip(self, tmp_path):
        loader = CSVDataLoader(data_dir=str(tmp_path))
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        loader.save_csv(df, "sample.csv")
        loaded = loader.load_csv("sample.csv")
        pd.testing.assert_frame_equal(loaded, df)

    def test_load_missing_file_raises(self, tmp_path):
        loader = CSVDataLoader(data_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            loader.load_csv("does_not_exist.csv")

    def test_list_csv_files(self, tmp_path):
        loader = CSVDataLoader(data_dir=str(tmp_path))
        loader.save_csv(pd.DataFrame({"x": [1]}), "one.csv")
        loader.save_csv(pd.DataFrame({"x": [2]}), "two.csv")
        files = loader.list_csv_files()
        assert isinstance(files, pd.Series)
        assert set(files) == {"one.csv", "two.csv"}


class TestApiKeyValidation:
    """Providers requiring credentials must fail clearly when none are supplied."""

    def test_alpha_vantage_requires_key(self, monkeypatch):
        monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ALPHAVANTAGE_API_KEY"):
            AlphaVantageLoader()

    def test_fred_requires_key(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with pytest.raises(ValueError, match="FRED_API_KEY"):
            FREDLoader()

    def test_tushare_requires_token(self, monkeypatch):
        monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
        # tushare import must succeed for the token check to be reached.
        pytest.importorskip("tushare")
        with pytest.raises(ValueError, match="TUSHARE_TOKEN"):
            TushareLoader()
