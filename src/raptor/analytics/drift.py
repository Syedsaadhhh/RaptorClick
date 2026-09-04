"""Deterministic state-drift checks used to trigger a fresh hedge auction."""

from __future__ import annotations

from decimal import Decimal

from ._num import ZERO, q4
from .config import DEFAULT_CONFIG, AnalyticsConfig
from .exposure import compute_concentration, compute_exposure
from .types import DriftAssessment, PortfolioSnapshot

__all__ = ["assess_state_drift"]


def _relative_change(previous: Decimal, current: Decimal) -> Decimal:
    if previous == ZERO:
        return ZERO if current == ZERO else Decimal("1")
    return q4(abs(current - previous) / abs(previous))


def assess_state_drift(
    previous: PortfolioSnapshot,
    current: PortfolioSnapshot,
    config: AnalyticsConfig = DEFAULT_CONFIG,
) -> DriftAssessment:
    """Mark a prior bid stale when portfolio state crosses configured limits."""
    previous_exposure = compute_exposure(previous)
    current_exposure = compute_exposure(current)
    previous_concentration = compute_concentration(previous)
    current_concentration = compute_concentration(current)

    equity_drift = _relative_change(previous.equity, current.equity)
    exposure_drift = _relative_change(
        previous_exposure.gross_exposure, current_exposure.gross_exposure
    )
    concentration_drift = q4(
        abs(current_concentration.hhi - previous_concentration.hhi)
    )
    symbols_changed = {position.symbol for position in previous.positions} != {
        position.symbol for position in current.positions
    }

    reasons: list[str] = []
    if equity_drift > config.max_equity_drift:
        reasons.append(
            f"equity drift {equity_drift} exceeds {config.max_equity_drift}"
        )
    if exposure_drift > config.max_gross_exposure_drift:
        reasons.append(
            "gross exposure drift "
            f"{exposure_drift} exceeds {config.max_gross_exposure_drift}"
        )
    if concentration_drift > config.max_concentration_drift:
        reasons.append(
            "concentration drift "
            f"{concentration_drift} exceeds {config.max_concentration_drift}"
        )
    if symbols_changed:
        reasons.append("position symbols changed")

    return DriftAssessment(
        is_stale=bool(reasons),
        equity_drift=equity_drift,
        gross_exposure_drift=exposure_drift,
        concentration_drift=concentration_drift,
        symbols_changed=symbols_changed,
        reasons=tuple(reasons),
    )
