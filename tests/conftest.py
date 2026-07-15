"""Shared pytest configuration and fixtures.

Tests are network-free and deterministic. They import the ``portfolio_management``
package, which is expected to be installed (``pip install -e .``); no ``sys.path``
manipulation is needed. Matplotlib uses the non-interactive ``Agg`` backend so
plot functions can be smoke-tested without a display.
"""

import matplotlib

matplotlib.use("Agg")  # must be set before pyplot is imported anywhere

import numpy as np
import pandas as pd
import pytest

# A fixed seed keeps every synthetic series reproducible across runs.
SEED = 20260711


@pytest.fixture
def rng():
    """A seeded NumPy random generator."""
    return np.random.default_rng(SEED)


@pytest.fixture
def dates():
    """A business-day DatetimeIndex of 750 observations (~3 years)."""
    return pd.date_range("2021-01-01", periods=750, freq="B")


@pytest.fixture
def returns_series(rng, dates):
    """A single stationary return series (percent units), as a named Series."""
    values = rng.normal(loc=0.05, scale=1.0, size=len(dates))
    return pd.Series(values, index=dates, name="ASSET")


@pytest.fixture
def returns_frame(rng, dates):
    """A two-asset return DataFrame (percent units)."""
    data = rng.normal(loc=0.05, scale=1.0, size=(len(dates), 2))
    return pd.DataFrame(data, index=dates, columns=["AAA", "BBB"])


@pytest.fixture
def prices_frame(returns_frame):
    """A two-asset price DataFrame built from the return frame."""
    return 100.0 * (1 + returns_frame / 100.0).cumprod()


@pytest.fixture
def regime_series(rng, dates):
    """A return series with a deliberately injected high-volatility middle regime."""
    n = len(dates)
    vol = np.full(n, 0.5)
    vol[n // 3 : 2 * n // 3] = 3.0  # a clear high-vol block in the middle
    values = rng.normal(loc=0.0, scale=1.0, size=n) * vol
    return pd.Series(values, index=dates, name="REGIME")
