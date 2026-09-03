"""Datastream futures (WRDS ``tr_ds_fut``): the cross-asset continuous-series basket.

This is library knowledge, not example knowledge. Every fact below was learned by
measuring the tables, and each one silently corrupts the data if ignored — so it
lives here, next to the code that acts on it, rather than in a script.

**1. ``wrds_fut_series`` is STACKED LONG (a SAS transpose).** Every date appears
~5 times, distinguished by ``_name_``: ``Value_``, ``Item``, ``Table_``,
``DataTypeCode``, ``CodeNum``. Only ``_name_ = 'Value_'`` carries the series; the
rest are metadata. Without that filter you get 5x duplicate dates and any
``diff()``-based logic is meaningless.

A consequence worth stating plainly: ``cmonth`` and ``life`` are NOT semantic
columns. They are generic value slots whose meaning depends on ``_name_``. On the
``Value_`` row the ``cmonth`` slot holds YYYYMM (the contract month) and ``life``
holds calendar days to the contract's last trading day — verified on the Bund,
where every date plus ``life`` lands exactly on 2016-03-08, the Eurex FGBL March
2016 last trading day. On the ``Item`` row the same slots hold 25 and 26, the
Datastream item numbers of those two quantities. ``life`` and ``volume`` are
simply unpopulated for many ``calcseriescode`` values, so neither can be relied
on. Because the slot is generic, a series whose Datastream item is not the
contract month would silently break roll detection — hence
:func:`looks_like_yyyymm`.

**2. Datastream does NOT back-adjust, and the bias is DIRECTIONAL.** ``cmonth``
changes at each roll and the settlement price jumps across the switch. Measured
on GGECS00 (Bund, CS00) over 2015-2016, eight rolls:

===========================  ========
mean |return| on roll days     0.960%
mean |return| on normal days   0.264%
ratio                             3.6x
mean SIGNED return on rolls   -0.545%
===========================  ========

The signed figure is the important one: six of eight rolls were negative, so on a
quarterly cycle the series carries a ~-2.2%/year drift that would push the Bund's
12-month trend signal systematically toward SHORT. The price fall is not a loss —
rolling a long position sells the old contract and buys the cheaper new one, so
wealth is unchanged. The series drops; the portfolio does not.

The gap is confined to the roll day (the following day averages 0.402% against
0.264% normal), so masking that single return suffices. Cost ~4 observations a
year; benefit, no fake quarterly signal.

Roll timing under CS00, verified rather than assumed: all eight rolls fall on the
first trading day of the delivery month, with 7-10 days still on the old
contract. Open interest confirms liquidity had not yet moved (1.43M contracts
still open on the front with 7 days to go), so a late roll is normal for the Bund
rather than a data defect.

**3. ``dsmnem`` is not unique, and roll variants differ hugely in coverage.**
CZNCS01 (US 10Y T-Note, roll 1) holds 1,401 rows starting 2024; CZNCS00 holds
33,512 starting 1998. So a mnemonic is always resolved to the
``calcseriescode`` with the MOST rows, never to whichever row comes back first.

**Currency.** Returns are in each contract's LOCAL currency (Bund in EUR, Nikkei
in JPY). That is the standard convention for futures trend research — margin is
posted locally and FX exposure is a separate decision — but these are not USD
returns.
"""

from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

SCHEMA = "tr_ds_fut"
VALUE_ROW = "Value_"          # the only _name_ that carries the time series

# Chosen by measurement, not assumption - see tools/compare_ds_roll_methods.py
# and local_data/ds_roll_comparison.csv. Across all 39 candidate markets and the
# four tradeable front-contract roll rules (CS00-CS03):
#
#   CS00  32/39 usable, 28 with volume, median 31.7 yrs, earliest 1979-01  <- base
#   CS01  30/39 usable, 27 with volume, median 29.2 yrs
#   CS02   0/39 usable  (contract month is entirely absent)
#   CS03  32/39 usable,  2 with volume, median 29.2 yrs
#
# CS00 and CS03 tie on coverage; CS00 wins because it carries volume and open
# interest for 28 markets against CS03's 2. CS04 ("as a price index") and CS05
# ("average of all futures") are excluded on principle: they are index
# constructions, not tradeable front-contract positions, however complete.
#
# Three markets use a fallback rule because CS00 is empty or absent for them.
# COMPROMISE: mixing roll rules means those three are not strictly comparable to
# the rest - the switch date differs by days. Accepted because all three are
# still front-contract rolls and roll-day returns are masked anyway; recorded
# here so it is not forgotten.
#
# Dropped (no usable variant in CS00-CS03): AUS10Y (~700 rows everywhere) and
# the FINEX FX contracts EURUSD (ends 2008-01), USDCHF and USDJPY (end 2019-04),
# which were delisted. The FX leg is therefore thin - USDINDEX (a basket) and
# GBPJPY only - and that is this basket's weakest asset class.
BASKET = {
    # --- equity --------------------------------------------------------
    "GDXCS00": ("equity", "DAX"),
    "GEXCS00": ("equity", "ESTOXX50"),
    "LSXCS00": ("equity", "FTSE100"),
    "HSICS00": ("equity", "HANGSENG"),
    "KKXCS00": ("equity", "KOSPI200"),
    "ONACS00": ("equity", "NIKKEI225"),
    "AAPCS03": ("equity", "SPI200"),   # fallback roll 3
    # --- bond ----------------------------------------------------------
    "ATYCS03": ("bond", "AUS3Y"),   # fallback roll 3
    "GBECS00": ("bond", "BOBL"),
    "GGECS00": ("bond", "BUND"),
    "LIGCS00": ("bond", "GILT"),
    "SJGCS00": ("bond", "JGB10Y"),
    "GEBCS00": ("bond", "SCHATZ"),
    "CZNCS00": ("bond", "US10Y"),
    "CZTCS00": ("bond", "US2Y"),
    "CZBCS00": ("bond", "US30Y"),
    "CZFCS00": ("bond", "US5Y"),
    # --- fx ------------------------------------------------------------
    "NSYCS00": ("fx", "GBPJPY"),
    "NDXCS00": ("fx", "USDINDEX"),
    # --- energy --------------------------------------------------------
    "LLCCS00": ("energy", "BRENT"),
    "NNGCS01": ("energy", "NATGAS"),   # fallback roll 1
    "LTCCS00": ("energy", "WTI"),
    # --- metal ---------------------------------------------------------
    "LAHCS00": ("metal", "ALUMINIUM"),
    "LCPCS00": ("metal", "COPPER"),
    "CZGCS00": ("metal", "GOLD"),
    "LNICS00": ("metal", "NICKEL"),
    "CZICS00": ("metal", "SILVER"),
    "LZZCS00": ("metal", "ZINC"),
    # --- ag ------------------------------------------------------------
    "NCCCS00": ("ag", "COCOA"),
    "NKCCS00": ("ag", "COFFEE"),
    "PCOCS00": ("ag", "CORN_MAT"),
    "NJOCS00": ("ag", "ORANGEJUICE"),
    "NSBCS00": ("ag", "SUGAR"),
    "LWHCS00": ("ag", "WHEAT_LIF"),
    "PMWCS00": ("ag", "WHEAT_MAT"),
}


# -- resolution ------------------------------------------------------------


def resolve_series(loader, mnemonics: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """Map each dsmnem to the ``calcseriescode`` with the MOST observations.

    dsmnem is not unique in ``wrds_cseries_info``, and some duplicates are
    near-empty re-issues (CZNCS01 holds 1,401 rows from 2024 against CZNCS00's
    33,512 from 1998). Resolving by data volume avoids silently picking one of
    those. Row counts are taken under the ``_name_`` filter, or they come out 5x
    too large.

    Returns one row per mnemonic with ``label`` and ``asset_class`` attached.
    """
    mnems = tuple(mnemonics if mnemonics is not None else BASKET)
    got = loader.raw_sql(f"""
        select i.calcseriescode, i.dsmnem, i.calcseriesname, i.isocurrcode,
               (select count(*) from {SCHEMA}.wrds_fut_series v
                where v.calcseriescode = i.calcseriescode
                  and v._name_ = %(nm)s) as n_rows
        from {SCHEMA}.wrds_cseries_info i
        where i.dsmnem in %(m)s
    """, params={"m": mnems, "nm": VALUE_ROW})
    if got.empty:
        raise ValueError(f"no series resolved for {len(mnems)} mnemonics")

    got["n_rows"] = pd.to_numeric(got["n_rows"]).astype("int64")
    got = (got.sort_values("n_rows")
              .drop_duplicates("dsmnem", keep="last")
              .reset_index(drop=True))
    got["label"] = got["dsmnem"].map(lambda m: BASKET[m][1] if m in BASKET else m)
    got["asset_class"] = got["dsmnem"].map(
        lambda m: BASKET[m][0] if m in BASKET else "?")
    return got.sort_values(["asset_class", "label"]).reset_index(drop=True)


def fetch_series(loader, code: int) -> pd.DataFrame:
    """One continuous series as a date-indexed frame of ``px`` and ``cmonth``.

    The ``_name_`` filter is what turns the stacked table into one row per date.
    """
    df = loader.raw_sql(f"""
        select date_, settlement, cmonth
        from {SCHEMA}.wrds_fut_series
        where calcseriescode = %(c)s and _name_ = %(nm)s
        order by date_
    """, params={"c": int(code), "nm": VALUE_ROW})
    df["px"] = pd.to_numeric(df["settlement"], errors="coerce").astype("float64")
    df["cmonth"] = pd.to_numeric(df["cmonth"], errors="coerce").astype("float64")
    df["date"] = pd.to_datetime(df["date_"])
    return (df.dropna(subset=["px"]).drop_duplicates("date")
              .set_index("date")[["px", "cmonth"]])


# -- cleaning --------------------------------------------------------------


def clean_prices(df: pd.DataFrame, label: str = "",
                 verbose: bool = False) -> Tuple[pd.DataFrame, int, int]:
    """Drop the two kinds of bad settlement price found in ``tr_ds_fut``.

    1. **Zero prices.** Datastream writes ``settlement = 0`` on some non-trading
       days (SILVER, 2013-01-01, New Year's Day) instead of omitting the row.
       Taken at face value that is a -100% return followed by an infinite one.
       Prices are strictly positive, so zero means "no data".

    2. **Isolated unit glitches.** MATIF milling wheat prints 762.0 on
       1998-12-30 between neighbours of 116.01 and 120.0 — and 762 / 6.55957 =
       116.2, where 6.55957 is the fixed franc-to-euro rate. One observation was
       left in francs across the 1999 changeover, producing a fake +557% followed
       by -84%. Detected as a large move that immediately reverses.

    Dropping the offending **price** rather than the resulting return is what
    makes the repair correct: ``pct_change`` then spans the gap and yields the
    true move across it (+2.58% for the silver holiday, +3.44% for the wheat).

    Returns ``(cleaned, n_zero_dropped, n_spikes_dropped)``.
    """
    n0 = len(df)
    df = df[df["px"] > 0.0]
    n_zero = n0 - len(df)

    lr = np.log(df["px"]).diff()
    spike = ((lr.abs() > 0.5) & (lr.shift(-1).abs() > 0.5)
             & (np.sign(lr) != np.sign(lr.shift(-1))))
    n_spike = int(spike.sum())
    if n_spike:
        if verbose:
            for dt in df.index[spike]:
                print(f"      {label}: dropped spike at {dt:%Y-%m-%d} "
                      f"px={df.loc[dt, 'px']:.4g}", flush=True)
        df = df[~spike]
    return df, n_zero, n_spike


def looks_like_yyyymm(v: pd.Series) -> bool:
    """Is this generic value slot really carrying a contract month?

    ``cmonth`` is a slot whose meaning depends on ``_name_``, so verify rather
    than assume: contract months are YYYYMM in a plausible range with a month
    part of 1-12. If this fails, roll detection for that series is invalid and
    the caller must not pretend otherwise.
    """
    x = pd.to_numeric(v, errors="coerce").dropna()
    if len(x) < 100:
        return False
    in_range = x.between(190001, 210012)
    if in_range.mean() < 0.95:
        return False
    return bool((x[in_range] % 100).between(1, 12).mean() > 0.99)


def mask_roll_returns(df: pd.DataFrame) -> Tuple[pd.Series, int, bool]:
    """Daily returns with the roll-day return removed.

    On a roll day ``pct_change`` compares the OLD contract yesterday with the NEW
    contract today — two different instruments on two different dates. That is
    not the return on any position, and it cannot be repaired from this series
    alone because the new contract's prior close is not in it. So the value is
    masked rather than guessed.

    Returns ``(returns, n_rolls, roll_ok)``. When the contract-month slot does
    not validate, returns are still produced but nothing is masked and
    ``roll_ok`` is False — the caller must treat that market as suspect.
    """
    ret = df["px"].pct_change()
    if not looks_like_yyyymm(df["cmonth"]):
        return ret, 0, False
    is_roll = df["cmonth"].diff().fillna(0.0) != 0.0
    return ret.mask(is_roll), int(is_roll.sum()), True


# -- panels ----------------------------------------------------------------


def to_monthly(daily: pd.DataFrame, min_obs: int = 6) -> pd.DataFrame:
    """Compound daily returns into month-end returns.

    Masked roll days are NaN and simply do not contribute — treated as "no
    observation" rather than as a zero return. A month with ``min_obs`` or fewer
    observations is set to NaN so that a market's first partial month, or one
    with a data gap, does not masquerade as a real (small) return.
    """
    m = (1.0 + daily.fillna(0.0)).groupby(pd.Grouper(freq="ME")).prod() - 1.0
    m = m.where(daily.notna().groupby(pd.Grouper(freq="ME")).sum() > min_obs)
    m.index.name = "date"
    return m


def build_panels(loader, basket: Optional[Dict[str, tuple]] = None,
                 verbose: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame,
                                                pd.DataFrame]:
    """Fetch, clean and assemble the whole basket.

    Returns ``(daily, monthly, meta)``. ``meta`` records per market how much was
    cleaned and whether roll masking was possible, so data problems stay visible
    instead of being averaged away.
    """
    basket = basket or BASKET
    meta_rows, daily, suspect = [], {}, []

    info = resolve_series(loader, basket)
    if verbose:
        missing = sorted(set(basket) - set(info["dsmnem"]))
        if missing:
            print(f"!! not in wrds_cseries_info: {missing}")
        print(f"{len(info)} series resolved; pulling (_name_='{VALUE_ROW}') ...\n")
        print(f"  {'label':<13}{'ccy':<5}{'obs':>8}{'first':>10}{'last':>10}"
              f"{'rolls':>7}{'zero':>6}{'spike':>7}  flag")

    for _, r in info.iterrows():
        df = fetch_series(loader, r["calcseriescode"])
        df, n_zero, n_spike = clean_prices(df, r["label"], verbose=verbose)
        if len(df) < 250:
            if verbose:
                print(f"  {r['label']:<13}{str(r['isocurrcode']):<5}{len(df):>8}"
                      f"  SKIPPED (too short)")
            continue
        ret, n_roll, roll_ok = mask_roll_returns(df)
        daily[r["label"]] = ret
        meta_rows.append({**r.to_dict(), "obs": len(df), "rolls": n_roll,
                          "roll_ok": roll_ok, "bad_zero": n_zero,
                          "bad_spike": n_spike,
                          "first": df.index.min(), "last": df.index.max()})
        if not roll_ok:
            suspect.append(r["label"])
        if verbose:
            first, last = f"{df.index.min():%Y-%m}", f"{df.index.max():%Y-%m}"
            print(f"  {r['label']:<13}{str(r['isocurrcode']):<5}{len(df):>8}"
                  f"{first:>10}{last:>10}{n_roll:>7}{n_zero:>6}{n_spike:>7}"
                  f"  {'' if roll_ok else 'NO ROLL INFO'}")

    if not daily:
        raise RuntimeError("no series fetched")

    d = pd.DataFrame(daily).sort_index()
    d.index.name = "date"
    n_bad = int(np.isinf(d.to_numpy(dtype="float64", na_value=np.nan)).sum())
    if n_bad:
        if verbose:
            print(f"\n!! {n_bad} non-finite daily return(s) survived cleaning; "
                  f"masking them")
        d = d.replace([np.inf, -np.inf], np.nan)

    if suspect and verbose:
        print(f"\n!! {len(suspect)} market(s) have no usable contract-month slot, "
              f"so roll days could NOT be masked:\n   {', '.join(suspect)}")
        print("   Their returns still contain roll gaps - exclude them, or find "
              "the roll dates from wrds_contract_info.lasttrddate instead.")

    return d, to_monthly(d), pd.DataFrame(meta_rows)


def effective_breadth(returns: pd.DataFrame) -> Tuple[int, float, float]:
    """``(n_markets, mean |pairwise corr|, effective breadth)``.

    Effective breadth is ``sum(eig)^2 / sum(eig^2)`` of the correlation matrix —
    how many genuinely independent bets the panel contains. The 10-ETF basket
    scores 3.4; 35 futures score about 8.2. Counting markets overstates
    diversification badly when ten of them are points on two yield curves.
    """
    x = returns.dropna(axis=1, how="all").dropna()
    c = x.corr()
    ev = np.linalg.eigvalsh(c.fillna(0.0).values)
    off = c.values[np.triu_indices(len(c), 1)]
    return x.shape[1], float(np.nanmean(np.abs(off))), float(ev.sum() ** 2 / (ev ** 2).sum())
