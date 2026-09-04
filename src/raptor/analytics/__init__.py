"""Deterministic protection analytics for RaptorClick.

The public surface is intentionally small. Import from this package root; the
submodules are implementation detail and may be reorganised.

    >>> from raptor.analytics import analyse, PortfolioSnapshot, Position
    >>> report = analyse(snapshot, bids)
    >>> report.score.total
    Decimal('72.40')

Guarantees
----------
* **Deterministic.** Same inputs produce byte-identical output. No clock, no
  randomness, no ambient state.
* **Typed.** Every input and output is a frozen dataclass with validation at
  construction.
* **Serialisable.** ``report.to_dict()`` is JSON-native with no custom encoder.

See ``docs/analytics/README.md`` for the model write-up and
``docs/analytics/INTEGRATION.md`` for the wire contract.
"""

from __future__ import annotations

from ._num import D
from .config import (
    CONSERVATIVE_CONFIG,
    DEFAULT_CONFIG,
    AnalyticsConfig,
    StressScenario,
)
from .drawdown import compute_drawdown
from .drift import assess_state_drift
from .counterfactual import compare_shadow_book
from .engine import analyse, analyze
from .errors import (
    AnalyticsError,
    ConfigError,
    InsufficientDataError,
    ValidationError,
)
from .exposure import compute_concentration, compute_exposure
from .hedge import (
    assess_liquidity,
    assess_risk,
    evaluate_bid,
    evaluate_bids,
    hedge_payout,
    maximum_hedge_risk,
    normalized_hedge_score,
)
from .scoring import band_score, compute_score, grade_for
from .types import (
    SCHEMA_VERSION,
    AssetClass,
    ConcentrationMetrics,
    DrawdownMetrics,
    DriftAssessment,
    EquityPoint,
    ExposureMetrics,
    HedgeBid,
    HedgeEvaluation,
    HedgeInstrument,
    LiquidityAssessment,
    MetricStatus,
    PriceBar,
    PortfolioSnapshot,
    Position,
    ProtectionReport,
    ProtectionScore,
    RiskAssessment,
    RiskFlag,
    ScoreComponent,
    Severity,
    ShadowComparison,
    Side,
    Verdict,
    VolatilityEstimate,
    VolatilityMetrics,
)
from .volatility import compute_historical_volatility

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SCHEMA_VERSION",
    # entry point
    "analyse",
    "analyze",
    # config
    "AnalyticsConfig",
    "StressScenario",
    "DEFAULT_CONFIG",
    "CONSERVATIVE_CONFIG",
    # input types
    "PortfolioSnapshot",
    "Position",
    "EquityPoint",
    "PriceBar",
    "HedgeBid",
    # output types
    "ProtectionReport",
    "ProtectionScore",
    "ScoreComponent",
    "ExposureMetrics",
    "ConcentrationMetrics",
    "DrawdownMetrics",
    "RiskAssessment",
    "HedgeEvaluation",
    "RiskFlag",
    "VolatilityEstimate",
    "VolatilityMetrics",
    "LiquidityAssessment",
    "ShadowComparison",
    "DriftAssessment",
    # enums
    "Side",
    "AssetClass",
    "HedgeInstrument",
    "Verdict",
    "Severity",
    "MetricStatus",
    # functions
    "compute_exposure",
    "compute_concentration",
    "compute_drawdown",
    "assess_risk",
    "evaluate_bid",
    "evaluate_bids",
    "hedge_payout",
    "assess_liquidity",
    "maximum_hedge_risk",
    "normalized_hedge_score",
    "compute_historical_volatility",
    "compare_shadow_book",
    "assess_state_drift",
    "compute_score",
    "band_score",
    "grade_for",
    # errors
    "AnalyticsError",
    "ValidationError",
    "ConfigError",
    "InsufficientDataError",
    # helper
    "D",
]
