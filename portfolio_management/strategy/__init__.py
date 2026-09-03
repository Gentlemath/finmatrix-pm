"""Portfolio strategy module."""

from .momentum import MomentumStrategy
from .pead import analyst_sue, event_car, standardized_unexpected_earnings
from .trend import (
    PRECIOUS_METALS,
    TREND_SPEEDS,
    TimeSeriesMomentum,
    lookback_by_group,
    speed_group,
    trend_signal_table,
)
from .performance import (
    apply_costs,
    capm,
    cap_weighted_return,
    max_drawdown,
    performance_summary,
    transaction_costs,
    turnover,
    volatility_target,
)
from .universe import build_membership, panels_from_crsp

__all__ = [
    "MomentumStrategy",
    "PRECIOUS_METALS",
    "TREND_SPEEDS",
    "TimeSeriesMomentum",
    "lookback_by_group",
    "speed_group",
    "trend_signal_table",
    "build_membership",
    "panels_from_crsp",
    "performance_summary",
    "capm",
    "turnover",
    "volatility_target",
    "transaction_costs",
    "apply_costs",
    "cap_weighted_return",
    "max_drawdown",
    "standardized_unexpected_earnings",
    "analyst_sue",
    "event_car",
]
