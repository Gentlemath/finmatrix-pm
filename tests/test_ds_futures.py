"""Tests for the Datastream futures helpers (synthetic + the real bad data).

The two cleaning cases use the ACTUAL values that broke the first download, so a
regression would reproduce a bug we have already paid for once.
"""

import numpy as np
import pandas as pd
import pytest

from portfolio_management.dataloader.ds_futures import (
    BASKET, clean_prices, effective_breadth, looks_like_yyyymm,
    mask_roll_returns, to_monthly)


def _frame(px, cmonth, start="2015-01-01"):
    idx = pd.bdate_range(start, periods=len(px))
    return pd.DataFrame({"px": px, "cmonth": cmonth}, index=idx, dtype="float64")


class TestBasket:
    def test_basket_is_consistent(self):
        assert len(BASKET) == 35
        labels = [v[1] for v in BASKET.values()]
        assert len(set(labels)) == len(labels)          # no duplicate labels
        # every mnemonic is [MARKET]CS0n - front-month continuations only
        assert all(len(m) > 4 and m[-4:-2] == "CS" and m[-2] == "0"
                   for m in BASKET)


class TestCleanPrices:
    def test_zero_price_dropped_and_gap_spanned(self):
        """SILVER 2013-01-01: settlement 0 on a holiday (real values)."""
        df = _frame([30.196991, 0.0, 30.97699, 30.71399], [201301, 201302, 201302, 201302])
        out, n_zero, n_spike = clean_prices(df)
        assert (n_zero, n_spike) == (1, 0)
        ret = out["px"].pct_change()
        # the gap is spanned, giving the true two-day move, not -100% then inf
        assert ret.iloc[1] == pytest.approx(30.97699 / 30.196991 - 1, rel=1e-9)
        assert np.isfinite(ret.dropna()).all()

    def test_isolated_unit_spike_dropped(self):
        """MATIF wheat 1998-12-30: one observation left in francs (real values)."""
        df = _frame([116.01369, 762.0, 120.0, 119.0], [199901, 199901, 199903, 199903])
        out, n_zero, n_spike = clean_prices(df)
        assert (n_zero, n_spike) == (0, 1)
        assert 762.0 not in set(out["px"])
        ret = out["px"].pct_change()
        assert ret.iloc[1] == pytest.approx(120.0 / 116.01369 - 1, rel=1e-9)

    def test_genuine_large_move_is_kept(self):
        """A big move that does NOT reverse is real and must survive."""
        df = _frame([100.0, 175.0, 178.0, 176.0], [201503] * 4)
        out, _, n_spike = clean_prices(df)
        assert n_spike == 0
        assert len(out) == 4


class TestRollMasking:
    def test_roll_day_return_is_masked(self):
        # looks_like_yyyymm needs >=100 observations before it will trust the
        # contract-month slot, so the fixture has to be realistically long.
        px = [100.0 + 0.1 * i for i in range(60)]
        px += [p - 10.0 for p in px]                # a -10 point gap at the roll
        cm = [201503.0] * 60 + [201506.0] * 60
        df = _frame(px, cm)
        ret, n_rolls, ok = mask_roll_returns(df)
        assert ok and n_rolls == 1
        assert pd.isna(ret.iloc[60])                # the splice is gone
        assert ret.iloc[61] == pytest.approx(px[61] / px[60] - 1)
        assert ret.drop(ret.index[60]).abs().max() < 0.02   # rest are normal

    def test_unusable_contract_month_reports_not_ok(self):
        df = _frame([100.0 + i for i in range(120)], [25.0] * 120)
        ret, n_rolls, ok = mask_roll_returns(df)
        assert not ok and n_rolls == 0
        assert ret.notna().sum() == 119             # nothing masked, but flagged

    @pytest.mark.parametrize("vals,expected", [
        ([201501.0] * 120, True),
        ([25.0] * 120, False),
        ([201513.0] * 120, False),                  # month 13 is not a month
        ([201501.0] * 50, False),                   # too few observations
    ])
    def test_looks_like_yyyymm(self, vals, expected):
        assert looks_like_yyyymm(pd.Series(vals)) is expected


class TestMonthly:
    def test_compounds_and_drops_thin_months(self):
        idx = pd.bdate_range("2020-01-01", "2020-03-31")
        d = pd.DataFrame(index=idx, columns=["FULL", "THIN"], dtype="float64")
        d["FULL"] = 0.001
        d.loc["2020-01-06":"2020-01-08", "THIN"] = 0.001    # only 3 obs
        m = to_monthly(d)
        assert m["FULL"].notna().all()
        assert pd.isna(m["THIN"].iloc[0])
        jan = d["FULL"].loc["2020-01"]
        assert m["FULL"].iloc[0] == pytest.approx((1 + jan).prod() - 1)

    def test_masked_roll_day_does_not_count_as_zero_return(self):
        idx = pd.bdate_range("2020-01-01", "2020-01-31")
        a = pd.Series(0.001, index=idx)
        b = a.copy()
        b.iloc[5] = np.nan                          # a masked roll
        m = to_monthly(pd.DataFrame({"A": a, "B": b}))
        assert m["B"].iloc[0] < m["A"].iloc[0]      # one fewer day compounded


class TestBreadth:
    def test_independent_series_score_near_n(self):
        rng = np.random.default_rng(0)
        x = pd.DataFrame(rng.normal(size=(400, 5)),
                         index=pd.bdate_range("2015-01-01", periods=400))
        n, corr, breadth = effective_breadth(x)
        assert n == 5 and corr < 0.15 and breadth > 4.0

    def test_identical_series_score_near_one(self):
        rng = np.random.default_rng(1)
        base = rng.normal(size=400)
        x = pd.DataFrame({f"c{i}": base for i in range(5)},
                         index=pd.bdate_range("2015-01-01", periods=400))
        _, corr, breadth = effective_breadth(x)
        assert corr > 0.99 and breadth == pytest.approx(1.0, abs=0.01)
