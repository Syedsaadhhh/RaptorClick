"""Exception hierarchy for the analytics layer.

A single base class (:class:`AnalyticsError`) means the backend can wrap every
analytics call in one ``except`` and translate it into a typed API error,
without importing the internals of this package.
"""

from __future__ import annotations

__all__ = [
    "AnalyticsError",
    "ValidationError",
    "ConfigError",
    "InsufficientDataError",
]


class AnalyticsError(Exception):
    """Base class for every error raised by :mod:`raptor.analytics`."""


class ValidationError(AnalyticsError):
    """Input data violated a domain invariant.

    Raised at construction time by the typed models, so an invalid snapshot can
    never reach a calculation. Failing loudly at the boundary is what keeps the
    maths functions free of defensive branches.
    """


class ConfigError(AnalyticsError):
    """An :class:`~raptor.analytics.config.AnalyticsConfig` is self-inconsistent.

    Example: scoring weights that do not sum to 1, which would silently rescale
    the protection score and make two deployments disagree.
    """


class InsufficientDataError(AnalyticsError):
    """A metric was requested that the supplied history cannot support.

    Most of this package degrades gracefully instead of raising (a two-point
    equity curve yields zero volatility, not an exception). This is reserved
    for callers who explicitly opt into strict mode.
    """
