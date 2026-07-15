"""Tests for WRDSLoader (CIZ-native) using a mocked ``wrds`` package.

There is no live WRDS connection here, so a fake ``wrds`` module is injected
into ``sys.modules``. Its fake connection returns canned CIZ-shaped frames keyed
by the SQL text, which lets us verify query construction, dispatch, and panel
building without a database.
"""

import sys
import types

import pandas as pd
import pytest

from portfolio_management.dataloader import WRDSLoader, create_data_loader


class FakeConnection:
    """Stand-in for wrds.Connection; returns canned CIZ frames and records SQL."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.queries = []
        self.closed = False

    def raw_sql(self, sql, params=None):
        self.queries.append((sql, params))
        s = sql.lower()
        if "information_schema" in s:
            return pd.DataFrame(
                {"column_name": ["permno", "mthcaldt", "mthret", "mthprc", "mthcap", "shrout"],
                 "data_type": ["integer", "date", "numeric", "numeric", "numeric", "integer"]}
            )
        if "distinct" in s and "ticker" in s:            # permnos_for_tickers
            return pd.DataFrame({"permno": [14593]})
        if "crsp.msf_v2" in s:
            return pd.DataFrame(
                {
                    "permno": [14593, 14593, 14593],
                    "mthcaldt": pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"]),
                    "mthret": [0.05, -0.02, 0.03],
                    "mthprc": [100.0, 98.0, 101.0],
                    "shrout": [1000, 1000, 1000],
                    "mthcap": [100000.0, 98000.0, 101000.0],
                }
            )
        if "crsp.dsf_v2" in s:
            return pd.DataFrame(
                {
                    "permno": [14593],
                    "dlycaldt": pd.to_datetime(["2025-01-02"]),
                    "dlyret": [0.01], "dlyprc": [100.0], "shrout": [1000], "dlycap": [100000.0],
                }
            )
        if "crsp.msp500list_v2" in s:
            return pd.DataFrame(
                {"permno": [14593, 10107],
                 "mbrstartdt": ["2015-01-01", "2010-01-01"],
                 "mbrenddt": [None, None]}
            )
        if "from comp.funda" in s:
            return pd.DataFrame({"gvkey": ["001690"], "datadate": ["2020-12-31"], "at": [1.0]})
        if "from crsp.ccmxpf_lnkhist" in s:
            return pd.DataFrame({"gvkey": ["001690"], "permno": [14593]})
        return pd.DataFrame()

    def get_table(self, library, table, **kwargs):
        self.queries.append((f"get_table:{library}.{table}", kwargs))
        return pd.DataFrame({"col": [1]})

    def list_libraries(self):
        return ["crsp", "comp"]

    def list_tables(self, library):
        return ["msf_v2", "dsf_v2", "msp500list_v2"]

    def close(self):
        self.closed = True


@pytest.fixture
def fake_wrds(monkeypatch):
    """Inject a fake ``wrds`` module and provide a username."""
    module = types.ModuleType("wrds")
    module.Connection = FakeConnection
    monkeypatch.setitem(sys.modules, "wrds", module)
    monkeypatch.setenv("WRDS_USERNAME", "tester")
    return module


class TestConstruction:
    def test_requires_username(self, monkeypatch):
        module = types.ModuleType("wrds")
        module.Connection = FakeConnection
        monkeypatch.setitem(sys.modules, "wrds", module)
        monkeypatch.delenv("WRDS_USERNAME", raising=False)
        with pytest.raises(ValueError, match="WRDS_USERNAME"):
            WRDSLoader(connect=False)

    def test_username_from_env(self, fake_wrds):
        loader = WRDSLoader(connect=False)
        assert loader.username == "tester"
        assert loader.db is None

    def test_connect_opens_connection(self, fake_wrds):
        assert isinstance(WRDSLoader(connect=True).db, FakeConnection)

    def test_factory_dispatch(self, fake_wrds):
        assert isinstance(create_data_loader("wrds", connect=False), WRDSLoader)

    def test_context_manager_closes(self, fake_wrds):
        with WRDSLoader(connect=True) as loader:
            conn = loader.db
        assert conn.closed is True
        assert loader.db is None


class TestCRSPCiz:
    def test_monthly_native_columns(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        df = loader.get_crsp_monthly(permnos=[14593], start="2025-01-01", end="2025-12-31")
        assert {"permno", "mthcaldt", "mthret", "mthprc", "mthcap", "shrout"}.issubset(df.columns)
        sql, params = loader.db.queries[-1]
        assert "crsp.msf_v2" in sql
        assert " as " not in sql            # native columns, no SIZ aliasing
        assert params["permnos"] == (14593,)

    def test_daily_uses_dsf_v2(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        loader.get_crsp_daily(permnos=[14593])
        assert "crsp.dsf_v2" in loader.db.queries[-1][0]

    def test_cols_override(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        loader.get_crsp_monthly(permnos=[14593], cols={"ret": "mthretx"})
        assert "mthretx" in loader.db.queries[-1][0]

    def test_permnos_for_tickers(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        assert loader.permnos_for_tickers(["AAPL"]) == [14593]
        assert "crsp.msf_v2" in loader.db.queries[-1][0]


class TestSP500:
    def test_constituents_native_columns(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        df = loader.get_sp500_constituents()
        assert {"permno", "mbrstartdt", "mbrenddt"}.issubset(df.columns)
        assert "crsp.msp500list_v2" in loader.db.queries[-1][0]

    def test_universe_returns_panels(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        returns, membership, caps = loader.get_sp500_universe(start="2025-01-01")
        assert "14593" in returns.columns
        assert isinstance(membership, pd.DataFrame)
        assert bool(membership["14593"].any())
        assert caps is not None


class TestGetPrices:
    def test_total_return_index(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        panel = loader.get_prices([14593], start="2025-01-01", by="permno")
        assert list(panel.columns) == ["14593"]
        assert isinstance(panel.index, pd.DatetimeIndex)
        # base 100 * (1 + 0.05) = 105 on the first month
        assert panel["14593"].iloc[0] == pytest.approx(105.0)

    def test_invalid_by_raises(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        with pytest.raises(ValueError, match="permno.*ticker"):
            loader.get_prices([14593], by="cusip")


class TestCompustat:
    def test_annual_applies_standard_filters(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        loader.get_compustat_annual(tickers=["AAPL"])
        sql, params = loader.db.queries[-1]
        assert "from comp.funda" in sql
        assert "indfmt='INDL'" in sql
        assert params["tickers"] == ("AAPL",)


class TestCCM:
    def test_link_filters(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        loader.get_ccm_link(gvkeys=["001690"])
        sql, _ = loader.db.queries[-1]
        assert "crsp.ccmxpf_lnkhist" in sql
        assert "linktype in ('LU', 'LC')" in sql


class TestRawEscapeHatches:
    def test_describe_table(self, fake_wrds):
        out = WRDSLoader(connect=True).describe_table("crsp", "msf_v2")
        assert "mthret" in list(out["column_name"])

    def test_raw_sql_passthrough(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        loader.raw_sql("select 1 from ibes.detail")
        assert loader.db.queries[-1][0] == "select 1 from ibes.detail"

    def test_get_table(self, fake_wrds):
        assert not WRDSLoader(connect=True).get_table("ibes", "detu_epsus", obs=10).empty

    def test_list_helpers(self, fake_wrds):
        loader = WRDSLoader(connect=True)
        assert "crsp" in loader.list_libraries()
        assert "msf_v2" in loader.list_tables("crsp")

    def test_raw_sql_requires_open_connection(self, fake_wrds):
        with pytest.raises(RuntimeError, match="not open"):
            WRDSLoader(connect=False).raw_sql("select 1")
