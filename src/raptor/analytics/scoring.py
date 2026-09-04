"""Protection scoring - metrics in, defensible 0-100 verdict out.

Scoring philosophy
------------------
Every component is scored 0-100 by a **piecewise-linear band function**, then
combined with configured weights.

Piecewise-linear was chosen over the obvious alternatives on purpose:

* **Not a step function.** Cliff edges mean a portfolio flips from 80 to 40 on a
  rounding change in the fourth decimal. That looks broken in a live demo, and
  it *is* broken as risk measurement.
* **Not a logistic curve.** Smooth and defensible, but nobody can re-derive the
  number by hand. Explainability beats elegance when a user is deciding whether
  to trust the agent with money.
* **Piecewise-linear** degrades smoothly and stays auditable: given the bands
  and the input, anyone can reproduce the score with a calculator.

Every component carries a ``rationale`` string. A score with no explanation is
not something a user will act on.

Hard overrides
--------------
Weighted averages have a real failure mode: a book can be catastrophically
leveraged and still score respectably because its other components are clean.
:func:`_apply_overrides` caps the final score when any single dimension is
critical, so the headline number can never launder one fatal risk behind three
healthy ones.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from ._num import ONE, ZERO, D, Numeric, clamp, q2, q4, safe_div
from .config import DEFAULT_CONFIG, AnalyticsConfig
from .types import (
    ConcentrationMetrics,
    DrawdownMetrics,
    ExposureMetrics,
    HedgeEvaluation,
    ProtectionScore,
    RiskAssessment,
    RiskFlag,
    ScoreComponent,
    Severity,
    Verdict,
    sort_flags,
)

__all__ = [
    "band_score",
    "score_exposure",
    "score_concentration",
    "score_drawdown",
    "score_hedge",
    "compute_score",
    "grade_for",
]

_HUNDRED = Decimal("100")


def band_score(
    value: Numeric,
    good: Numeric,
    bad: Numeric,
    higher_is_better: bool = False,
) -> Decimal:
    """Map a metric onto 0-100 with linear interpolation between two anchors.

    Args:
        value: the observed metric.
        good: the value scoring 100.
        bad: the value scoring 0.
        higher_is_better: set when larger values are healthier (cash ratio),
            as opposed to the default where larger is worse (leverage).

    Returns:
        A score in ``[0, 100]``, clamped at both ends.

    Example:
        Leverage with ``good=1.0``, ``bad=2.0``: 1.0 scores 100, 1.5 scores 50,
        2.0 scores 0, and 3.0 clamps at 0.
    """
    val, good_d, bad_d = D(value), D(good), D(bad)

    span = good_d - bad_d if higher_is_better else bad_d - good_d
    if span == ZERO:
        # Degenerate band: anything at-or-better than the anchor is perfect.
        if higher_is_better:
            return _HUNDRED if val >= good_d else ZERO
        return _HUNDRED if val <= good_d else ZERO

    progress = (val - bad_d) / span if higher_is_better else (bad_d - val) / span
    return q4(clamp(progress, ZERO, ONE) * _HUNDRED)


def score_exposure(
    exposure: ExposureMetrics, config: AnalyticsConfig = DEFAULT_CONFIG
) -> ScoreComponent:
    """Score leverage.

    Driven by gross leverage against ``max_gross_leverage``. The zero-score
    anchor is 2x the threshold, so breaching the limit lands at 50 rather than
    0 - a breach is serious, not automatically fatal, and the override rules
    handle the genuinely fatal cases.
    """
    good = config.max_gross_leverage * Decimal("0.5")
    bad = config.max_gross_leverage * Decimal("2")
    score = band_score(exposure.gross_leverage, good=good, bad=bad)

    if exposure.gross_leverage <= good:
        rationale = (
            f"Gross leverage {exposure.gross_leverage}x is comfortably below the "
            f"{config.max_gross_leverage}x limit."
        )
    elif exposure.gross_leverage <= config.max_gross_leverage:
        rationale = (
            f"Gross leverage {exposure.gross_leverage}x is within the "
            f"{config.max_gross_leverage}x limit but no longer conservative."
        )
    else:
        rationale = (
            f"Gross leverage {exposure.gross_leverage}x breaches the "
            f"{config.max_gross_leverage}x limit; a shock is amplified against equity."
        )

    return ScoreComponent(
        name="exposure",
        raw_value=exposure.gross_leverage,
        score=score,
        weight=config.weight_exposure,
        contribution=q4(score * config.weight_exposure),
        rationale=rationale,
    )


def score_concentration(
    concentration: ConcentrationMetrics, config: AnalyticsConfig = DEFAULT_CONFIG
) -> ScoreComponent:
    """Score diversification.

    Scored on HHI, then penalised for a single oversized position. A book can
    have an acceptable HHI while still holding one dominant name, and that name
    is the risk.
    """
    good = config.max_hhi * Decimal("0.5")
    bad = config.max_hhi * Decimal("3")
    base = band_score(concentration.hhi, good=good, bad=bad)

    penalty = ZERO
    if concentration.top_position_weight > config.max_position_weight:
        excess = concentration.top_position_weight - config.max_position_weight
        # 100 points per unit of excess weight, capped at 25 so a single
        # oversized name degrades the score without erasing genuine breadth.
        penalty = min(Decimal("25"), q4(excess * _HUNDRED))

    score = q4(clamp(base - penalty, ZERO, _HUNDRED))

    rationale = (
        f"HHI {concentration.hhi} implies {concentration.effective_positions} "
        f"effective positions"
    )
    if penalty > ZERO:
        rationale += (
            f"; {concentration.largest_symbol} at {concentration.top_position_weight} "
            f"exceeds the {config.max_position_weight} single-name cap "
            f"(-{penalty} points)"
        )
    rationale += "."

    return ScoreComponent(
        name="concentration",
        raw_value=concentration.hhi,
        score=score,
        weight=config.weight_concentration,
        contribution=q4(score * config.weight_concentration),
        rationale=rationale,
    )


def score_drawdown(
    drawdown: DrawdownMetrics, config: AnalyticsConfig = DEFAULT_CONFIG
) -> ScoreComponent:
    """Score realised drawdown.

    With no history the component scores a neutral 50, not 100. A fresh account
    has not demonstrated resilience, and awarding a perfect score for absent
    data would let any new account claim maximum protection.
    """
    if drawdown.observations < 2:
        return ScoreComponent(
            name="drawdown",
            raw_value=ZERO,
            score=Decimal("50"),
            weight=config.weight_drawdown,
            contribution=q4(Decimal("50") * config.weight_drawdown),
            rationale=(
                "Insufficient equity history; scored neutral rather than "
                "assuming resilience that has not been demonstrated."
            ),
        )

    good = config.max_drawdown_tolerance * Decimal("0.33")
    bad = config.max_drawdown_tolerance * Decimal("2")
    base = band_score(drawdown.max_drawdown, good=good, bad=bad)

    # Being in a drawdown now is worse than having recovered from one.
    penalty = ZERO
    if drawdown.current_drawdown > config.critical_current_drawdown:
        excess = drawdown.current_drawdown - config.critical_current_drawdown
        penalty = min(Decimal("20"), q4(excess * _HUNDRED))

    score = q4(clamp(base - penalty, ZERO, _HUNDRED))

    rationale = (
        f"Max drawdown {drawdown.max_drawdown} against a "
        f"{config.max_drawdown_tolerance} tolerance"
    )
    if penalty > ZERO:
        rationale += (
            f"; currently {drawdown.current_drawdown} below peak and needs "
            f"{drawdown.recovery_needed} to recover (-{penalty} points)"
        )
    rationale += "."

    return ScoreComponent(
        name="drawdown",
        raw_value=drawdown.max_drawdown,
        score=score,
        weight=config.weight_drawdown,
        contribution=q4(score * config.weight_drawdown),
        rationale=rationale,
    )


def score_hedge(
    risk: RiskAssessment,
    best: Optional[HedgeEvaluation],
    config: AnalyticsConfig = DEFAULT_CONFIG,
) -> ScoreComponent:
    """Score protection actually in place.

    With no viable hedge, the score is derived from how survivable the unhedged
    stress loss is - an unlevered all-cash book is genuinely protected without
    buying anything, and should not be punished for declining to.

    With a hedge, the score reflects coverage of the stress loss, adjusted for
    cost: protection bought at a punitive premium is not full protection.
    """
    if best is None or not best.is_viable:
        score = band_score(
            risk.stress_loss_pct,
            good=config.max_stress_loss_pct * Decimal("0.25"),
            bad=config.max_stress_loss_pct * Decimal("1.5"),
        )
        rationale = (
            f"No viable hedge accepted; unhedged {risk.scenario_name} loss is "
            f"{risk.stress_loss_pct} of equity."
        )
        raw = risk.stress_loss_pct
    else:
        coverage_score = band_score(best.coverage_of_stress, good=ONE, bad=ZERO,
                                    higher_is_better=True)
        cost_score = band_score(best.premium_bps, good=ZERO, bad=config.max_premium_bps)
        # 75/25 split: coverage is the point of a hedge, price is the constraint.
        score = q4(coverage_score * Decimal("0.75") + cost_score * Decimal("0.25"))
        rationale = (
            f"{best.provider} covers {best.coverage_of_stress} of the stress loss "
            f"at {best.premium_bps}bps, leaving {best.residual_loss} residual."
        )
        raw = best.coverage_of_stress

    return ScoreComponent(
        name="hedge",
        raw_value=raw,
        score=score,
        weight=config.weight_hedge,
        contribution=q4(score * config.weight_hedge),
        rationale=rationale,
    )


def _build_flags(
    exposure: ExposureMetrics,
    concentration: ConcentrationMetrics,
    drawdown: DrawdownMetrics,
    risk: RiskAssessment,
    config: AnalyticsConfig,
) -> Tuple[RiskFlag, ...]:
    """Emit machine-readable flags for every breached threshold.

    Flags are additive to the score, not a substitute for it: the score says how
    protected the book is, the flags say precisely what to fix.
    """
    flags: List[RiskFlag] = []

    if exposure.gross_leverage > config.max_gross_leverage:
        flags.append(
            RiskFlag(
                code="LEVERAGE_BREACH",
                severity=(
                    Severity.CRITICAL
                    if exposure.gross_leverage > config.max_gross_leverage * Decimal("1.5")
                    else Severity.WARNING
                ),
                message=(
                    f"Gross leverage {exposure.gross_leverage}x exceeds the "
                    f"{config.max_gross_leverage}x limit."
                ),
                metric="gross_leverage",
                value=exposure.gross_leverage,
                threshold=config.max_gross_leverage,
            )
        )

    if abs(exposure.net_leverage) > config.max_net_leverage:
        flags.append(
            RiskFlag(
                code="DIRECTIONAL_BREACH",
                severity=Severity.WARNING,
                message=(
                    f"Net directional leverage {exposure.net_leverage}x exceeds the "
                    f"{config.max_net_leverage}x limit."
                ),
                metric="net_leverage",
                value=exposure.net_leverage,
                threshold=config.max_net_leverage,
            )
        )

    if concentration.top_position_weight > config.max_position_weight:
        flags.append(
            RiskFlag(
                code="POSITION_CONCENTRATION",
                severity=(
                    Severity.CRITICAL
                    if concentration.top_position_weight > config.max_position_weight * Decimal("2")
                    else Severity.WARNING
                ),
                message=(
                    f"{concentration.largest_symbol} is "
                    f"{concentration.top_position_weight} of gross exposure, above "
                    f"the {config.max_position_weight} cap."
                ),
                metric="top_position_weight",
                value=concentration.top_position_weight,
                threshold=config.max_position_weight,
            )
        )

    if concentration.top_sector_weight > config.max_sector_weight:
        flags.append(
            RiskFlag(
                code="SECTOR_CONCENTRATION",
                severity=Severity.WARNING,
                message=(
                    f"Sector '{concentration.top_sector}' is "
                    f"{concentration.top_sector_weight} of gross exposure, above the "
                    f"{config.max_sector_weight} cap."
                ),
                metric="top_sector_weight",
                value=concentration.top_sector_weight,
                threshold=config.max_sector_weight,
            )
        )

    if concentration.hhi > config.max_hhi:
        flags.append(
            RiskFlag(
                code="LOW_DIVERSIFICATION",
                severity=Severity.INFO,
                message=(
                    f"HHI {concentration.hhi} implies only "
                    f"{concentration.effective_positions} effective positions."
                ),
                metric="hhi",
                value=concentration.hhi,
                threshold=config.max_hhi,
            )
        )

    if drawdown.observations >= 2 and drawdown.max_drawdown > config.max_drawdown_tolerance:
        flags.append(
            RiskFlag(
                code="DRAWDOWN_BREACH",
                severity=Severity.WARNING,
                message=(
                    f"Max drawdown {drawdown.max_drawdown} exceeds the "
                    f"{config.max_drawdown_tolerance} tolerance."
                ),
                metric="max_drawdown",
                value=drawdown.max_drawdown,
                threshold=config.max_drawdown_tolerance,
            )
        )

    if not risk.survives_stress:
        flags.append(
            RiskFlag(
                code="STRESS_FAILURE",
                severity=Severity.CRITICAL,
                message=(
                    f"A {risk.scenario_name} shock costs {risk.stress_loss_pct} of "
                    f"equity, beyond the {config.max_stress_loss_pct} survival limit."
                ),
                metric="stress_loss_pct",
                value=risk.stress_loss_pct,
                threshold=config.max_stress_loss_pct,
            )
        )

    return sort_flags(flags)


def _apply_overrides(
    total: Decimal, flags: Sequence[RiskFlag], config: AnalyticsConfig
) -> Decimal:
    """Cap the total score when a single dimension is critical.

    This is the guard against the central weakness of weighted averages: three
    healthy components should not be able to launder one fatal one. A book that
    cannot survive its own stress scenario is not "acceptable" no matter how
    well diversified it is.
    """
    critical = [f for f in flags if f.severity is Severity.CRITICAL]
    if not critical:
        return total

    # Never better than the top of the "exposed" band while a critical flag stands.
    ceiling = config.score_acceptable - Decimal("0.01")
    if any(f.code == "STRESS_FAILURE" for f in critical):
        ceiling = min(ceiling, config.score_exposed - Decimal("0.01"))
    return min(total, ceiling)


def grade_for(total: Decimal, config: AnalyticsConfig = DEFAULT_CONFIG) -> str:
    """Letter grade for the headline score - the UI's at-a-glance summary."""
    if total >= config.score_protected:
        return "A"
    if total >= config.score_acceptable:
        return "B"
    if total >= config.score_exposed:
        return "C"
    if total >= config.score_exposed / 2:
        return "D"
    return "F"


def _verdict_for(total: Decimal, config: AnalyticsConfig) -> Verdict:
    if total >= config.score_protected:
        return Verdict.PROTECTED
    if total >= config.score_acceptable:
        return Verdict.ACCEPTABLE
    if total >= config.score_exposed:
        return Verdict.EXPOSED
    return Verdict.CRITICAL


def compute_score(
    exposure: ExposureMetrics,
    concentration: ConcentrationMetrics,
    drawdown: DrawdownMetrics,
    risk: RiskAssessment,
    best_hedge: Optional[HedgeEvaluation] = None,
    config: AnalyticsConfig = DEFAULT_CONFIG,
) -> ProtectionScore:
    """Combine every component into the headline protection score.

    Returns:
        A :class:`~raptor.analytics.types.ProtectionScore` carrying the total,
        letter grade, verdict, per-component breakdown with rationales, and all
        risk flags. The breakdown is the deliverable, not just the total - it is
        what lets the control room explain the verdict instead of asserting it.
    """
    components = (
        score_exposure(exposure, config),
        score_concentration(concentration, config),
        score_drawdown(drawdown, config),
        score_hedge(risk, best_hedge, config),
    )

    raw_total = sum((c.contribution for c in components), ZERO)
    flags = _build_flags(exposure, concentration, drawdown, risk, config)
    total = q2(clamp(_apply_overrides(q4(raw_total), flags, config), ZERO, _HUNDRED))

    return ProtectionScore(
        total=total,
        grade=grade_for(total, config),
        verdict=_verdict_for(total, config),
        components=components,
        flags=flags,
    )
