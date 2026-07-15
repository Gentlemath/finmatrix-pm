"""WRDS (Wharton Research Data Services) loader.

WRDS is a SQL/PostgreSQL data service, not a ticker-fetch API. This loader
speaks the modern CRSP **CIZ** format natively (CRSP froze the legacy SIZ stock
tables such as ``crsp.msf`` / ``crsp.dsf`` and moved ongoing data to the CIZ
tables ``crsp.msf_v2`` / ``crsp.dsf_v2`` / ``crsp.msp500list_v2``). CIZ carries
the full history and integrates the delisting return into ``mthret``/``dlyret``,
so there is no separate delisting join.

It exposes:

- CRSP stock data: ``get_crsp_monthly`` / ``get_crsp_daily`` (native CIZ columns).
- S&P 500 universe: ``get_sp500_constituents`` (point-in-time membership) and the
  one-call ``get_sp500_universe`` returning ready returns/membership/mktcap panels.
- ``get_prices`` (canonical total-return-index panel) and ``permnos_for_tickers``.
- Compustat (``get_compustat_annual`` / ``get_compustat_quarterly``) and the
  CRSP-Compustat link (``get_ccm_link``).
- Raw escape hatches (``raw_sql``, ``get_table``, ``list_libraries``,
  ``list_tables``, ``describe_table``) for any other library (IBES, TAQ, ...).

The CIZ monthly schema and S&P 500 membership were validated against a live
WRDS connection. The CIZ *daily* column names are by analogy (confirm with
``describe_table("crsp", "dsf_v2")``); table/column names are editable via the
``CIZ_*`` constants or the ``table=`` / ``cols=`` arguments.
"""

import os
from typing import Optional, Sequence, Union

import pandas as pd

from .base import BaseLoader, as_symbol_list


class WRDSLoader(BaseLoader):
    """Load CRSP (CIZ) / Compustat / other WRDS data over the ``wrds`` connection."""

    CIZ_MONTHLY_TABLE = "crsp.msf_v2"
    CIZ_DAILY_TABLE = "crsp.dsf_v2"
    CIZ_SP500_TABLE = "crsp.msp500list_v2"
    CIZ_MONTHLY_COLS = {
        "permno": "permno", "date": "mthcaldt", "ret": "mthret",
        "prc": "mthprc", "shrout": "shrout", "mktcap": "mthcap", "ticker": "ticker",
    }
    CIZ_DAILY_COLS = {
        "permno": "permno", "date": "dlycaldt", "ret": "dlyret",
        "prc": "dlyprc", "shrout": "shrout", "mktcap": "dlycap", "ticker": "ticker",
    }
    CIZ_SP500_COLS = {"permno": "permno", "start": "mbrstartdt", "ending": "mbrenddt"}

    def __init__(self, username: Optional[str] = None, connect: bool = True, **connect_kwargs):
        """Open a WRDS connection.

        Args:
            username: WRDS username. Falls back to the ``WRDS_USERNAME`` env var.
                The password is handled by the ``wrds`` package (interactive
                prompt or a ``~/.pgpass`` entry).
            connect: If False, do not open the connection immediately (useful
                for testing or deferred connection).
            connect_kwargs: Extra keyword arguments forwarded to
                ``wrds.Connection``.
        """
        try:
            import wrds
        except ImportError as exc:
            raise ImportError(
                "wrds is required for WRDSLoader. Install it with `pip install wrds`."
            ) from exc

        self._wrds = wrds
        self.username = username or os.environ.get("WRDS_USERNAME")
        if not self.username:
            raise ValueError(
                "WRDS requires WRDS_USERNAME in the environment or a username argument."
            )

        self.db = None
        if connect:
            self.connect(**connect_kwargs)

    # -- connection lifecycle -------------------------------------------------

    def connect(self, **connect_kwargs):
        """Open the underlying ``wrds.Connection`` if not already open."""
        if self.db is None:
            self.db = self._wrds.Connection(wrds_username=self.username, **connect_kwargs)
        return self.db

    def close(self) -> None:
        """Close the underlying connection."""
        if self.db is not None:
            self.db.close()
            self.db = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _require_db(self):
        if self.db is None:
            raise RuntimeError("WRDS connection is not open. Call connect() first.")
        return self.db

    # -- raw escape hatches (IBES, TAQ, anything else) ------------------------

    def raw_sql(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Run an arbitrary SQL query and return the result frame."""
        return self._require_db().raw_sql(sql, params=params)

    def get_table(
        self,
        library: str,
        table: str,
        columns: Optional[Sequence[str]] = None,
        obs: Optional[int] = None,
    ) -> pd.DataFrame:
        """Fetch a whole table (optionally limited columns / row count)."""
        kwargs = {}
        if columns is not None:
            kwargs["columns"] = list(columns)
        if obs is not None:
            kwargs["obs"] = obs
        return self._require_db().get_table(library=library, table=table, **kwargs)

    def list_libraries(self):
        """List WRDS libraries available to this account."""
        return self._require_db().list_libraries()

    def list_tables(self, library: str):
        """List tables within a WRDS library."""
        return self._require_db().list_tables(library=library)

    def describe_table(self, library: str, table: str) -> pd.DataFrame:
        """List a table's columns and types (to confirm a CIZ schema)."""
        sql = (
            "select column_name, data_type from information_schema.columns "
            "where table_schema = %(lib)s and table_name = %(tbl)s "
            "order by ordinal_position"
        )
        return self.raw_sql(sql, params={"lib": library, "tbl": table})

    # -- CRSP stock data (CIZ) ------------------------------------------------

    def get_crsp_monthly(
        self,
        permnos: Optional[Sequence[int]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        table: Optional[str] = None,
        cols: Optional[dict] = None,
    ) -> pd.DataFrame:
        """CIZ monthly stock file (``crsp.msf_v2``); returns native CIZ columns.

        ``mthret`` already includes the delisting return, so no adjustment is
        needed. A ``mthcap`` market-cap column is included for value weighting.
        """
        return self._ciz_stock(
            table or self.CIZ_MONTHLY_TABLE,
            {**self.CIZ_MONTHLY_COLS, **(cols or {})},
            permnos, start, end,
        )

    def get_crsp_daily(
        self,
        permnos: Optional[Sequence[int]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        table: Optional[str] = None,
        cols: Optional[dict] = None,
    ) -> pd.DataFrame:
        """CIZ daily stock file (``crsp.dsf_v2``); returns native CIZ columns."""
        return self._ciz_stock(
            table or self.CIZ_DAILY_TABLE,
            {**self.CIZ_DAILY_COLS, **(cols or {})},
            permnos, start, end,
        )

    def _ciz_stock(self, table, cols, permnos, start, end) -> pd.DataFrame:
        """Shared CIZ stock query; selects and returns the native column names."""
        wanted = [cols["permno"], cols["date"], cols["ret"], cols["prc"], cols["shrout"]]
        if cols.get("mktcap"):
            wanted.append(cols["mktcap"])

        params = {}
        where = []
        if permnos is not None:
            where.append(f"{cols['permno']} in %(permnos)s")
            params["permnos"] = tuple(int(p) for p in permnos)
        if start is not None:
            where.append(f"{cols['date']} >= %(start)s")
            params["start"] = start
        if end is not None:
            where.append(f"{cols['date']} <= %(end)s")
            params["end"] = end
        where_sql = ("where " + " and ".join(where)) if where else ""

        sql = (
            f"select {', '.join(wanted)} from {table} "
            f"{where_sql} order by {cols['permno']}, {cols['date']}"
        )
        return self._post_process_ciz(self.raw_sql(sql, params=params), cols)

    @staticmethod
    def _post_process_ciz(df: pd.DataFrame, cols: dict) -> pd.DataFrame:
        """Coerce the return to numeric; derive mktcap if the column is absent."""
        df = df.copy()
        if cols["ret"] in df.columns:
            df[cols["ret"]] = pd.to_numeric(df[cols["ret"]], errors="coerce")
        mktcap = cols.get("mktcap")
        if (not mktcap or mktcap not in df.columns) and {cols["prc"], cols["shrout"]}.issubset(
            df.columns
        ):
            df[mktcap or "mktcap"] = pd.to_numeric(df[cols["prc"]], errors="coerce").abs() * (
                pd.to_numeric(df[cols["shrout"]], errors="coerce")
            )
        return df

    def permnos_for_tickers(self, tickers: Sequence[str], table: Optional[str] = None) -> list:
        """Map tickers to permnos via the CIZ ticker column (distinct)."""
        table = table or self.CIZ_MONTHLY_TABLE
        tcol = self.CIZ_MONTHLY_COLS["ticker"]
        pcol = self.CIZ_MONTHLY_COLS["permno"]
        params = {"tickers": tuple(str(t).upper() for t in tickers)}
        sql = f"select distinct {pcol} from {table} where upper({tcol}) in %(tickers)s"
        result = self.raw_sql(sql, params=params)
        if result.empty:
            raise ValueError(f"No permno found for tickers: {list(tickers)}")
        return result[pcol].astype(int).tolist()

    # -- S&P 500 universe (CIZ) -----------------------------------------------

    def get_sp500_constituents(
        self,
        table: Optional[str] = None,
        cols: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Point-in-time S&P 500 membership from ``crsp.msp500list_v2``.

        Returns native CIZ columns (``permno``, ``mbrstartdt``, ``mbrenddt``).
        Survivorship-bias-free: it includes securities later removed or delisted.

        Note: ``msp500list_v2`` also carries ``indno``/``indfam`` columns. If you
        get more permnos than expected, the table may span several S&P indices --
        inspect ``raw_sql("select distinct indno, indfam from crsp.msp500list_v2")``
        and filter accordingly.
        """
        table = table or self.CIZ_SP500_TABLE
        c = {**self.CIZ_SP500_COLS, **(cols or {})}
        sql = (
            f"select {c['permno']}, {c['start']}, {c['ending']} "
            f"from {table} order by {c['permno']}, {c['start']}"
        )
        return self.raw_sql(sql)

    def get_sp500_universe(self, start: Optional[str] = None, end: Optional[str] = None):
        """One call -> aligned (returns, membership, market_caps) panels for the S&P 500.

        Pulls point-in-time membership and delisting-adjusted CIZ monthly returns,
        then builds the panels the strategy layer consumes. Drop straight into
        ``MomentumStrategy.backtest``.
        """
        from ..strategy.universe import panels_from_crsp

        constituents = self.get_sp500_constituents()
        permnos = constituents[self.CIZ_SP500_COLS["permno"]].astype(int).unique().tolist()
        monthly = self.get_crsp_monthly(permnos=permnos, start=start, end=end)

        c, s = self.CIZ_MONTHLY_COLS, self.CIZ_SP500_COLS
        return panels_from_crsp(
            monthly, constituents,
            date_col=c["date"], id_col=c["permno"], ret_col=c["ret"], mktcap_col=c["mktcap"],
            start_col=s["start"], end_col=s["ending"],
        )

    # -- canonical price panel (BaseLoader) -----------------------------------

    def get_prices(
        self,
        symbols: Union[str, Sequence[str]],
        start: Optional[str] = None,
        end: Optional[str] = None,
        by: str = "permno",
    ) -> pd.DataFrame:
        """Return a canonical price panel as a total-return index (base 100).

        Built from CIZ monthly total returns (``mthret``), so it is split- and
        dividend-adjusted by construction. Columns are permno labels.

        Args:
            symbols: Permno(s) or ticker(s), selected by ``by``.
            by: ``"permno"`` (default) or ``"ticker"``.
        """
        from .base import _finalize_panel

        symbols = as_symbol_list(symbols)
        if by == "ticker":
            permnos = self.permnos_for_tickers(symbols)
        elif by == "permno":
            permnos = [int(s) for s in symbols]
        else:
            raise ValueError("by must be 'permno' or 'ticker'.")

        c = self.CIZ_MONTHLY_COLS
        monthly = self.get_crsp_monthly(permnos=permnos, start=start, end=end)
        wide = monthly.pivot_table(
            index=c["date"], columns=c["permno"], values=c["ret"], aggfunc="last"
        )
        returns = _finalize_panel(wide)
        return 100.0 * (1.0 + returns.fillna(0.0)).cumprod()

    # -- Compustat ------------------------------------------------------------

    def get_compustat_annual(
        self,
        gvkeys: Optional[Sequence[str]] = None,
        tickers: Optional[Sequence[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        items: Sequence[str] = ("gvkey", "datadate", "tic", "conm", "at", "lt", "sale", "ni"),
    ) -> pd.DataFrame:
        """Query Compustat annual fundamentals (``comp.funda``).

        Applies the standard filters indfmt='INDL', datafmt='STD', popsrc='D',
        consol='C' to avoid duplicate rows.
        """
        return self._compustat("funda", gvkeys, tickers, start, end, items)

    def get_compustat_quarterly(
        self,
        gvkeys: Optional[Sequence[str]] = None,
        tickers: Optional[Sequence[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        items: Sequence[str] = ("gvkey", "datadate", "tic", "conm", "atq", "ltq", "saleq", "niq"),
    ) -> pd.DataFrame:
        """Query Compustat quarterly fundamentals (``comp.fundq``)."""
        return self._compustat("fundq", gvkeys, tickers, start, end, items)

    def _compustat(self, table, gvkeys, tickers, start, end, items):
        params = {}
        select_cols = ", ".join(items)
        where = ["indfmt='INDL'", "datafmt='STD'", "popsrc='D'", "consol='C'"]

        if gvkeys is not None:
            where.append("gvkey in %(gvkeys)s")
            params["gvkeys"] = tuple(str(g) for g in gvkeys)
        elif tickers is not None:
            where.append("upper(tic) in %(tickers)s")
            params["tickers"] = tuple(str(t).upper() for t in tickers)

        if start is not None:
            where.append("datadate >= %(start)s")
            params["start"] = start
        if end is not None:
            where.append("datadate <= %(end)s")
            params["end"] = end

        sql = (
            f"select {select_cols} from comp.{table} "
            f"where {' and '.join(where)} order by gvkey, datadate"
        )
        return self.raw_sql(sql, params=params)

    # -- CRSP-Compustat Merged link -------------------------------------------

    def get_ccm_link(self, gvkeys: Optional[Sequence[str]] = None) -> pd.DataFrame:
        """Return the CCM link history (``crsp.ccmxpf_lnkhist``).

        Filtered to the standard primary links (linktype in LU/LC, linkprim in
        P/C). Use it to join Compustat ``gvkey`` to CRSP ``permno``.
        """
        params = {}
        where = ["linktype in ('LU', 'LC')", "linkprim in ('P', 'C')"]
        if gvkeys is not None:
            where.append("gvkey in %(gvkeys)s")
            params["gvkeys"] = tuple(str(g) for g in gvkeys)
        sql = (
            "select gvkey, lpermno as permno, linktype, linkprim, linkdt, linkenddt "
            f"from crsp.ccmxpf_lnkhist where {' and '.join(where)} order by gvkey, linkdt"
        )
        return self.raw_sql(sql, params=params)
