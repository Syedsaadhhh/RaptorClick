"""Typed domain models for the RaptorClick analytics layer.

Design notes
------------
* Every model is a frozen dataclass. Analytics inputs are snapshots of a moment
  in time; letting a caller mutate a ``Position`` after a metric was computed
  is a whole class of bug we simply delete by construction.
* Validation happens in ``__post_init__``. An invalid object cannot exist, so
  the calculation modules never re-check their inputs.
* Money and ratios are ``Decimal``. Constructors accept int/float/str and
  coerce through :func:`raptor.analytics._num.D`, so the backend can hand over
  raw Alpaca JSON without pre-converting anything.
* Every output model exposes ``to_dict()`` returning JSON-native types. This is
  the seam between analytics and both other workstreams: the frontend (Issue #1)
  builds mocks from it, the backend (Issue #2) serialises it onto the event bus.

Input models:  :class:`Position`, :class:`EquityPoint`, :class:`PriceBar`,
:class:`PortfolioSnapshot`, :class:`HedgeBid`.
Output models: :class:`ExposureMetrics`, :class:`ConcentrationMetrics`,
:class:`DrawdownMetrics`, :class:`RiskAssessment`, :class:`HedgeEvaluation`,
:class:`ScoreComponent`, :class:`ProtectionScore`, :class:`ProtectionReport`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ._num import D, Numeric, ZERO, q2, q4
from .errors import ValidationError

__all__ = [
    "SCHEMA_VERSION",
    "Side",
    "AssetClass",
    "HedgeInstrument",
    "Verdict",
    "Severity",
    "MetricStatus",
    "Position",
    "EquityPoint",
    "PriceBar",
    "PortfolioSnapshot",
    "HedgeBid",
    "ExposureMetrics",
    "ConcentrationMetrics",
    "DrawdownMetrics",
    "RiskAssessment",
    "HedgeEvaluation",
    "VolatilityEstimate",
    "VolatilityMetrics",
    "LiquidityAssessment",
    "ShadowComparison",
    "DriftAssessment",
    "RiskFlag",
    "ScoreComponent",
    "ProtectionScore",
    "ProtectionReport",
]

#: Bump on any breaking change to the JSON contract. The frontend pins this and
#: the backend echoes it on every event, so a mismatch is caught at the seam
#: rather than in a demo.
SCHEMA_VERSION = "1.1.0"

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,15}$")


def _dec_str(value: Decimal) -> str:
    """Serialise a Decimal losslessly.

    Strings, not floats. ``float(Decimal("0.1"))`` round-trips today and bites
    you the moment a number crosses a JS boundary - and this payload is headed
    straight for a React frontend.
    """
    return format(value, "f")


def _require_symbol(symbol: str, label: str = "symbol") -> str:
    if not isinstance(symbol, str):
        raise ValidationError(f"{label} must be a string, got {type(symbol).__name__}")
    cleaned = symbol.strip().upper()
    if not _SYMBOL_RE.match(cleaned):
        raise ValidationError(
            f"{label} {symbol!r} is not a valid ticker "
            "(expected 1-16 chars of A-Z, 0-9, dot, dash or underscore)"
        )
    return cleaned


class Side(str, Enum):
    """Direction of a position. ``str`` mixin keeps JSON output readable."""

    LONG = "long"
    SHORT = "short"


class AssetClass(str, Enum):
    """Asset class, used for cross-asset concentration."""

    EQUITY = "equity"
    ETF = "etf"
    CRYPTO = "crypto"
    OPTION = "option"
    CASH = "cash"


class HedgeInstrument(str, Enum):
    """The shape of protection a bid offers.

    Drives the payoff model in :mod:`raptor.analytics.hedge`. A put spread caps
    out; an inverse ETF does not. Collapsing these into one linear model would
    make the auction rank bids on price alone, which is exactly the naive
    behaviour RaptorClick is meant to beat.
    """

    PUT = "put"
    PUT_SPREAD = "put_spread"
    COLLAR = "collar"
    INVERSE_ETF = "inverse_etf"
    FUTURES = "futures"
    CASH_RESERVE = "cash_reserve"


class Verdict(str, Enum):
    """Final deterministic recommendation."""

    PROTECTED = "protected"
    ACCEPTABLE = "acceptable"
    EXPOSED = "exposed"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Risk-flag severity. Ordered low to high for stable sorting."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MetricStatus(str, Enum):
    """Whether a calculation had enough trustworthy source data."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INCONCLUSIVE = "inconclusive"


_SEVERITY_RANK: Mapping[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


# --------------------------------------------------------------------------- #
# Input models
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, init=False)
class Position:
    """A single open position in the portfolio.

    Args:
        symbol: ticker, normalised to upper case.
        quantity: signed size. Negative means short; ``side`` is derived from
            the sign so the two can never contradict each other.
        market_value: signed current value. Defaults to
            ``quantity * current_price``, which is what Alpaca reports.
        cost_basis: total entry cost. Optional; enables unrealised P&L.
        beta: sensitivity to the market factor. Defaults to 1.0 - assuming a
            position moves with the market is the conservative choice when we
            have no better estimate.
        sector: free-text sector label for concentration analysis.
        asset_class: see :class:`AssetClass`.

    Raises:
        ValidationError: on a bad symbol, non-positive price, zero quantity, or
            a market value whose sign contradicts the quantity.
    """

    symbol: str
    quantity: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Optional[Decimal] = None
    beta: Decimal = Decimal("1")
    sector: str = "unclassified"
    asset_class: AssetClass = AssetClass.EQUITY

    def __init__(
        self,
        symbol: str,
        quantity: Numeric,
        current_price: Numeric,
        market_value: Optional[Numeric] = None,
        cost_basis: Optional[Numeric] = None,
        beta: Numeric = Decimal("1"),
        sector: str = "unclassified",
        asset_class: AssetClass = AssetClass.EQUITY,
    ) -> None:
        object.__setattr__(self, "symbol", _require_symbol(symbol))
        qty = D(quantity)
        price = D(current_price)

        if qty == ZERO:
            raise ValidationError(
                f"{self.symbol}: quantity cannot be zero - a closed position "
                "should be omitted from the snapshot, not sent as zero"
            )
        if price <= ZERO:
            raise ValidationError(
                f"{self.symbol}: current_price must be positive, got {price}"
            )

        mv = qty * price if market_value is None else D(market_value)
        if (qty > ZERO) != (mv > ZERO):
            raise ValidationError(
                f"{self.symbol}: market_value {mv} contradicts quantity {qty}; "
                "a long position cannot have negative market value"
            )

        object.__setattr__(self, "quantity", q4(qty))
        object.__setattr__(self, "current_price", q4(price))
        object.__setattr__(self, "market_value", q2(mv))
        object.__setattr__(
            self, "cost_basis", None if cost_basis is None else q2(cost_basis)
        )
        object.__setattr__(self, "beta", q4(beta))
        object.__setattr__(self, "sector", (sector or "unclassified").strip().lower())
        object.__setattr__(self, "asset_class", AssetClass(asset_class))

    @property
    def side(self) -> Side:
        """Derived from the sign of ``quantity`` - never stored separately."""
        return Side.LONG if self.quantity > ZERO else Side.SHORT

    @property
    def exposure(self) -> Decimal:
        """Absolute market value: how much of the book this position commands."""
        return abs(self.market_value)

    @property
    def beta_adjusted_exposure(self) -> Decimal:
        """Signed exposure scaled by beta - the market-factor contribution.

        A short keeps its negative sign here, which is the whole point: it is
        what lets a hedged book net down to a small directional number.
        """
        return q2(self.market_value * self.beta)

    @property
    def unrealised_pnl(self) -> Optional[Decimal]:
        """Unrealised P&L, or ``None`` when no cost basis was supplied."""
        if self.cost_basis is None:
            return None
        return q2(self.market_value - self.cost_basis)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": _dec_str(self.quantity),
            "current_price": _dec_str(self.current_price),
            "market_value": _dec_str(self.market_value),
            "cost_basis": None if self.cost_basis is None else _dec_str(self.cost_basis),
            "beta": _dec_str(self.beta),
            "sector": self.sector,
            "asset_class": self.asset_class.value,
            "exposure": _dec_str(self.exposure),
            "unrealised_pnl": (
                None if self.unrealised_pnl is None else _dec_str(self.unrealised_pnl)
            ),
        }


@dataclass(frozen=True, init=False)
class EquityPoint:
    """One observation on the account equity curve."""

    timestamp: datetime
    equity: Decimal

    def __init__(self, timestamp: datetime, equity: Numeric) -> None:
        if not isinstance(timestamp, datetime):
            raise ValidationError(
                f"timestamp must be a datetime, got {type(timestamp).__name__}"
            )
        # Naive datetimes are assumed UTC. Mixing naive and aware values raises
        # TypeError on comparison, which would surface as a confusing sort error
        # deep inside the drawdown scan rather than here at the boundary.
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        eq = D(equity)
        if eq < ZERO:
            raise ValidationError(f"equity cannot be negative, got {eq}")
        object.__setattr__(self, "timestamp", timestamp.astimezone(timezone.utc))
        object.__setattr__(self, "equity", q2(eq))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": _dec_str(self.equity),
        }


@dataclass(frozen=True, init=False)
class PriceBar:
    """One sanitized closing-price observation supplied by market data."""

    symbol: str
    timestamp: datetime
    close: Decimal

    def __init__(self, symbol: str, timestamp: datetime, close: Numeric) -> None:
        object.__setattr__(self, "symbol", _require_symbol(symbol))
        if not isinstance(timestamp, datetime):
            raise ValidationError("price-bar timestamp must be a datetime")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        close_d = D(close)
        if close_d <= ZERO:
            raise ValidationError(f"{self.symbol}: bar close must be positive, got {close_d}")
        object.__setattr__(self, "timestamp", timestamp.astimezone(timezone.utc))
        object.__setattr__(self, "close", q4(close_d))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "close": _dec_str(self.close),
        }


@dataclass(frozen=True, init=False)
class PortfolioSnapshot:
    """Complete account state at one instant - the primary analytics input.

    Args:
        account_id: Alpaca account identifier.
        timestamp: when the snapshot was taken (UTC).
        cash: settled cash. May be negative on margin.
        equity: total account equity (cash + positions).
        positions: open positions. Stored sorted by symbol so that iteration
            order - and therefore every downstream sum - is independent of the
            order the backend happened to fetch them in.
        buying_power: optional, informational.
        history: optional equity curve for drawdown analysis.
        price_bars: optional sanitized market closes for historical volatility.

    Raises:
        ValidationError: on negative equity, duplicate symbols, or unsorted
            history.
    """

    account_id: str
    timestamp: datetime
    cash: Decimal
    equity: Decimal
    positions: Tuple[Position, ...]
    buying_power: Optional[Decimal] = None
    history: Tuple[EquityPoint, ...] = field(default_factory=tuple)
    price_bars: Tuple[PriceBar, ...] = field(default_factory=tuple)

    def __init__(
        self,
        account_id: str,
        timestamp: datetime,
        cash: Numeric,
        equity: Numeric,
        positions: Sequence[Position] = (),
        buying_power: Optional[Numeric] = None,
        history: Sequence[EquityPoint] = (),
        price_bars: Sequence[PriceBar] = (),
    ) -> None:
        if not account_id or not str(account_id).strip():
            raise ValidationError("account_id is required")
        if not isinstance(timestamp, datetime):
            raise ValidationError("timestamp must be a datetime")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        eq = D(equity)
        if eq < ZERO:
            raise ValidationError(
                f"equity cannot be negative, got {eq}; a blown-up account should "
                "be reported as zero equity with an explicit risk flag"
            )

        seen = set()
        for pos in positions:
            if not isinstance(pos, Position):
                raise ValidationError(
                    f"positions must contain Position instances, got "
                    f"{type(pos).__name__}"
                )
            if pos.symbol in seen:
                raise ValidationError(
                    f"duplicate position for {pos.symbol}; merge fills before "
                    "building the snapshot"
                )
            seen.add(pos.symbol)

        for point in history:
            if not isinstance(point, EquityPoint):
                raise ValidationError(
                    f"history must contain EquityPoint instances, got "
                    f"{type(point).__name__}"
                )

        for bar in price_bars:
            if not isinstance(bar, PriceBar):
                raise ValidationError(
                    f"price_bars must contain PriceBar instances, got "
                    f"{type(bar).__name__}"
                )

        object.__setattr__(self, "account_id", str(account_id).strip())
        object.__setattr__(self, "timestamp", timestamp.astimezone(timezone.utc))
        object.__setattr__(self, "cash", q2(cash))
        object.__setattr__(self, "equity", q2(eq))
        # Deterministic ordering, enforced once, here.
        object.__setattr__(
            self, "positions", tuple(sorted(positions, key=lambda p: p.symbol))
        )
        object.__setattr__(
            self, "buying_power", None if buying_power is None else q2(buying_power)
        )
        object.__setattr__(
            self, "history", tuple(sorted(history, key=lambda h: h.timestamp))
        )
        object.__setattr__(
            self,
            "price_bars",
            tuple(sorted(price_bars, key=lambda b: (b.symbol, b.timestamp))),
        )

    @property
    def is_empty(self) -> bool:
        """True when there are no open positions (all cash)."""
        return len(self.positions) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "account_id": self.account_id,
            "timestamp": self.timestamp.isoformat(),
            "cash": _dec_str(self.cash),
            "equity": _dec_str(self.equity),
            "buying_power": (
                None if self.buying_power is None else _dec_str(self.buying_power)
            ),
            "positions": [p.to_dict() for p in self.positions],
            "history": [h.to_dict() for h in self.history],
            "price_bars": [b.to_dict() for b in self.price_bars],
        }


@dataclass(frozen=True, init=False)
class HedgeBid:
    """A competing offer of downside protection in the hedge auction.

    Args:
        bid_id: unique identifier; also the deterministic tie-breaker.
        provider: name of the bidding agent.
        instrument: see :class:`HedgeInstrument`.
        notional: portfolio value the hedge covers.
        premium: upfront cost. Zero is allowed (a cash-reserve "hedge" is free
            but has an opportunity cost the scorer accounts for separately).
        coverage_ratio: fraction of a loss beyond the buffer that is offset.
        buffer_pct: loss the portfolio absorbs before protection engages - the
            deductible.
        max_payout: optional cap. Required for capped structures like spreads.
        expiry_days: tenor in days.
        quote_bid: current contract or conservative multi-leg bid.
        quote_ask: current contract or conservative multi-leg ask.
        volume: reported option volume; missing stays unavailable.
        open_interest: reported option open interest; missing stays unavailable.

    Raises:
        ValidationError: on negative notional/premium, a coverage ratio or
            buffer outside [0, 1], or a capped instrument with no cap.
    """

    bid_id: str
    provider: str
    instrument: HedgeInstrument
    notional: Decimal
    premium: Decimal
    coverage_ratio: Decimal
    buffer_pct: Decimal
    max_payout: Optional[Decimal] = None
    expiry_days: int = 30
    quote_bid: Optional[Decimal] = None
    quote_ask: Optional[Decimal] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None

    def __init__(
        self,
        bid_id: str,
        provider: str,
        instrument: HedgeInstrument,
        notional: Numeric,
        premium: Numeric,
        coverage_ratio: Numeric = Decimal("1"),
        buffer_pct: Numeric = ZERO,
        max_payout: Optional[Numeric] = None,
        expiry_days: int = 30,
        quote_bid: Optional[Numeric] = None,
        quote_ask: Optional[Numeric] = None,
        volume: Optional[int] = None,
        open_interest: Optional[int] = None,
    ) -> None:
        if not bid_id or not str(bid_id).strip():
            raise ValidationError("bid_id is required")
        if not provider or not str(provider).strip():
            raise ValidationError("provider is required")

        notional_d = D(notional)
        premium_d = D(premium)
        coverage = D(coverage_ratio)
        buffer_d = D(buffer_pct)

        if notional_d <= ZERO:
            raise ValidationError(f"{bid_id}: notional must be positive, got {notional_d}")
        if premium_d < ZERO:
            raise ValidationError(f"{bid_id}: premium cannot be negative, got {premium_d}")
        if not (ZERO <= coverage <= Decimal("1")):
            raise ValidationError(
                f"{bid_id}: coverage_ratio must be within [0, 1], got {coverage}"
            )
        if not (ZERO <= buffer_d <= Decimal("1")):
            raise ValidationError(
                f"{bid_id}: buffer_pct must be within [0, 1], got {buffer_d}"
            )
        if int(expiry_days) <= 0:
            raise ValidationError(f"{bid_id}: expiry_days must be positive")

        instrument = HedgeInstrument(instrument)
        capped = {HedgeInstrument.PUT_SPREAD, HedgeInstrument.COLLAR}
        if instrument in capped and max_payout is None:
            raise ValidationError(
                f"{bid_id}: {instrument.value} is a capped structure and requires "
                "max_payout; without it the payoff model would overstate protection"
            )
        if max_payout is not None and D(max_payout) <= ZERO:
            raise ValidationError(f"{bid_id}: max_payout must be positive when set")
        if volume is not None and int(volume) < 0:
            raise ValidationError(f"{bid_id}: volume cannot be negative")
        if open_interest is not None and int(open_interest) < 0:
            raise ValidationError(f"{bid_id}: open_interest cannot be negative")

        object.__setattr__(self, "bid_id", str(bid_id).strip())
        object.__setattr__(self, "provider", str(provider).strip())
        object.__setattr__(self, "instrument", instrument)
        object.__setattr__(self, "notional", q2(notional_d))
        object.__setattr__(self, "premium", q2(premium_d))
        object.__setattr__(self, "coverage_ratio", q4(coverage))
        object.__setattr__(self, "buffer_pct", q4(buffer_d))
        object.__setattr__(
            self, "max_payout", None if max_payout is None else q2(max_payout)
        )
        object.__setattr__(self, "expiry_days", int(expiry_days))
        object.__setattr__(
            self, "quote_bid", None if quote_bid is None else q4(quote_bid)
        )
        object.__setattr__(
            self, "quote_ask", None if quote_ask is None else q4(quote_ask)
        )
        object.__setattr__(self, "volume", None if volume is None else int(volume))
        object.__setattr__(
            self,
            "open_interest",
            None if open_interest is None else int(open_interest),
        )

    @property
    def premium_bps(self) -> Decimal:
        """Premium in basis points of notional - the cross-bid price yardstick.

        Comparing raw premiums is meaningless when bids cover different
        notionals; bps is the only fair unit for the auction.
        """
        from ._num import safe_div  # local import keeps module import order flat

        return q4(safe_div(self.premium, self.notional) * Decimal("10000"))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "bid_id": self.bid_id,
            "provider": self.provider,
            "instrument": self.instrument.value,
            "notional": _dec_str(self.notional),
            "premium": _dec_str(self.premium),
            "premium_bps": _dec_str(self.premium_bps),
            "coverage_ratio": _dec_str(self.coverage_ratio),
            "buffer_pct": _dec_str(self.buffer_pct),
            "max_payout": None if self.max_payout is None else _dec_str(self.max_payout),
            "expiry_days": self.expiry_days,
            "quote_bid": None if self.quote_bid is None else _dec_str(self.quote_bid),
            "quote_ask": None if self.quote_ask is None else _dec_str(self.quote_ask),
            "volume": self.volume,
            "open_interest": self.open_interest,
        }


# --------------------------------------------------------------------------- #
# Output models
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExposureMetrics:
    """How much market the portfolio is actually holding."""

    gross_exposure: Decimal
    net_exposure: Decimal
    long_exposure: Decimal
    short_exposure: Decimal
    beta_adjusted_exposure: Decimal
    gross_leverage: Decimal
    net_leverage: Decimal
    cash_ratio: Decimal
    position_count: int
    long_short_ratio: Optional[Decimal] = None
    symbol_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    sector_exposures: Mapping[str, Decimal] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "gross_exposure": _dec_str(self.gross_exposure),
            "net_exposure": _dec_str(self.net_exposure),
            "long_exposure": _dec_str(self.long_exposure),
            "short_exposure": _dec_str(self.short_exposure),
            "beta_adjusted_exposure": _dec_str(self.beta_adjusted_exposure),
            "gross_leverage": _dec_str(self.gross_leverage),
            "net_leverage": _dec_str(self.net_leverage),
            "cash_ratio": _dec_str(self.cash_ratio),
            "position_count": self.position_count,
            "long_short_ratio": (
                None if self.long_short_ratio is None else _dec_str(self.long_short_ratio)
            ),
            "symbol_exposures": {
                key: _dec_str(value)
                for key, value in sorted(self.symbol_exposures.items())
            },
            "sector_exposures": {
                key: _dec_str(value)
                for key, value in sorted(self.sector_exposures.items())
            },
        }


@dataclass(frozen=True)
class ConcentrationMetrics:
    """How much of the risk sits in too few places."""

    hhi: Decimal
    effective_positions: Decimal
    top_position_weight: Decimal
    top_3_weight: Decimal
    top_5_weight: Decimal
    largest_symbol: Optional[str]
    sector_weights: Mapping[str, Decimal]
    top_sector: Optional[str]
    top_sector_weight: Decimal

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "hhi": _dec_str(self.hhi),
            "effective_positions": _dec_str(self.effective_positions),
            "top_position_weight": _dec_str(self.top_position_weight),
            "top_3_weight": _dec_str(self.top_3_weight),
            "top_5_weight": _dec_str(self.top_5_weight),
            "largest_symbol": self.largest_symbol,
            # Sorted so the JSON payload is byte-identical between runs.
            "sector_weights": {
                k: _dec_str(v) for k, v in sorted(self.sector_weights.items())
            },
            "top_sector": self.top_sector,
            "top_sector_weight": _dec_str(self.top_sector_weight),
        }


@dataclass(frozen=True)
class DrawdownMetrics:
    """How much pain the equity curve has already taken."""

    max_drawdown: Decimal
    max_drawdown_value: Decimal
    current_drawdown: Decimal
    peak_equity: Decimal
    trough_equity: Decimal
    recovery_needed: Decimal
    ulcer_index: Decimal
    periods_under_water: int
    observations: int

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "max_drawdown": _dec_str(self.max_drawdown),
            "max_drawdown_value": _dec_str(self.max_drawdown_value),
            "current_drawdown": _dec_str(self.current_drawdown),
            "peak_equity": _dec_str(self.peak_equity),
            "trough_equity": _dec_str(self.trough_equity),
            "recovery_needed": _dec_str(self.recovery_needed),
            "ulcer_index": _dec_str(self.ulcer_index),
            "periods_under_water": self.periods_under_water,
            "observations": self.observations,
        }


@dataclass(frozen=True)
class RiskAssessment:
    """Forward-looking loss estimate for the unhedged book."""

    stress_loss: Decimal
    stress_loss_pct: Decimal
    directional_loss: Decimal
    idiosyncratic_loss: Decimal
    parametric_var: Decimal
    var_confidence: Decimal
    scenario_name: str
    scenario_shock: Decimal
    survives_stress: bool

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "stress_loss": _dec_str(self.stress_loss),
            "stress_loss_pct": _dec_str(self.stress_loss_pct),
            "directional_loss": _dec_str(self.directional_loss),
            "idiosyncratic_loss": _dec_str(self.idiosyncratic_loss),
            "parametric_var": _dec_str(self.parametric_var),
            "var_confidence": _dec_str(self.var_confidence),
            "scenario_name": self.scenario_name,
            "scenario_shock": _dec_str(self.scenario_shock),
            "survives_stress": self.survives_stress,
        }


@dataclass(frozen=True)
class VolatilityEstimate:
    """Historical volatility result for one supplied symbol."""

    symbol: str
    status: MetricStatus
    annualized_volatility: Optional[Decimal]
    observations: int
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation with no fabricated fallback."""
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "annualized_volatility": (
                None
                if self.annualized_volatility is None
                else _dec_str(self.annualized_volatility)
            ),
            "observations": self.observations,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class VolatilityMetrics:
    """Deterministic realized volatility calculated only from supplied bars."""

    status: MetricStatus
    annualization_periods: int
    estimates: Tuple[VolatilityEstimate, ...]
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "status": self.status.value,
            "annualization_periods": self.annualization_periods,
            "estimates": [estimate.to_dict() for estimate in self.estimates],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LiquidityAssessment:
    """Inspectable quote, spread, volume and open-interest checks for a bid."""

    status: MetricStatus
    score: Optional[Decimal]
    spread: Optional[Decimal]
    spread_pct: Optional[Decimal]
    volume: Optional[int]
    open_interest: Optional[int]
    passed: Optional[bool]
    reasons: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "status": self.status.value,
            "score": None if self.score is None else _dec_str(self.score),
            "spread": None if self.spread is None else _dec_str(self.spread),
            "spread_pct": (
                None if self.spread_pct is None else _dec_str(self.spread_pct)
            ),
            "volume": self.volume,
            "open_interest": self.open_interest,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ShadowComparison:
    """Protected outcome versus the unprotected Shadow Book."""

    bid_id: str
    scenario_name: str
    unprotected_loss: Decimal
    hedge_payout: Decimal
    hedge_cost: Decimal
    protected_loss: Decimal
    protection_delta: Decimal
    protection_delta_pct: Optional[Decimal]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "bid_id": self.bid_id,
            "scenario_name": self.scenario_name,
            "unprotected_loss": _dec_str(self.unprotected_loss),
            "hedge_payout": _dec_str(self.hedge_payout),
            "hedge_cost": _dec_str(self.hedge_cost),
            "protected_loss": _dec_str(self.protected_loss),
            "protection_delta": _dec_str(self.protection_delta),
            "protection_delta_pct": (
                None
                if self.protection_delta_pct is None
                else _dec_str(self.protection_delta_pct)
            ),
        }


@dataclass(frozen=True)
class DriftAssessment:
    """Decision explaining whether prior analytics must be re-auctioned."""

    is_stale: bool
    equity_drift: Decimal
    gross_exposure_drift: Decimal
    concentration_drift: Decimal
    symbols_changed: bool
    reasons: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "is_stale": self.is_stale,
            "equity_drift": _dec_str(self.equity_drift),
            "gross_exposure_drift": _dec_str(self.gross_exposure_drift),
            "concentration_drift": _dec_str(self.concentration_drift),
            "symbols_changed": self.symbols_changed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class HedgeEvaluation:
    """Scored assessment of one hedge bid against one risk picture."""

    bid_id: str
    provider: str
    instrument: HedgeInstrument
    premium: Decimal
    premium_bps: Decimal
    expected_payout: Decimal
    net_benefit: Decimal
    coverage_of_stress: Decimal
    cost_efficiency: Decimal
    residual_loss: Decimal
    notional_gap: Decimal
    maximum_risk: Decimal
    normalized_score: Decimal
    score_components: Tuple[ScoreComponent, ...]
    liquidity: LiquidityAssessment
    is_viable: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "bid_id": self.bid_id,
            "provider": self.provider,
            "instrument": self.instrument.value,
            "premium": _dec_str(self.premium),
            "premium_bps": _dec_str(self.premium_bps),
            "expected_payout": _dec_str(self.expected_payout),
            "net_benefit": _dec_str(self.net_benefit),
            "coverage_of_stress": _dec_str(self.coverage_of_stress),
            "cost_efficiency": _dec_str(self.cost_efficiency),
            "residual_loss": _dec_str(self.residual_loss),
            "notional_gap": _dec_str(self.notional_gap),
            "maximum_risk": _dec_str(self.maximum_risk),
            "normalized_score": _dec_str(self.normalized_score),
            "score_components": [component.to_dict() for component in self.score_components],
            "liquidity": self.liquidity.to_dict(),
            "is_viable": self.is_viable,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RiskFlag:
    """A named, machine-readable warning. The frontend renders these directly."""

    code: str
    severity: Severity
    message: str
    metric: str
    value: Decimal
    threshold: Decimal

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "metric": self.metric,
            "value": _dec_str(self.value),
            "threshold": _dec_str(self.threshold),
        }


@dataclass(frozen=True)
class ScoreComponent:
    """One weighted input to the protection score.

    ``rationale`` exists so the UI can explain *why* a score moved. A number
    with no explanation is not something a user will trust with their money.
    """

    name: str
    raw_value: Decimal
    score: Decimal
    weight: Decimal
    contribution: Decimal
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "name": self.name,
            "raw_value": _dec_str(self.raw_value),
            "score": _dec_str(self.score),
            "weight": _dec_str(self.weight),
            "contribution": _dec_str(self.contribution),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ProtectionScore:
    """The headline 0-100 score plus its full derivation."""

    total: Decimal
    grade: str
    verdict: Verdict
    components: Tuple[ScoreComponent, ...]
    flags: Tuple[RiskFlag, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-native representation."""
        return {
            "total": _dec_str(self.total),
            "grade": self.grade,
            "verdict": self.verdict.value,
            "components": [c.to_dict() for c in self.components],
            "flags": [f.to_dict() for f in self.flags],
        }


@dataclass(frozen=True)
class ProtectionReport:
    """Top-level analytics output - the object crossing the API boundary.

    This is the full contract for Issue #1 (frontend) and Issue #2 (backend).
    ``to_dict()`` is JSON-serialisable with no custom encoder required.
    """

    schema_version: str
    account_id: str
    generated_at: datetime
    exposure: ExposureMetrics
    concentration: ConcentrationMetrics
    drawdown: DrawdownMetrics
    volatility: VolatilityMetrics
    risk: RiskAssessment
    score: ProtectionScore
    hedge_evaluations: Tuple[HedgeEvaluation, ...] = ()
    recommended_bid_id: Optional[str] = None
    shadow_comparison: Optional[ShadowComparison] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return the stable JSON contract consumed by API and frontend."""
        return {
            "schema_version": self.schema_version,
            "account_id": self.account_id,
            "generated_at": self.generated_at.isoformat(),
            "exposure": self.exposure.to_dict(),
            "concentration": self.concentration.to_dict(),
            "drawdown": self.drawdown.to_dict(),
            "volatility": self.volatility.to_dict(),
            "risk": self.risk.to_dict(),
            "score": self.score.to_dict(),
            "hedge_evaluations": [h.to_dict() for h in self.hedge_evaluations],
            "recommended_bid_id": self.recommended_bid_id,
            "shadow_comparison": (
                None if self.shadow_comparison is None else self.shadow_comparison.to_dict()
            ),
        }


def sort_flags(flags: Sequence[RiskFlag]) -> Tuple[RiskFlag, ...]:
    """Order flags by severity then code, so output never reshuffles."""
    return tuple(sorted(flags, key=lambda f: (_SEVERITY_RANK[f.severity], f.code)))
