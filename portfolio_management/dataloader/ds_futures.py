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

**4. A series can stop carrying prices while still emitting rows.** After a
series goes quiet, ``wrds_fut_series`` keeps returning rows for it with
``settlement`` NULL. Gold (CZGCS00) has 13 such rows spread over 3.6 years, so
``max(date_)`` reads 2026-06-26 while the last real price is 2022-11-30. Nor is
the series flagged ``DEAD`` in ``calcseriesname`` — Datastream does use that flag,
just not here. **So neither the catalogue nor ``max(date_)`` detects staleness.**
The only reliable test is::

    max(date_) filter (where settlement is not null)

Measured 2026-09-09, seven of the 35 basket markets are stale at the recent end:
GOLD and SILVER end 2022-11-30, US2Y/US5Y/US10Y/US30Y all end 2025-04-25, and
NATGAS ends 2026-04-02. ``fetch_series`` handles this correctly
(``dropna(subset=["px"])`` discards the NULL rows), so the truncation is real
data loss, not a bug here.

**5. A market has SEVERAL classes; the continuous series pins it to ONE, and for
the CME markets that one is deprecated.** The hierarchy is
instrument -> class (``clscode``) -> contract -> prices. ``clscode`` appears in
both ``wrds_cseries_info`` and ``wrds_contract_info``, so it links a series to
its contracts -- but it is NOT one-to-one with the instrument. Six basket markets
point at a dead class while a live one exists::

    market  basket cls   better cls   months            mnem family
    SILVER   3607         1574        218 ->  639       1973-01 ..
    GOLD      335         1508        218 ->  584       1977-08 ..
    US30Y     330         2441 (CUB)  319 ->  584       1977-08 ..
    US10Y     338         3896 (CTT)  318 ->  527       1982-05 ..
    US5Y      334         1997 (CTF)  318 ->  455       1988-05 ..
    US2Y      342         2523 (CTE)  319 ->  430       1990-06 ..

The US notes hide under a SECOND naming family: the basket's classes are named
"10 YEAR US TREASURY NOTE" while the live ones are "10 YRS US T-NOTE COMP.".
Searching by the basket's own contrname will never find them.

When swapping a class, verify ``isocurrcode`` AND the dsmnem prefix, not the
name. Matching on contrname alone flags ICE UK gas (GBP, LNG) as an "upgrade" to
NYMEX Henry Hub (USD, NNG), and Tokyo corn (JPY, JCN) as an upgrade to MATIF corn
(EUR, PCO). All CME classes still stop at 2026-04-03.

**6. THE CONTINUOUS-SERIES TABLES NO LONGER CARRY CME GROUP DATA.** The seven
stale markets are exactly the seven CME Group markets in the basket -- 7 of 7
dead, against 28 of 28 live on other exchanges. A survey of every series priced
after 2026-06-01 (checked 2026-09-09) returns 40 exchange prefixes with 3+ such
continuous series (EUREX 328, NSE,
LIFFE, BSE, MEFF, HKFE, KSE, ICE, SFE, LME, TOCOM, ME, SGX, TAIFEX, MATIF, ...)
and NO CME, CBOT, ECBOT, COMEX, NYL or NYMEX entry anywhere. Withdrawal is
staggered by exchange: COMEX 2022-11, CBOT 2025-04, NYMEX 2026-04.

Do not go looking for these under new mnemonics -- they are not present under any
name IN THE CONTINUOUS-SERIES TABLES.

**But the CONTRACT-level tables still have CME.** ``wrds_contract_info`` /
``wrds_fut_contract`` hold 2,231 NYMEX, 679 CME, 559 CME E and 425 ECBOT
contracts, every one carrying settlements, with ``volume`` and ``openinterest``
populated. History far exceeds the derived series -- COMEX gold from 1977-08
(821 contracts) against the CS00 series' 2004-10; CBOT 10Y from 1982-05. All CME
markets stop at 2026-04-03, so the contract feed ceased too, just later and all
at once. Front-month open interest confirms identity: US5Y peaks at 6.8M
contracts, US10Y at 5.6M.

Rebuilding continuous series from contracts would fix three things this module
currently cannot: roll returns would be computable instead of masked (see
pitfall 2), the roll rule would be ours to choose and could follow open interest
rather than the calendar, and gold's history nearly triples. Traps: resolve
contract names as carefully as series names (gold has a retired ``CZG*`` family,
``CZG0626`` last priced 2021-12-13 with zero OI, beside the live ``NGC*``), and
a ``SILVER%`` name match also returns TOCOM/DGCX/MCX contracts.

If staying on the continuous series, substitutes on other exchanges, with LONGER
history than the COMEX series had, and in local currency per this module's
convention::

    GOLD    JAUCS00  TOCOM-GOLD (JPY)          1986-06 ..  9,832 obs
    SILVER  JSVCS00  TOCOM-SILVER (JPY)        1984-01 .. 10,437 obs
    NATGAS  LNGCS00  ICE-NATURAL GAS (GBP)     1997-02 ..  7,570 obs

US rates have no substitute; no US-exchange bond future survives here. For
sovereign breadth instead: AGDCS00 (SFE AU 10Y, 1984-12, 10,580), CDGCS00
(ME Canada 10Y, 1989-09, 9,128), KTBCS00 (KSE Korea 3Y, 1999-09, 6,642),
CGZCS00 (ME Canada 2Y, 2004-05, 5,533).

Note AGDCS00 above: the "Dropped ... AUS10Y (~700 rows everywhere)" comment below
is WRONG. The original search used the AUS3Y naming pattern
("SFE-AUST 3 YEAR T-BOND") but the ten-year is "SFE-AU 10 YR T-BOND DAY CONT", so
a 42-year series was missed. Search calcseriesname broadly, never by analogy to a
sibling contract's name.

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

# ---------------------------------------------------------------------------
# PLANNED REBUILD: 35 -> 46 markets. Decided 2026-09-10, extended 2026-09-10
# with FX and the US equity index. NOT YET EXECUTED.
#
# The basket below is keyed by dsmnem, which pins each market to ONE clscode.
# Six of those classes are deprecated while a live class for the same instrument
# exists (pitfall 5), and eleven live markets are missing entirely. Executing
# this needs each clscode resolved to its CS00 dsmnem first -- the mnemonics
# below are class families, not series names.
#
# KEY TO FINDING ANY OF THIS: the live CME classes sit in a naming family ending
# "COMP." -- "JAPANESE YEN COMP.", "STERLING COMP.", "10 YRS US T-NOTE COMP." --
# while the deprecated ones use the plain product name. Searching by the
# basket's own contrname finds only the dead ones. Use
# tools/survey_ds_classes.py, which queries the contract table and so sees
# every class.
#
# A. IDENTITY REPLACEMENTS -- same instrument, dead class -> live class.
#    Adds ~1,510 market-months and recovers stale tails (metals were stuck at
#    2022-11, bonds at 2025-04).
#
#      market   from cls   to cls          new coverage        months
#      SILVER   3607       1574            1973-01 .. 2026-04  218 -> 639
#      GOLD      335       1508            1977-08 .. 2026-04  217 -> 584
#      US30Y     330       2441 (CUB)      1977-08 .. 2026-04  319 -> 584
#      US10Y     338       3896 (CTT)      1982-05 .. 2026-04  318 -> 527
#      US5Y      334       1997 (CTF)      1988-05 .. 2026-04  318 -> 455
#      US2Y      342       2523 (CTE)      1990-06 .. 2026-04  319 -> 430
#
# B. FX -- the leg that most needs it: 2 markets today, and FX correlates -0.01
#    with the rest of the book, so it is the most valuable class per market and
#    the most under-supplied. All six are CME, all in the COMP. family, all
#    stop 2026-04-03. Three of them start 1973-01, when Bretton Woods collapsed
#    and the IMM began listing currency futures -- longer than ANY market
#    currently in the basket.
#
#      clscode  mnem  pair      coverage             months
#      2125     IJC   JPY/USD   1973-01 .. 2026-04   639
#      2094     IFC   CHF/USD   1973-01 .. 2026-04   639
#      2072     ICE   CAD/USD   1973-01 .. 2026-04   639
#      2059     IBC   GBP/USD   1975-10 .. 2026-04   605
#      2047     IAE   AUD/USD   1987-01 .. 2026-04   471
#      1999     CUC   EUR/USD   1998-05 .. 2026-04   334
#
#    EUR starts 1998-05 because the euro did not exist earlier; Deutsche Mark
#    futures are a different instrument, not deeper history for this one.
#
#    Redundancy to settle with the correlation check, not by argument:
#      - USDINDEX (kept) is 58% EUR, 14% JPY, 12% GBP, 9% CAD, 4% CHF. Four of
#        the six additions are inside it. Keeping it anyway because it is FINEX,
#        survives to 2026-08, and is the only FX signal in the last five months.
#      - GBPJPY (kept) becomes roughly (GBP/USD)/(JPY/USD) once both legs are in
#        the basket -- near-linear dependence. Its case is also recency.
#
#    A parallel set of non-CME pairs IS live to 2026-09 but starts much later:
#      1576 NSP GBP 2004-02, 94 BAU AUD 2004-08, 2929 NKU EUR 2011-06,
#      2924 NKA AUD 2011-06, 4163 SXU AUD/SGX 2013-11.
#    Useful only if a spliced tail past 2026-04 is wanted; separate work.
#
# C. US EQUITY INDEX -- the basket has seven equity indices and none in the US,
#    while SPY's standalone trend Sharpe was +0.55 over 2006-2026 against +0.01
#    for those seven. The E-mini exists; it is simply not named "E-mini":
#
#      clscode  mnem  contrname             coverage             months
#      1035     ISM   MINI S&P 500 INDEX    1997-09 .. 2026-04   343
#
#    Confirmed by three facts: prices start 1997-09 (the E-mini listed
#    1997-09-09), 137 contracts over 343 months is quarterly, and searching
#    "E-MINI" returns Russell/FTSE/sector/Micro/ESG variants but no plain S&P.
#
#    Deeper history is available but needs splicing, which is separate work:
#      3725 ISP  "S&P 500 INDEX"  1982-04 .. 2021-09-17, 473 months
#    ISP is the full-size contract CME delisted in September 2021. ISP + ISM
#    spliced would cover 1982-04 .. 2026-04, ~529 months. Do NOT put both in
#    the basket as separate markets: same underlying index, different contract
#    size, so that is double-counting (see the identity-rule refinement below).
#
# D. OTHER ADDITIONS -- different markets, all live to 2026-09, all non-CME.
#    Added rather than swapped in: breadth has repeatedly come from the
#    uncorrelated legs, not from any single market's history length. Dropping
#    agriculture alone cost 0.72 -> 0.63 Sharpe.
#
#      clscode  ccy  mnem  market                coverage             class
#      3756     GBP  LNG   ICE UK natural gas    1997-01 .. 2026-09   energy
#      1405     USD  MMW   wheat                 1978-04 .. 2026-09   ag
#      2216     JPY  JCN   Tokyo corn            1992-04 .. 2026-09   ag
#      3846     ZAR  SAC   SAFEX wheat           1997-11 .. 2026-09   ag
#
# RESULT: equity 7->8, bond 10, fx 2->8, energy 3->4, metal 6, ag 7->10.
#         35 -> 46 markets. Panel start 1979-01 -> 1973-01, with five markets
#         live in 1973 (silver, JPY, CHF, CAD, and CBOT corn if added).
#         This is aimed squarely at the study's weakest point: the 1979-1989
#         decade currently holds 4-10 markets and its slow group is GILT alone,
#         which is why the three-speed margin there is +0.10 against +0.37 to
#         +0.82 in every other decade.
#
# E. IDENTITY-RULE REFINEMENT. The working rule -- same currency AND same
#    mnemonic prefix means the same instrument, anything else is a different
#    market -- correctly stopped ICE UK gas being swapped for Henry Hub and
#    Tokyo corn for MATIF corn. But it needs one amendment: a different prefix
#    can also mean the SAME underlying at a different contract size.
#      ISP / ISM  (S&P 500 full-size vs E-mini)
#      IJC / IJE  (yen standard vs E-mini)
#      CUC / IEE  (euro standard vs E-mini)
#    Those pairs must be spliced or one chosen, never both listed. Decide by
#    what the contrname says the underlying is, not by the prefix alone. Where
#    one was chosen here it was the longer, more heavily traded standard-size
#    class: IJC over IJE (639 vs 318 months), CUC over IEE (334 vs 315).
#
# F. REJECTED
#      2010 CNY DC.  Dalian corn -- excluded by choice
#      2420 USD CCF  CBOT corn, 639 months from 1973-01, but dies 2026-04-03
#                    with the rest of CME; longest history in the whole survey
#      NATGAS        1539 USD NNG is already the best Henry Hub class; the GBP
#                    classes are ICE UK gas, a different market
#
# G. BEFORE COMMITTING: check each candidate's mean |correlation| against the
#    existing basket. The basket averages 0.24; a candidate above that dilutes
#    effective breadth instead of adding to it. Three specific risks:
#      - MMW / JCN / SAC are all grains and may be currency-translated views of
#        one global grain complex.
#      - Four of the six FX additions sit inside USDINDEX by construction.
#      - GBPJPY is near-linearly dependent on the GBP and JPY legs.
#    Also unverified: which exchange MMW actually is. What the data shows is
#    USD, 1978-04, 1 day stale -- so not in the CME withdrawal, whatever it is.
#
# H. WHAT THIS REBUILD STILL DOES NOT FIX. Every CME class stops 2026-04-03, so
#    the additions in B and C bring history, not recency: after 2026-04 there is
#    still no US rates, metals, Henry Hub gas, US equity index or major FX pair.
#    Only 28 of the current 35 markets are priced in the latest month; after the
#    rebuild that becomes 32 of 46.
# ---------------------------------------------------------------------------

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
# Dropped (no usable variant in CS00-CS03): AUS10Y -- WRONG, see pitfall 5 in the
# module docstring: AGDCS00 has 10,580 rows from 1984-12 and was missed by a
# naming mismatch. Should be added back. Also dropped:
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


def resolve_series(loader, mnemonics: Optional[Iterable[str]] = None,
                   basket: Optional[Dict[str, tuple]] = None) -> pd.DataFrame:
    """Map each dsmnem to the ``calcseriescode`` with the MOST observations.

    dsmnem is not unique in ``wrds_cseries_info``, and some duplicates are
    near-empty re-issues (CZNCS01 holds 1,401 rows from 2024 against CZNCS00's
    33,512 from 1998). Resolving by data volume avoids silently picking one of
    those. Row counts are taken under the ``_name_`` filter, or they come out 5x
    too large.

    Returns one row per mnemonic with ``label`` and ``asset_class`` attached.
    """
    # ``basket`` supplies the label/asset-class mapping. It defaults to BASKET,
    # but a caller assembling a DIFFERENT basket must be able to pass its own or
    # every market outside BASKET silently comes back labelled with its raw
    # mnemonic and an asset class of "?".
    names = basket if basket is not None else BASKET
    mnems = tuple(mnemonics if mnemonics is not None else names)
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
    got["label"] = got["dsmnem"].map(lambda m: names[m][1] if m in names else m)
    got["asset_class"] = got["dsmnem"].map(
        lambda m: names[m][0] if m in names else "?")
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

    info = resolve_series(loader, basket, basket=basket)
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
