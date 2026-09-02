"""The single entry point the rest of RaptorClick calls.

Everything else in this package is a pure function over typed inputs. This
module orchestrates them in a fixed order and returns one
:class:`~raptor.analytics.types.ProtectionReport`.

Why one façade
--------------
The backend (Issue #2) and the frontend mock layer (Issue #1) should not need to
know that concentration is computed before risk, or that the hedge auction runs
before scoring. They call :func:`analyse` and get a complete report. That keeps
the integration surface to exactly one function and one dataclass, which is what
makes "three branches that connect without a rewrite" achievable.

Determinism guarantee
---------------------
:func:`analyse` is a pure function of ``(snapshot, bids, config, generated_at)``.
It reads no clock, no environment, no global state. The one unavoidable
non-determinism - the report timestamp - is an injected parameter defaulting to
the snapshot's own timestamp rather than ``datetime.now()``. Two calls with the
same arguments produce byte-identical JSON, which is verified in
``tests/analytics/test_determinism.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from .config import DEFAULT_CONFIG, AnalyticsConfig
from .drawdown import compute_drawdown
from .exposure import compute_concentration, compute_exposure
from .hedge import assess_risk, evaluate_bids
from .scoring import compute_score
from .types import (
    SCHEMA_VERSION,
    HedgeBid,
    PortfolioSnapshot,
    ProtectionReport,
)

__all__ = ["analyse", "analyze"]


def analyse(
    snapshot: PortfolioSnapshot,
    bids: Sequence[HedgeBid] = (),
    config: AnalyticsConfig = DEFAULT_CONFIG,
    generated_at: Optional[datetime] = None,
) -> ProtectionReport:
    """Run the full analytics pipeline over a portfolio snapshot.

    Pipeline order (each step consumes the previous):

    1. Exposure - how much market is held.
    2. Concentration - how few places it sits in.
    3. Drawdown - what pain the curve has already taken.
    4. Risk - what a defined shock costs, using 1 and 2.
    5. Hedge auction - rank competing bids against 4.
    6. Score - combine everything into a verdict.

    Args:
        snapshot: validated portfolio state.
        bids: competing hedge offers. Empty is valid - the report then measures
            unhedged risk, which is the honest baseline.
        config: thresholds and weights.
        generated_at: report timestamp. Defaults to the snapshot's timestamp so
            the function stays pure; pass an explicit value only when you want
            wall-clock provenance.

    Returns:
        A complete :class:`~raptor.analytics.types.ProtectionReport`.

    Example:
        >>> report = analyse(snapshot, bids)
        >>> report.score.verdict
        <Verdict.ACCEPTABLE: 'acceptable'>
        >>> report.recommended_bid_id
        'bid-002'
    """
    exposure = compute_exposure(snapshot)
    concentration = compute_concentration(snapshot)
    drawdown = compute_drawdown(snapshot)

    risk = assess_risk(snapshot, exposure, concentration, config)

    evaluations = evaluate_bids(bids, risk, exposure, config)
    # evaluate_bids returns viable bids first, so the head is the winner when
    # it is viable. If it is not, no bid cleared the gates and we recommend none
    # rather than the "least bad" option - recommending a hedge that fails its
    # own viability test would undermine the entire verdict.
    best = evaluations[0] if evaluations and evaluations[0].is_viable else None

    score = compute_score(exposure, concentration, drawdown, risk, best, config)

    return ProtectionReport(
        schema_version=SCHEMA_VERSION,
        account_id=snapshot.account_id,
        generated_at=generated_at or snapshot.timestamp,
        exposure=exposure,
        concentration=concentration,
        drawdown=drawdown,
        risk=risk,
        score=score,
        hedge_evaluations=evaluations,
        recommended_bid_id=best.bid_id if best else None,
    )


#: US spelling alias. Costs nothing and avoids a mixed-spelling codebase
#: argument in review.
analyze = analyse
