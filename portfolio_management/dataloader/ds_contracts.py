"""Build continuous futures series from CONTRACT-level Datastream data.

Companion to ``ds_futures``, which reads Datastream's own pre-built continuous
series. Two things force this module to exist.

**1. The continuous-series tables no longer carry CME Group.** Withdrawal is
staggered by exchange -- COMEX 2022-11, CBOT 2025-04, NYMEX 2026-04 -- and the
live classes have no continuous series at all. The CONTRACT tables still hold
every one of those markets with settlements, volume and open interest, and with
far more history than the derived series ever had: COMEX silver from 1973-01
against the CS00 series' 2004-10, CBOT 30-year from 1977-08 against 1998-10.

**2. A continuous series cannot express the roll-day return.** It prints the old
contract on one day and the new one on the next, so their ratio is not the
return on any position -- ``ds_futures.mask_roll_returns`` has to discard that
day. Holding contracts directly removes the problem instead of masking it::

    the contract to hold over (t-1, t) is chosen at t-1, and the return is that
    ONE contract's own settlement at t over its own settlement at t-1

Every day is then a real return on a real position, roll days included.

MEASURED FACTS worth keeping in view, all from ``tools/build_contract_series``:

* The roll rule matters far more than which contract is traded. Same index,
  same construction, different contract size (full-size vs E-mini S&P): monthly
  correlation 0.9983. Same index, same class, same contracts, different
  construction (ours vs Datastream's CS00): 0.9796. Construction costs about
  twelve times what contract choice does.
* The roll gap a continuous series shows -- what masking discards -- runs
  +0.99%/roll on gold and -0.52% on the 10-year note, i.e. +5.0% and -2.1% a
  year of pure term structure. Sign follows the curve: storage costs put metals
  in contango, the yield curve puts bonds the other way.
* Mean-return differences against the CS00 series look large on high-volatility
  markets (+2.6%/yr on palladium) but sit inside sampling error (t = 1.96).
  A residual whose volatility scales with the asset's makes the difference
  scale too; that is the signature of noise. Coverage and volatility are what
  this construction pins down, not the level of long-run return.
* A nearest-expiry rule is unusable on metals and softs. Gold lists a contract
  every month but trades only Feb/Apr/Jun/Aug/Dec, and the serial months settle
  on derived rather than traded prices: nearest-expiry held a contract ranked
  11th by open interest, holding 0.3% of it, on 83% of days.
"""

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from .ds_futures import clean_prices

SCHEMA = "tr_ds_fut"

# Defaults established empirically; see pick_held for what each one prevents.
ROLL_RULE = "oi"
BUFFER_DAYS = 5
WINDOW_MONTHS = 6

# clscode -> (asset_class, label, CS00 series to validate against or None).
# Labels ending _NYM / _ICE / _FULL / _EMINI are SPLICE COMPONENTS, not final
# markets -- see SPLICES.
CONTRACT_MARKETS: Dict[int, tuple] = {
    # US rates. Live classes with no continuous series; the basket's CZ* entries
    # are the ECBOT siblings and stop 2025-04.
    2441: ("bond", "US30Y", "CZBCS00"),
    3896: ("bond", "US10Y", "CZNCS00"),
    1997: ("bond", "US5Y", "CZFCS00"),
    2523: ("bond", "US2Y", "CZTCS00"),
    # Precious metals. COMEX withdrawal killed the CS00 series in 2022-11.
    1508: ("metal", "GOLD", "CZGCS00"),
    1574: ("metal", "SILVER", "CZICS00"),
    1549: ("metal", "PLATINUM", "NPLCS00"),
    # US equity. The basket has no US index at all; ISPCS00 dies 2021-09 and the
    # E-mini has no continuous series, so the two are built and spliced.
    3725: ("equity", "SP500_FULL", "ISPCS00"),
    1035: ("equity", "SP500_EMINI", "ISPCS00"),
    # CME FX majors, three of them from 1973-01. The rebuild plan called these
    # impossible because no live continuous series exists.
    2125: ("fx", "JPYUSD", "IJYCS00"),
    2094: ("fx", "CHFUSD", "ISFCS00"),
    2072: ("fx", "CADUSD", "ICDCS00"),
    2059: ("fx", "GBPUSD", "IBPCS00"),
    2047: ("fx", "AUDUSD", "IADCS00"),
    1999: ("fx", "EURUSD", "CUCCS00"),
    # The world's most liquid grains, absent only because the continuous-series
    # route cannot see CME. They sit in the "COMPOSITE" naming family, and the
    # live soybean-oil class uses the British spelling "SOYABEAN OIL COMP." --
    # a search for SOYBEAN misses it entirely.
    2442: ("ag", "WHEAT_CBOT", "CZWCS00"),
    2420: ("ag", "CORN_CBOT", "CZCCS00"),
    2522: ("ag", "SOYBEAN_CBOT", "CZSCS00"),
    3968: ("ag", "SOYOIL_CBOT", "CZLCS00"),
    1487: ("ag", "COTTON", "NCTCS00"),
    # Livestock: an asset class the basket has none of, driven by breeding
    # cycles rather than by rates, energy or grain.
    1996: ("livestock", "LIVECATTLE", "CLDCS00"),
    3893: ("livestock", "LEANHOGS", "CLGCS00"),
    # NYMEX energy: 23 more years of WTI than the ICE series the basket uses,
    # and heating oil back to 1978.
    1482: ("energy", "WTI_NYM", "LTCCS00"),
    1514: ("energy", "HEATOIL_NYM", "NHOCS00"),
    3750: ("energy", "HEATOIL_ICE", "LHOCS00"),
    1159: ("energy", "GASOLINE", "LHUCS00"),
}

# Markets assembled from more than one series. FIRST component that has a value
# on a date wins, so order is preference, not chronology.
#
#   SP500    -- the E-mini is the liquid contract and runs to 2026-03; the
#               full-size one only fills 1982-04..1997-08.
#   HEATOIL  -- NYMEX is the liquid contract throughout; ICE only fills the
#               months after the NYMEX feed stops.
#   WTI      -- likewise. Note this one mixes constructions: WTI_ICE is a
#               Datastream continuous series, so those months carry the other
#               roll treatment. It covers 4 months of 522, which is why it is
#               tolerated rather than fixed.
SPLICES: Dict[str, tuple] = {
    "SP500": ("equity", ["SP500_EMINI", "SP500_FULL"]),
    "HEATOIL": ("energy", ["HEATOIL_NYM", "HEATOIL_ICE"]),
    "WTI": ("energy", ["WTI_NYM", "WTI_ICE"]),
}

# Markets kept on Datastream's own continuous series: no live CME class to
# rebuild from, or an exchange that never withdrew. WTI_ICE is a splice
# component rather than a market of its own.
CONTINUOUS_MARKETS: Dict[str, tuple] = {
    "LSXCS00": ("equity", "FTSE100"),
    "HSICS00": ("equity", "HANGSENG"),
    "ONACS00": ("equity", "NIKKEI225"),
    "GDXCS00": ("equity", "DAX"),
    "KKXCS00": ("equity", "KOSPI200"),
    "GEXCS00": ("equity", "ESTOXX50"),
    "AAPCS03": ("equity", "SPI200"),
    "LIGCS00": ("bond", "GILT"),
    "ATYCS03": ("bond", "AUS3Y"),
    "GBECS00": ("bond", "BOBL"),
    "GGECS00": ("bond", "BUND"),
    "GEBCS00": ("bond", "SCHATZ"),
    # Tokyo, not the Singapore offshore listing. The basket held SJGCS00 --
    # "SGX DT-10YR JGB CONTINUOUS" -- from v1 onward: 27,573 contract-days, of
    # which 26 carry any volume at all and the largest is 80 contracts. It
    # supplied 27,568 settlement prices and a plausible return series with
    # essentially no trading behind it. JGBCS00 is the actual Japanese
    # government bond future: 49,242 of 58,804 contract-days trade, peaking at
    # 151,075 contracts, and it starts 1986-12 rather than 2005-02.
    #
    # Nothing in this project's diagnostics could have caught that. Liquidity
    # was always measured RELATIVE to a market's own open interest, which a
    # market nobody trades can satisfy perfectly. Only absolute volume exposes
    # it, and continuous-series markets had no contract-level check at all.
    "JGBCS00": ("bond", "JGB10Y"),
    "AGDCS00": ("bond", "AUS10Y"),
    "CDGCS00": ("bond", "CAN10Y"),
    "LLCCS00": ("energy", "BRENT"),
    "NNGCS01": ("energy", "NATGAS"),
    "LNGCS00": ("energy", "NATGAS_UK"),
    "LTCCS00": ("energy", "WTI_ICE"),
    "LAHCS00": ("metal", "ALUMINIUM"),
    "LCPCS00": ("metal", "COPPER"),
    "LNICS00": ("metal", "NICKEL"),
    "LZZCS00": ("metal", "ZINC"),
    "NCCCS00": ("ag", "COCOA"),
    "NKCCS00": ("ag", "COFFEE"),
    "NSBCS00": ("ag", "SUGAR"),
    "PMWCS00": ("ag", "WHEAT_MAT"),
}

# Dropped from the previous 35-market basket, with the reason, so that the
# decision is recoverable rather than inferred from an absence.
DROPPED: Dict[str, str] = {
    "clscode 1542": "PALLADIUM -- 4,043 contracts a day against platinum's "
                    "19,672 on the same exchange with comparable contract sizes "
                    "(100 vs 50 troy oz), roughly $600m/day notional and the "
                    "thinnest market in the basket. Dropped on LIQUIDITY. It is "
                    "also the weakest addition since 2012 (-0.27 with platinum), "
                    "and that must not be read as the reason: screening on "
                    "outcome is the bias that makes the older basket's recent "
                    "Sharpe untrustworthy. Platinum, five times as liquid and in "
                    "line with the other metals, is kept -- including its share "
                    "of that -0.27.",
    "NJOCS00": "ORANGEJUICE -- among the thinnest listed futures anywhere",
    "LWHCS00": "WHEAT_LIF -- thin; CBOT wheat covers the exposure",
    "PCOCS00": "CORN_MAT -- thin, and redundant with CBOT corn",
    "NDXCS00": "USDINDEX -- a weighted basket of the six FX majors now held",
    "NSYCS00": "GBPJPY -- thin cross, and spanned by the GBP and JPY legs",
    "CZBCS00": "US30Y -- rebuilt from clscode 2441",
    "CZNCS00": "US10Y -- rebuilt from clscode 3896",
    "CZFCS00": "US5Y -- rebuilt from clscode 1997",
    "CZTCS00": "US2Y -- rebuilt from clscode 2523",
    "CZGCS00": "GOLD -- rebuilt from clscode 1508",
    "CZICS00": "SILVER -- rebuilt from clscode 1574",
}


def final_markets() -> Dict[str, str]:
    """label -> asset_class for the basket this module assembles."""
    out = {lab: cls for cls, lab, _ in CONTRACT_MARKETS.values()}
    out.update({lab: cls for cls, lab in CONTINUOUS_MARKETS.values()})
    for name, (cls, parts) in SPLICES.items():
        for part in parts:
            out.pop(part, None)
        out[name] = cls
    return out


def fetch_contracts(loader, clscode: int) -> pd.DataFrame:
    """Every contract in a class, with its listing and last-trade dates."""
    df = loader.raw_sql(f"""
        select futcode, dsmnem, contrname, isocurrcode, startdate, lasttrddate
        from {SCHEMA}.wrds_contract_info
        where clscode = %(c)s
    """, params={"c": int(clscode)})
    if df.empty:
        return df
    for c in ("startdate", "lasttrddate"):
        df[c] = pd.to_datetime(df[c])
    return df.reset_index(drop=True)


def fill_missing_expiry(info: pd.DataFrame,
                        px: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Give contracts with no ``lasttrddate`` one, from their last priced day.

    Older contracts in some classes carry prices but no last-trade date, and
    dropping them silently truncates the market: CBOT wheat lost 1974-01..
    2006-12 (161 contracts, 53,654 contract-days) and lean hogs 1973-11..
    2002-02, each surfacing only as a series that started thirty years late.

    An expired contract's last priced day IS its last trading day, so the
    substitution is sound rather than a guess -- and it is CHECKED rather than
    assumed: for contracts that do carry a lasttrddate, the gap between it and
    the last priced day is measured and reported as ``expiry_proxy_median_d``.
    A median near zero is the evidence that the filled dates are right.

    Using an observed date as an expiry is not look-ahead. A contract's delivery
    month is a contractual fact known at listing; the price record merely
    recovers it. The one failure mode is a contract whose data stops before it
    really expires, which makes the rule roll away early -- conservative, not
    optimistic.
    """
    last_px = px.groupby("futcode")["date"].max()
    info = info.copy()
    known = info["lasttrddate"].notna() & info["futcode"].isin(last_px.index)
    gap = (info.loc[known, "lasttrddate"]
           - info.loc[known, "futcode"].map(last_px)).dt.days
    miss = info["lasttrddate"].isna()
    info.loc[miss, "lasttrddate"] = info.loc[miss, "futcode"].map(last_px)
    stats = {
        "expiry_filled": int(miss.sum()),
        "expiry_unusable": int(info["lasttrddate"].isna().sum()),
        "expiry_proxy_median_d": (float(gap.median()) if len(gap) else None),
        "expiry_proxy_p95_d": (float(gap.abs().quantile(0.95))
                               if len(gap) else None),
    }
    return info.dropna(subset=["lasttrddate"]).reset_index(drop=True), stats


def fetch_contract_prices(loader, futcodes: Iterable) -> pd.DataFrame:
    """Daily settlement, open interest and volume for the given contracts."""
    df = loader.raw_sql(f"""
        select futcode, date_, settlement, openinterest, volume
        from {SCHEMA}.wrds_fut_contract
        where futcode in %(f)s and settlement is not null
    """, params={"f": tuple(int(f) for f in futcodes)})
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date_"])
    for c in ("settlement", "openinterest", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df[df["settlement"] > 0].drop(columns=["date_"])


def clean_contract_prices(px: pd.DataFrame,
                          verbose: bool = False) -> Tuple[pd.DataFrame, int, int]:
    """Apply ``ds_futures.clean_prices`` to each contract separately.

    The continuous-series path has always cleaned; this one did not, and the
    omission is not cosmetic. ICE RBOB gasoline prints a settlement roughly
    10,000x too large on three days -- 2007-10-17, 2008-08-25, 2008-09-26 --
    each immediately reversing. The next day's return is then -100%, which drives
    that MONTH's compounded return to -1.0 and the market's annualised volatility
    to 8,000%. Nothing downstream can recover from a -100% month.

    Cleaning per CONTRACT rather than on the assembled series is what makes the
    repair correct: a glitch belongs to one contract's price record, and dropping
    the price (not the return) lets the next return span the gap.

    An earlier reading of this gap dismissed it on the grounds that a reversing
    spike cancels when compounded within a month. That holds only while the
    spike is mild; a 10,000x spike does not cancel, it annihilates.
    """
    kept, n_zero, n_spike = [], 0, 0
    for fc, g in px.groupby("futcode", sort=False):
        f = g.set_index("date").sort_index()
        f["px"] = f["settlement"]
        cleaned, nz, ns = clean_prices(f, label=str(fc), verbose=verbose)
        n_zero += nz
        n_spike += ns
        kept.append(g[g["date"].isin(cleaned.index)] if (nz or ns) else g)
    return pd.concat(kept, ignore_index=True), n_zero, n_spike


def pick_held(px: pd.DataFrame, expiry: pd.Series, rule: str = ROLL_RULE,
              buffer_days: int = BUFFER_DAYS,
              window_months: int = WINDOW_MONTHS) -> pd.Series:
    """date -> futcode to hold, decided using only that date's information.

    Three constraints, each fixing a failure the diagnostics exposed:

    ``buffer_days`` drops contracts about to stop trading, whose settlements
    thin out as delivery approaches.

    ``window_months`` limits the choice to contracts expiring within that many
    months. Without it a rule free to pick ANY live contract occasionally takes
    a deep-deferred one -- gold's far December carries real open interest from
    financing trades -- and the no-backward constraint then pins the position
    there. Measured on gold: 13 runs over 4.5 months, one of 43.

    No backward roll: once a contract is left it is not re-entered, so a thin
    day in the new front month cannot bounce the position back and forth.

    Open interest is lagged a day because exchanges publish it the morning
    after the session.
    """
    settle = px.pivot_table(index="date", columns="futcode", values="settlement")
    oi = px.pivot_table(index="date", columns="futcode",
                        values="openinterest").reindex_like(settle).shift(1)
    exp = expiry.reindex(settle.columns)
    held: Dict[pd.Timestamp, object] = {}
    current = None
    for dt in settle.index:
        row = settle.loc[dt]
        live = row.index[row.notna()
                         & (exp > dt + pd.Timedelta(days=buffer_days))]
        if len(live) == 0:
            continue
        near = live[exp[live] <= dt + pd.DateOffset(months=window_months)]
        if len(near):
            live = near
        if current is not None and current in live:
            live = live[exp[live] >= exp[current]]
        if rule == "oi":
            o = oi.loc[dt, live]
            pick = o.idxmax() if o.notna().any() else exp[live].idxmin()
        else:
            pick = exp[live].idxmin()
        current = pick
        held[dt] = pick
    return pd.Series(held, name="futcode")


def contract_returns(px: pd.DataFrame, held: pd.Series) -> dict:
    """Daily returns of the held contract, plus roll diagnostics.

    ``roll_true`` is the return this construction earns on a roll day.
    ``roll_gap`` is what a continuous series prints on the same day -- the new
    contract's price over the OLD contract's -- which is the figure masking has
    to throw away. Their difference is the calendar spread, so the two can be
    cross-checked against the shape of the curve.
    """
    settle = px.pivot_table(index="date", columns="futcode",
                            values="settlement").reindex(held.index)
    prev_choice = held.shift(1)
    rets, roll_true, roll_gap, dates = [], [], [], []
    for i in range(1, len(held)):
        d, d0 = held.index[i], held.index[i - 1]
        c = prev_choice.iloc[i]
        if c is None or (isinstance(c, float) and not np.isfinite(c)):
            continue
        p1, p0 = settle.at[d, c], settle.at[d0, c]
        if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0):
            continue
        r = p1 / p0 - 1.0
        rets.append(r)
        dates.append(d)
        if held.iloc[i] != c:
            roll_true.append(r)
            pn = settle.at[d, held.iloc[i]]
            if np.isfinite(pn):
                roll_gap.append(pn / p0 - 1.0)
    daily = pd.Series(rets, index=pd.DatetimeIndex(dates), name="r")

    runs = []
    if len(held):
        start, cur = held.index[0], held.iloc[0]
        for dt, c in held.items():
            if c != cur:
                runs.append((start, cur, (dt - start).days / 30.44))
                start, cur = dt, c
        runs.append((start, cur, (held.index[-1] - start).days / 30.44))
    return {"daily": daily, "n_rolls": len(roll_true), "runs": runs,
            "roll_true": np.array(roll_true), "roll_gap": np.array(roll_gap)}


def liquidity_of_held(px: pd.DataFrame, held: pd.Series) -> dict:
    """Was the contract we held actually the liquid one that day?

    Decisive for choosing a roll rule, and the only per-market liquidity
    evidence available anywhere in this codebase. A real front month ranks 1st
    by open interest and holds a large share of it; a serial month that barely
    trades ranks far down and holds almost none.
    """
    oi = px.pivot_table(index="date", columns="futcode",
                        values="openinterest").reindex(held.index)
    share, rank = [], []
    for dt, c in held.items():
        row = oi.loc[dt].dropna()
        if c not in row.index or row.sum() <= 0:
            continue
        share.append(float(row[c] / row.sum()))
        rank.append(int((row > row[c]).sum()) + 1)
    if not share:
        return {}
    share, rank = np.array(share), np.array(rank)
    return {"n": len(share), "share_med": float(np.median(share)),
            "rank_med": float(np.median(rank)),
            "pct_rank1": float((rank == 1).mean()),
            "pct_share_lt5": float((share < 0.05).mean())}


def build_market(loader, clscode: int, rule: str = ROLL_RULE,
                 buffer_days: int = BUFFER_DAYS,
                 window_months: int = WINDOW_MONTHS) -> Tuple[pd.Series, dict]:
    """Fetch one class and return ``(daily returns, diagnostics)``."""
    info = fetch_contracts(loader, clscode)
    if info.empty:
        return pd.Series(dtype="float64"), {"error": "no contracts"}
    px = fetch_contract_prices(loader, info["futcode"])
    if px.empty:
        return pd.Series(dtype="float64"), {"error": "no settlements"}
    px, n_zero, n_spike = clean_contract_prices(px)
    if px.empty:
        return pd.Series(dtype="float64"), {"error": "no prices after cleaning"}
    info, expiry_stats = fill_missing_expiry(info, px)
    if info.empty:
        return pd.Series(dtype="float64"), {"error": "no usable expiry dates"}
    px = px[px["futcode"].isin(set(info["futcode"]))]
    held = pick_held(px, info.set_index("futcode")["lasttrddate"], rule,
                     buffer_days, window_months)
    if held.empty:
        return pd.Series(dtype="float64"), {"error": "nothing holdable"}
    out = contract_returns(px, held)
    diag = {k: v for k, v in out.items() if k != "daily"}
    diag.update(liquidity_of_held(px, held))
    diag["n_contracts"] = int(len(info))
    diag["n_contract_days"] = int(len(px))
    diag["ccy"] = ",".join(sorted(set(info["isocurrcode"].dropna().astype(str))))
    diag["oi_present"] = float(px["openinterest"].notna().mean())
    diag.update(expiry_stats)
    diag["bad_zero"] = int(n_zero)
    diag["bad_spike"] = int(n_spike)
    return out["daily"], diag


def splice_returns(parts: Dict[str, pd.Series],
                   order: List[str]) -> Optional[pd.Series]:
    """Join component return series; the FIRST listed component wins a date.

    Order is preference, not chronology: the liquid contract is listed first and
    the others only fill dates it does not cover.
    """
    have = [p for p in order if p in parts and not parts[p].empty]
    if not have:
        return None
    out = parts[have[0]].copy()
    for p in have[1:]:
        out = out.combine_first(parts[p])
    return out.sort_index()
