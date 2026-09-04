"""Protected-versus-unprotected counterfactual calculations."""

from __future__ import annotations

from ._num import ZERO, q2, q4, safe_div
from .hedge import hedge_payout
from .types import HedgeBid, RiskAssessment, ShadowComparison

__all__ = ["compare_shadow_book"]


def compare_shadow_book(bid: HedgeBid, risk: RiskAssessment) -> ShadowComparison:
    """Compare one hedge with the same portfolio left unprotected.

    Protection Delta is loss avoided after premium: ``payout - premium``. It
    can be negative, which honestly identifies a hedge that costs more than it
    contributes in the named scenario.
    """
    payout = hedge_payout(bid, risk.stress_loss)
    protected_loss = q2(max(ZERO, risk.stress_loss - payout) + bid.premium)
    delta = q2(risk.stress_loss - protected_loss)
    delta_pct = (
        q4(safe_div(delta, risk.stress_loss)) if risk.stress_loss > ZERO else None
    )
    return ShadowComparison(
        bid_id=bid.bid_id,
        scenario_name=risk.scenario_name,
        unprotected_loss=risk.stress_loss,
        hedge_payout=payout,
        hedge_cost=bid.premium,
        protected_loss=protected_loss,
        protection_delta=delta,
        protection_delta_pct=delta_pct,
    )
