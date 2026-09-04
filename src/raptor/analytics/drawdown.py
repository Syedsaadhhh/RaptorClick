"""Drawdown analytics over an account equity curve.

Drawdown is the metric retail traders actually feel. Volatility is abstract;
"you were down 22% and needed a 28% gain to get back to even" is not.

Metrics produced
----------------
* **max drawdown** - deepest peak-to-trough decline over the series.
* **current drawdown** - distance below the running peak *right now*. Being in
  a drawdown is materially worse than having recovered from one, so the scorer
  treats these separately.
* **recovery needed** - the gain required to return to the peak. This is not
  the drawdown: a 50% loss needs a 100% gain, and that asymmetry is the single
  most under-appreciated fact in retail risk.
* **ulcer index** - RMS of the drawdown series. Penalises deep *and* long
  drawdowns, where max drawdown only sees the single worst point.
* **periods under water** - observations spent below the peak.

Degradation policy
------------------
This module never raises on short history. Zero or one observation yields
zeroed metrics, and the scoring layer treats "no drawdown data" as a neutral
component rather than a good one - a fresh account has not proven anything.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from ._num import ZERO, dsqrt, dsum, q2, q4, safe_div
from .types import DrawdownMetrics, EquityPoint, PortfolioSnapshot

__all__ = ["compute_drawdown", "drawdown_series", "returns_series"]

_EMPTY = DrawdownMetrics(
    max_drawdown=ZERO,
    max_drawdown_value=ZERO,
    current_drawdown=ZERO,
    peak_equity=ZERO,
    trough_equity=ZERO,
    recovery_needed=ZERO,
    ulcer_index=ZERO,
    periods_under_water=0,
    observations=0,
)


def drawdown_series(history: Sequence[EquityPoint]) -> list[Decimal]:
    """Fractional drawdown at each observation, relative to the running peak.

    Values are non-negative: 0.05 means "5% below the peak at that time".

    The running peak is computed forward through the series with no lookahead,
    which is what makes the result identical whether it is computed once over
    the whole history or incrementally as new points arrive.
    """
    series: list[Decimal] = []
    peak = ZERO
    for point in history:
        if point.equity > peak:
            peak = point.equity
        # Guard the opening zero-equity case rather than dividing by zero.
        drawdown = safe_div(peak - point.equity, peak) if peak > ZERO else ZERO
        series.append(q4(drawdown))
    return series


def returns_series(history: Sequence[EquityPoint]) -> list[Decimal]:
    """Period-over-period fractional returns.

    Used by :mod:`raptor.analytics.hedge` for parametric VaR. Periods with a
    zero prior equity are skipped rather than treated as a total loss, which
    would poison the volatility estimate.
    """
    returns: list[Decimal] = []
    for prev, curr in zip(history, history[1:]):
        if prev.equity == ZERO:
            continue
        returns.append(q4(safe_div(curr.equity - prev.equity, prev.equity)))
    return returns


def compute_drawdown(snapshot: PortfolioSnapshot) -> DrawdownMetrics:
    """Compute drawdown metrics from a snapshot's equity history.

    History is already sorted chronologically by
    :class:`~raptor.analytics.types.PortfolioSnapshot`, so results do not depend
    on the order the backend fetched the bars in.

    Returns zeroed metrics when there are fewer than two observations.
    """
    history = snapshot.history
    if len(history) < 2:
        return _EMPTY

    series = drawdown_series(history)
    equities = [p.equity for p in history]

    peak = max(equities)
    max_drawdown = max(series)
    current_drawdown = series[-1]

    # The trough that produced the *maximum* drawdown - not the global minimum.
    # Those differ whenever the account made a new high after a deep decline,
    # and the max-drawdown trough is the one that explains the number.
    worst_index = series.index(max_drawdown)
    trough = equities[worst_index]

    running_peak = ZERO
    for equity in equities[: worst_index + 1]:
        running_peak = max(running_peak, equity)
    max_drawdown_value = q2(running_peak - trough)

    # Asymmetry of recovery: a 50% loss needs a 100% gain.
    current_equity = equities[-1]
    recovery_needed = (
        q4(safe_div(peak - current_equity, current_equity))
        if current_equity > ZERO and peak > current_equity
        else ZERO
    )

    # Ulcer index: RMS of the drawdown series, expressed in percent.
    squared = dsum(d * d for d in series)
    ulcer = q4(dsqrt(safe_div(squared, len(series))) * Decimal("100"))

    periods_under_water = sum(1 for d in series if d > ZERO)

    return DrawdownMetrics(
        max_drawdown=q4(max_drawdown),
        max_drawdown_value=max_drawdown_value,
        current_drawdown=q4(current_drawdown),
        peak_equity=q2(peak),
        trough_equity=q2(trough),
        recovery_needed=recovery_needed,
        ulcer_index=ulcer,
        periods_under_water=periods_under_water,
        observations=len(history),
    )
