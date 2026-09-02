"""Deterministic sample data for demos, tests and frontend mocks.

Every fixture is a hand-built portfolio with a specific teaching purpose, so a
reviewer can see the model respond to a named condition rather than to noise:

* :func:`balanced_portfolio` - healthy, diversified, low leverage.
* :func:`concentrated_portfolio` - one name dominates; isolates the HHI path.
* :func:`levered_portfolio` - breaches leverage and fails the stress test.
* :func:`market_neutral_portfolio` - near-zero net exposure but concentrated,
  which is the case a naive directional model scores as safe and this one does
  not.
* :func:`empty_portfolio` - all cash; the boundary case.

Timestamps are fixed constants, never ``datetime.now()``. A fixture that changes
with the wall clock is not a fixture.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Tuple

from .types import (
    AssetClass,
    EquityPoint,
    HedgeBid,
    HedgeInstrument,
    PortfolioSnapshot,
    Position,
)

__all__ = [
    "FIXED_TIME",
    "balanced_portfolio",
    "concentrated_portfolio",
    "levered_portfolio",
    "market_neutral_portfolio",
    "empty_portfolio",
    "sample_bids",
    "equity_curve",
]

#: Anchor for every fixture. Fixed so golden files never drift.
FIXED_TIME = datetime(2025, 8, 31, 13, 0, 0, tzinfo=timezone.utc)


def equity_curve(
    start: Decimal = Decimal("100000"),
    moves: Tuple[str, ...] = (
        "0.02", "0.015", "-0.01", "0.03", "-0.025", "-0.04",
        "0.01", "0.02", "-0.015", "0.025", "0.01", "-0.005",
    ),
    origin: datetime = FIXED_TIME - timedelta(days=12),
) -> List[EquityPoint]:
    """Build a deterministic equity curve from fractional daily moves.

    The default series contains a genuine peak-to-trough decline followed by a
    partial recovery, so drawdown, current drawdown and recovery are all
    exercised by one fixture.
    """
    points = [EquityPoint(timestamp=origin, equity=start)]
    equity = start
    for index, move in enumerate(moves, start=1):
        equity = equity * (Decimal("1") + Decimal(move))
        points.append(
            EquityPoint(timestamp=origin + timedelta(days=index), equity=equity)
        )
    return points


def balanced_portfolio() -> PortfolioSnapshot:
    """Diversified, unlevered, healthy. The 'good' reference case."""
    positions = [
        Position("AAPL", 100, "185.50", sector="technology"),
        Position("MSFT", 60, "410.20", sector="technology"),
        Position("JNJ", 120, "155.75", sector="healthcare"),
        Position("JPM", 90, "198.40", sector="financials"),
        Position("XOM", 150, "112.30", sector="energy"),
        Position("PG", 110, "165.90", sector="consumer_staples"),
        Position("SPY", 40, "545.00", sector="broad_market",
                 asset_class=AssetClass.ETF, beta="1.0"),
    ]
    gross = sum(p.exposure for p in positions)
    cash = Decimal("40000")
    return PortfolioSnapshot(
        account_id="demo-balanced",
        timestamp=FIXED_TIME,
        cash=cash,
        equity=gross + cash,
        positions=positions,
        buying_power=cash * 2,
        history=equity_curve(),
    )


def concentrated_portfolio() -> PortfolioSnapshot:
    """One name dominates. Isolates concentration from every other factor."""
    positions = [
        Position("NVDA", 900, "128.40", sector="technology", beta="1.75"),
        Position("AAPL", 40, "185.50", sector="technology"),
        Position("MSFT", 20, "410.20", sector="technology"),
    ]
    gross = sum(p.exposure for p in positions)
    cash = Decimal("15000")
    return PortfolioSnapshot(
        account_id="demo-concentrated",
        timestamp=FIXED_TIME,
        cash=cash,
        equity=gross + cash,
        positions=positions,
        history=equity_curve(),
    )


def levered_portfolio() -> PortfolioSnapshot:
    """Gross exposure far above equity. Should breach and fail the stress test."""
    positions = [
        Position("TSLA", 400, "245.60", sector="consumer_discretionary", beta="2.1"),
        Position("NVDA", 500, "128.40", sector="technology", beta="1.75"),
        Position("AMD", 600, "142.80", sector="technology", beta="1.9"),
        Position("COIN", 300, "215.30", sector="financials", beta="3.2"),
    ]
    # Equity well below gross exposure: the definition of leverage.
    return PortfolioSnapshot(
        account_id="demo-levered",
        timestamp=FIXED_TIME,
        cash=Decimal("-120000"),
        equity=Decimal("180000"),
        positions=positions,
        history=equity_curve(start=Decimal("250000")),
    )


def market_neutral_portfolio() -> PortfolioSnapshot:
    """Longs and shorts roughly offset, but the book is concentrated.

    The instructive case: net exposure is near zero, so a purely directional
    model calls this safe. Concentration plus correlation uplift is what reveals
    the real risk.
    """
    positions = [
        Position("AAPL", 300, "185.50", sector="technology"),
        Position("MSFT", 140, "410.20", sector="technology"),
        Position("QQQ", -160, "480.25", sector="technology",
                 asset_class=AssetClass.ETF, beta="1.15"),
    ]
    return PortfolioSnapshot(
        account_id="demo-neutral",
        timestamp=FIXED_TIME,
        cash=Decimal("95000"),
        equity=Decimal("125000"),
        positions=positions,
        history=equity_curve(start=Decimal("125000")),
    )


def empty_portfolio() -> PortfolioSnapshot:
    """All cash, no positions. Boundary case for every divide."""
    return PortfolioSnapshot(
        account_id="demo-empty",
        timestamp=FIXED_TIME,
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        positions=[],
        history=[],
    )


def sample_bids(notional: Decimal = Decimal("150000")) -> List[HedgeBid]:
    """Five competing bids spanning the interesting corners of the auction.

    Included on purpose:
        * a fairly-priced put (should usually win),
        * a capped put spread (cheaper, less protection),
        * an overpriced put (rejected on premium),
        * a token hedge (rejected on coverage),
        * a zero-premium cash reserve (exercises the divide-by-zero path).
    """
    return [
        HedgeBid(
            bid_id="bid-001",
            provider="AtlasHedge",
            instrument=HedgeInstrument.PUT,
            notional=notional,
            premium=notional * Decimal("0.012"),
            coverage_ratio="0.90",
            buffer_pct="0.03",
            expiry_days=30,
        ),
        HedgeBid(
            bid_id="bid-002",
            provider="MeridianRisk",
            instrument=HedgeInstrument.PUT_SPREAD,
            notional=notional,
            premium=notional * Decimal("0.007"),
            coverage_ratio="0.85",
            buffer_pct="0.05",
            max_payout=notional * Decimal("0.15"),
            expiry_days=30,
        ),
        HedgeBid(
            bid_id="bid-003",
            provider="ApexCover",
            instrument=HedgeInstrument.PUT,
            notional=notional,
            premium=notional * Decimal("0.035"),
            coverage_ratio="0.95",
            buffer_pct="0.02",
            expiry_days=45,
        ),
        HedgeBid(
            bid_id="bid-004",
            provider="ThinShield",
            instrument=HedgeInstrument.INVERSE_ETF,
            notional=notional * Decimal("0.25"),
            premium=notional * Decimal("0.002"),
            coverage_ratio="0.30",
            buffer_pct="0.10",
            expiry_days=30,
        ),
        HedgeBid(
            bid_id="bid-005",
            provider="VaultReserve",
            instrument=HedgeInstrument.CASH_RESERVE,
            notional=notional * Decimal("0.20"),
            premium=Decimal("0"),
            coverage_ratio="1.00",
            buffer_pct="0.00",
            expiry_days=90,
        ),
    ]
