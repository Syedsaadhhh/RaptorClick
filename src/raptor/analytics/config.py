"""Tunable thresholds and weights for the analytics layer.

Why every constant lives in one frozen object
---------------------------------------------
Hard-coded thresholds scattered through calculation code are the fastest way to
lose determinism. Two callers end up with two different notions of "too
concentrated", and the scores stop being comparable.

Centralising them buys three things:

1. **Auditability.** A judge can read one file and know exactly what the agent
   considers risky.
2. **Reproducibility.** A report can be re-derived later from the config that
   produced it - :meth:`AnalyticsConfig.to_dict` round-trips.
3. **Tunability without forks.** The backend can raise a threshold for an
   aggressive account without touching any maths.

Calibration is documented per field. The numbers are opinionated but not
arbitrary: they follow standard risk-management convention (HHI bands from
antitrust literature, the 20% bear-market definition, 1.65 sigma for 95% VaR).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Dict, Mapping, Tuple

from ._num import D, Numeric, ZERO, is_close
from .errors import ConfigError

__all__ = ["StressScenario", "AnalyticsConfig", "DEFAULT_CONFIG", "CONSERVATIVE_CONFIG"]


@dataclass(frozen=True)
class StressScenario:
    """A named market shock used for deterministic stress testing.

    We deliberately do not simulate. A Monte Carlo run would be more
    sophisticated and completely unreproducible without seed plumbing, and
    "trust me, I ran 10,000 paths" is a worse demo than "here is the 2008 number
    and here is the arithmetic".

    Args:
        name: human-readable label, shown in the UI.
        market_shock: fractional drop in the market factor (0.20 = -20%).
        correlation_uplift: how much idiosyncratic diversification benefit
            disappears in this scenario. In a real crash correlations converge
            toward 1, so a "diversified" book behaves like a concentrated one.
            This is the term most naive risk models miss.
        description: provenance of the calibration.
    """

    name: str
    market_shock: Decimal
    correlation_uplift: Decimal
    description: str = ""

    def __post_init__(self) -> None:
        if not (ZERO <= self.market_shock <= Decimal("1")):
            raise ConfigError(
                f"scenario {self.name}: market_shock must be within [0, 1], "
                f"got {self.market_shock}"
            )
        if not (ZERO <= self.correlation_uplift <= Decimal("1")):
            raise ConfigError(
                f"scenario {self.name}: correlation_uplift must be within [0, 1], "
                f"got {self.correlation_uplift}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "market_shock": format(self.market_shock, "f"),
            "correlation_uplift": format(self.correlation_uplift, "f"),
            "description": self.description,
        }


#: Ordered mildest-to-worst. Order is part of the contract: the UI renders them
#: as a severity ladder.
DEFAULT_SCENARIOS: Tuple[StressScenario, ...] = (
    StressScenario(
        name="mild_correction",
        market_shock=Decimal("0.05"),
        correlation_uplift=Decimal("0.10"),
        description="Routine 5% pullback; diversification mostly still works.",
    ),
    StressScenario(
        name="correction",
        market_shock=Decimal("0.10"),
        correlation_uplift=Decimal("0.25"),
        description="Standard 10% correction; sector dispersion begins to compress.",
    ),
    StressScenario(
        name="bear_shock",
        market_shock=Decimal("0.20"),
        correlation_uplift=Decimal("0.50"),
        description="20% bear-market threshold; cross-asset correlations rise sharply.",
    ),
    StressScenario(
        name="crisis",
        market_shock=Decimal("0.35"),
        correlation_uplift=Decimal("0.80"),
        description="2008/2020-style dislocation; diversification largely fails.",
    ),
)


@dataclass(frozen=True)
class AnalyticsConfig:
    """All thresholds, weights and scenarios in one immutable object.

    Use :meth:`with_overrides` to derive a variant; the instance itself is
    frozen so a shared default can never be mutated by one caller and silently
    change another's results.
    """

    # -- Leverage -------------------------------------------------------- #
    #: Gross leverage above this is flagged. 1.5x is where a 20% shock starts
    #: consuming a third of equity.
    max_gross_leverage: Decimal = Decimal("1.5")
    #: Net (directional) leverage ceiling. Below gross, because a market-neutral
    #: book can carry more gross safely.
    max_net_leverage: Decimal = Decimal("1.0")

    # -- Concentration ---------------------------------------------------- #
    #: HHI above this counts as concentrated. 0.18 is the antitrust threshold
    #: for a "moderately concentrated" market; it maps to roughly 5-6 effective
    #: equal-weight positions.
    max_hhi: Decimal = Decimal("0.18")
    #: No single name should exceed 25% of gross exposure.
    max_position_weight: Decimal = Decimal("0.25")
    #: No single sector should exceed 40%.
    max_sector_weight: Decimal = Decimal("0.40")
    #: Top 3 names above 60% of the book is a red flag.
    max_top3_weight: Decimal = Decimal("0.60")

    # -- Drawdown --------------------------------------------------------- #
    #: Max drawdown tolerance. 15% is the conventional retail pain threshold.
    max_drawdown_tolerance: Decimal = Decimal("0.15")
    #: A current drawdown beyond this escalates severity - being *in* a
    #: drawdown is materially worse than having recovered from one.
    critical_current_drawdown: Decimal = Decimal("0.10")

    # -- Risk / VaR ------------------------------------------------------- #
    #: One-sided normal z for 95% confidence.
    var_z_score: Decimal = Decimal("1.645")
    var_confidence: Decimal = Decimal("0.95")
    #: Scenario used for the headline verdict. "bear_shock" is the honest
    #: middle: severe enough to matter, common enough to be credible.
    primary_scenario: str = "bear_shock"
    #: Stress loss beyond this fraction of equity fails the survival check.
    max_stress_loss_pct: Decimal = Decimal("0.20")

    # -- Hedging ---------------------------------------------------------- #
    #: A hedge costing more than 2% of notional is expensive.
    max_premium_bps: Decimal = Decimal("200")
    #: Below this fraction of stress loss covered, a hedge is decorative.
    min_coverage_ratio: Decimal = Decimal("0.50")
    #: Payout per unit premium below this makes the hedge non-viable.
    min_cost_efficiency: Decimal = Decimal("1.0")

    # -- Scoring weights (must sum to 1) ---------------------------------- #
    #: Exposure is weighted highest: leverage is the fastest route to ruin.
    weight_exposure: Decimal = Decimal("0.30")
    weight_concentration: Decimal = Decimal("0.25")
    weight_drawdown: Decimal = Decimal("0.20")
    weight_hedge: Decimal = Decimal("0.25")

    # -- Verdict bands ---------------------------------------------------- #
    score_protected: Decimal = Decimal("80")
    score_acceptable: Decimal = Decimal("60")
    score_exposed: Decimal = Decimal("40")

    scenarios: Tuple[StressScenario, ...] = field(default=DEFAULT_SCENARIOS)

    def __post_init__(self) -> None:
        weights = (
            self.weight_exposure
            + self.weight_concentration
            + self.weight_drawdown
            + self.weight_hedge
        )
        if not is_close(weights, Decimal("1"), Decimal("0.0001")):
            raise ConfigError(
                f"scoring weights must sum to 1.0, got {weights}. "
                "Unnormalised weights would silently rescale every score and "
                "make two deployments disagree."
            )

        for name in (
            "max_gross_leverage",
            "max_net_leverage",
            "max_hhi",
            "max_position_weight",
            "max_sector_weight",
            "max_drawdown_tolerance",
            "var_z_score",
            "max_premium_bps",
        ):
            if getattr(self, name) <= ZERO:
                raise ConfigError(f"{name} must be positive")

        if not (self.score_protected > self.score_acceptable > self.score_exposed):
            raise ConfigError(
                "verdict bands must strictly decrease: "
                f"protected({self.score_protected}) > "
                f"acceptable({self.score_acceptable}) > "
                f"exposed({self.score_exposed})"
            )

        if not self.scenarios:
            raise ConfigError("at least one stress scenario is required")

        names = [s.name for s in self.scenarios]
        if len(names) != len(set(names)):
            raise ConfigError(f"scenario names must be unique, got {names}")
        if self.primary_scenario not in names:
            raise ConfigError(
                f"primary_scenario {self.primary_scenario!r} is not among the "
                f"configured scenarios {names}"
            )

    def scenario(self, name: str) -> StressScenario:
        """Look up a scenario by name.

        Raises:
            ConfigError: if it is not configured.
        """
        for candidate in self.scenarios:
            if candidate.name == name:
                return candidate
        raise ConfigError(
            f"unknown scenario {name!r}; configured: "
            f"{[s.name for s in self.scenarios]}"
        )

    @property
    def primary(self) -> StressScenario:
        """The scenario driving the headline verdict."""
        return self.scenario(self.primary_scenario)

    def with_overrides(self, **kwargs: Any) -> "AnalyticsConfig":
        """Return a validated copy with fields replaced.

        Decimal-typed fields accept int/float/str and are coerced, so callers
        can write ``cfg.with_overrides(max_hhi=0.25)`` naturally.
        """
        coerced: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise ConfigError(f"unknown config field: {key}")
            current = getattr(self, key)
            if isinstance(current, Decimal) and not isinstance(value, Decimal):
                coerced[key] = D(value)
            else:
                coerced[key] = value
        return replace(self, **coerced)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for reproducibility - a report can cite the exact config."""

        def fmt(value: Any) -> Any:
            if isinstance(value, Decimal):
                return format(value, "f")
            return value

        return {
            "max_gross_leverage": fmt(self.max_gross_leverage),
            "max_net_leverage": fmt(self.max_net_leverage),
            "max_hhi": fmt(self.max_hhi),
            "max_position_weight": fmt(self.max_position_weight),
            "max_sector_weight": fmt(self.max_sector_weight),
            "max_top3_weight": fmt(self.max_top3_weight),
            "max_drawdown_tolerance": fmt(self.max_drawdown_tolerance),
            "critical_current_drawdown": fmt(self.critical_current_drawdown),
            "var_z_score": fmt(self.var_z_score),
            "var_confidence": fmt(self.var_confidence),
            "primary_scenario": self.primary_scenario,
            "max_stress_loss_pct": fmt(self.max_stress_loss_pct),
            "max_premium_bps": fmt(self.max_premium_bps),
            "min_coverage_ratio": fmt(self.min_coverage_ratio),
            "min_cost_efficiency": fmt(self.min_cost_efficiency),
            "weights": {
                "exposure": fmt(self.weight_exposure),
                "concentration": fmt(self.weight_concentration),
                "drawdown": fmt(self.weight_drawdown),
                "hedge": fmt(self.weight_hedge),
            },
            "verdict_bands": {
                "protected": fmt(self.score_protected),
                "acceptable": fmt(self.score_acceptable),
                "exposed": fmt(self.score_exposed),
            },
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


#: Shared default. Frozen, so it is safe to use as a module-level singleton.
DEFAULT_CONFIG = AnalyticsConfig()

#: Tighter profile for capital-preservation accounts. Demonstrates that the
#: thresholds are genuinely policy, not physics.
CONSERVATIVE_CONFIG = AnalyticsConfig(
    max_gross_leverage=Decimal("1.0"),
    max_net_leverage=Decimal("0.7"),
    max_hhi=Decimal("0.12"),
    max_position_weight=Decimal("0.15"),
    max_drawdown_tolerance=Decimal("0.10"),
    max_stress_loss_pct=Decimal("0.12"),
    primary_scenario="crisis",
)
