"""Exposure and concentration metrics.

Two questions, answered deterministically:

* **Exposure** - how much market is this book actually holding? Gross, net,
  long, short, beta-adjusted, and the leverage ratios derived from them.
* **Concentration** - how much of that exposure sits in too few places?
  Herfindahl-Hirschman index, effective position count, top-N weights and
  sector clustering.

Why concentration is not an afterthought here
---------------------------------------------
Concentration is what makes a stress loss non-linear. Two books with identical
gross exposure behave completely differently in a crash if one is ten names and
the other is one. :mod:`raptor.analytics.hedge` feeds HHI straight into the
idiosyncratic loss term, so this module is upstream of the verdict, not just a
display metric.

All weights are computed against **gross** exposure, never net. Net can be zero
for a market-neutral book that is nonetheless enormously concentrated, and
dividing by it would either explode or silently report zero risk.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Mapping, Sequence

from ._num import ZERO, D, dsum, q4, safe_div
from .types import ConcentrationMetrics, ExposureMetrics, PortfolioSnapshot, Position

__all__ = [
    "compute_exposure",
    "compute_concentration",
    "position_weights",
    "sector_weights",
    "herfindahl_index",
]


def compute_exposure(snapshot: PortfolioSnapshot) -> ExposureMetrics:
    """Compute the exposure profile of a snapshot.

    Definitions:
        gross = sum of |market value| - total capital at risk.
        net = sum of signed market value - directional tilt.
        beta-adjusted net = sum of signed value x beta - true market
            sensitivity, and the number the stress test actually uses.

    An empty portfolio returns all-zero metrics with ``cash_ratio`` of 1, which
    is the correct answer rather than an error: 100% cash is a valid, maximally
    protected state.
    """
    positions = snapshot.positions

    long_exposure = dsum(p.market_value for p in positions if p.quantity > ZERO)
    short_exposure = dsum(
        abs(p.market_value) for p in positions if p.quantity < ZERO
    )
    gross = long_exposure + short_exposure
    net = long_exposure - short_exposure
    beta_adjusted = dsum(p.beta_adjusted_exposure for p in positions)

    equity = snapshot.equity

    # Leverage is undefined without equity. Zero is the honest report; the
    # scoring layer raises a separate flag for a zero-equity account.
    gross_leverage = safe_div(gross, equity)
    net_leverage = safe_div(net, equity)
    cash_ratio = safe_div(snapshot.cash, equity)

    # None rather than infinity for a book with no shorts - the frontend can
    # render "n/a" instead of a misleading number.
    long_short_ratio = (
        q4(safe_div(long_exposure, short_exposure)) if short_exposure > ZERO else None
    )

    return ExposureMetrics(
        gross_exposure=q4(gross),
        net_exposure=q4(net),
        long_exposure=q4(long_exposure),
        short_exposure=q4(short_exposure),
        beta_adjusted_exposure=q4(beta_adjusted),
        gross_leverage=q4(gross_leverage),
        net_leverage=q4(net_leverage),
        cash_ratio=q4(cash_ratio),
        position_count=len(positions),
        long_short_ratio=long_short_ratio,
    )


def position_weights(positions: Sequence[Position]) -> Dict[str, Decimal]:
    """Weight of each position as a fraction of gross exposure.

    Returns a dict keyed by symbol. Weights sum to 1 (within quantisation
    tolerance) whenever gross exposure is non-zero.
    """
    gross = dsum(p.exposure for p in positions)
    if gross == ZERO:
        return {}
    return {p.symbol: q4(safe_div(p.exposure, gross)) for p in positions}


def sector_weights(positions: Sequence[Position]) -> Dict[str, Decimal]:
    """Aggregate exposure weight by sector.

    Sector labels are normalised to lower case by :class:`Position`, so
    "Tech" and "tech" aggregate together rather than appearing as two
    artificially smaller buckets.
    """
    gross = dsum(p.exposure for p in positions)
    if gross == ZERO:
        return {}
    totals: Dict[str, Decimal] = {}
    for pos in positions:
        totals[pos.sector] = totals.get(pos.sector, ZERO) + pos.exposure
    return {sector: q4(safe_div(value, gross)) for sector, value in totals.items()}


def herfindahl_index(weights: Mapping[str, Decimal]) -> Decimal:
    """Herfindahl-Hirschman index: the sum of squared weights.

    Interpretation:
        1/n for n equal-weight positions, so a 10-name equal book scores 0.10.
        1.0 for a single position.
        Its reciprocal is the "effective number of positions" - the count of
        equal-weight holdings that would carry the same concentration.

    HHI is used instead of a simple position count because it is
    size-sensitive: a book of twenty names where one is 80% is concentrated,
    and a naive count would call it diversified.
    """
    if not weights:
        return ZERO
    return q4(dsum(D(w) * D(w) for w in weights.values()))


def compute_concentration(snapshot: PortfolioSnapshot) -> ConcentrationMetrics:
    """Compute the concentration profile of a snapshot.

    Ties in the top-N ranking are broken by symbol so that two positions of
    identical size always produce the same ordering, and therefore the same
    ``largest_symbol``, on every run.
    """
    positions = snapshot.positions
    weights = position_weights(positions)

    if not weights:
        return ConcentrationMetrics(
            hhi=ZERO,
            effective_positions=ZERO,
            top_position_weight=ZERO,
            top_3_weight=ZERO,
            top_5_weight=ZERO,
            largest_symbol=None,
            sector_weights={},
            top_sector=None,
            top_sector_weight=ZERO,
        )

    # Descending by weight, ascending by symbol for deterministic tie-breaks.
    ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
    ordered_weights = [w for _, w in ranked]

    hhi = herfindahl_index(weights)
    effective = q4(safe_div(Decimal("1"), hhi)) if hhi > ZERO else ZERO

    sectors = sector_weights(positions)
    top_sector, top_sector_weight = (None, ZERO)
    if sectors:
        top_sector, top_sector_weight = sorted(
            sectors.items(), key=lambda kv: (-kv[1], kv[0])
        )[0]

    return ConcentrationMetrics(
        hhi=hhi,
        effective_positions=effective,
        top_position_weight=ordered_weights[0],
        top_3_weight=q4(dsum(ordered_weights[:3])),
        top_5_weight=q4(dsum(ordered_weights[:5])),
        largest_symbol=ranked[0][0],
        sector_weights=sectors,
        top_sector=top_sector,
        top_sector_weight=q4(top_sector_weight),
    )
