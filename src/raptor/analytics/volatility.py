"""Historical volatility calculated deterministically from supplied bars."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Sequence

from ._num import ZERO, dsqrt, dstdev, q4, safe_div
from .types import MetricStatus, PriceBar, VolatilityEstimate, VolatilityMetrics

__all__ = ["compute_historical_volatility"]


def compute_historical_volatility(
    bars: Sequence[PriceBar], annualization_periods: int = 252
) -> VolatilityMetrics:
    """Return annualized close-to-close volatility for each supplied symbol.

    At least three bars (two returns) are required per symbol. Missing or short
    histories return explicit statuses and ``None`` values; they are never
    turned into a misleading zero-volatility observation.
    """
    if annualization_periods <= 0:
        raise ValueError("annualization_periods must be positive")
    if not bars:
        return VolatilityMetrics(
            status=MetricStatus.UNAVAILABLE,
            annualization_periods=annualization_periods,
            estimates=(),
            reason="No price bars were supplied.",
        )

    grouped: dict[str, list[PriceBar]] = defaultdict(list)
    for bar in bars:
        if not isinstance(bar, PriceBar):
            raise TypeError("bars must contain PriceBar instances")
        grouped[bar.symbol].append(bar)

    estimates: list[VolatilityEstimate] = []
    for symbol in sorted(grouped):
        ordered = sorted(grouped[symbol], key=lambda bar: bar.timestamp)
        returns = [
            q4(safe_div(current.close - previous.close, previous.close))
            for previous, current in zip(ordered, ordered[1:])
            if previous.close > ZERO
        ]
        if len(returns) < 2:
            estimates.append(
                VolatilityEstimate(
                    symbol=symbol,
                    status=MetricStatus.INCONCLUSIVE,
                    annualized_volatility=None,
                    observations=len(ordered),
                    reason="At least three valid bars are required.",
                )
            )
            continue

        realized = q4(dstdev(returns, sample=True) * dsqrt(Decimal(annualization_periods)))
        estimates.append(
            VolatilityEstimate(
                symbol=symbol,
                status=MetricStatus.AVAILABLE,
                annualized_volatility=realized,
                observations=len(ordered),
            )
        )

    statuses = {estimate.status for estimate in estimates}
    overall = (
        MetricStatus.AVAILABLE
        if statuses == {MetricStatus.AVAILABLE}
        else MetricStatus.INCONCLUSIVE
    )
    reason = None if overall is MetricStatus.AVAILABLE else "Some symbols lack enough bars."
    return VolatilityMetrics(
        status=overall,
        annualization_periods=annualization_periods,
        estimates=tuple(estimates),
        reason=reason,
    )
