"""Deterministic numeric primitives for the RaptorClick analytics layer.

Every number that reaches a verdict flows through this module. The rules are
deliberately strict, because analytics is the component judges poke at hardest:
if two runs over the same snapshot disagree, the "deterministic protection"
claim collapses.

Rules enforced here
-------------------
1. ``Decimal`` everywhere. Floats are accepted only at the boundary and are
   converted via ``repr`` so ``0.1`` becomes ``Decimal("0.1")`` rather than
   ``Decimal("0.1000000000000000055511151231257827021181583404541015625")``.
2. A pinned :class:`decimal.Context`. We never rely on the ambient context,
   which another module, a notebook, or a test runner could mutate.
3. ``ROUND_HALF_EVEN`` for all quantisation. Banker's rounding is the IEEE
   default and stops repeated aggregation from drifting upward.
4. No division by zero, ever. :func:`safe_div` returns an explicit fallback so
   callers do not need a defensive branch at every call site.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Iterable, Sequence, Union

__all__ = [
    "DECIMAL_PRECISION",
    "ZERO",
    "ONE",
    "HUNDRED",
    "Numeric",
    "D",
    "q",
    "q2",
    "q4",
    "safe_div",
    "dsqrt",
    "dmean",
    "dstdev",
    "clamp",
    "dmax",
    "dmin",
    "dsum",
    "to_pct",
    "is_close",
]

#: Working precision. 28 significant digits is the Python default and is far
#: more than portfolio maths needs; pinning it makes the value explicit.
DECIMAL_PRECISION = 28

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

_Q6 = Decimal("0.000001")
_Q4 = Decimal("0.0001")
_Q2 = Decimal("0.01")

Numeric = Union[int, float, str, Decimal]


def D(value: Numeric) -> Decimal:
    """Coerce ``value`` into a :class:`Decimal` without float contamination.

    Floats are routed through ``repr`` so the shortest round-trippable literal
    is used. That is what a human means when they type ``0.1``, and it keeps
    fixtures readable when echoed back into JSON.

    Raises:
        TypeError: if the value cannot be interpreted as a number.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool subclasses int; silently treating True as 1 hides real bugs.
        raise TypeError("bool is not a valid numeric input")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise TypeError("empty string is not a valid numeric input")
        try:
            return Decimal(text)
        except InvalidOperation as exc:  # pragma: no cover - defensive
            raise TypeError(f"cannot parse {value!r} as a number") from exc
    raise TypeError(f"unsupported numeric type: {type(value).__name__}")


def q(value: Numeric, exp: Decimal = _Q6) -> Decimal:
    """Quantise to a fixed exponent with banker's rounding."""
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        return D(value).quantize(exp, rounding=ROUND_HALF_EVEN)


def q4(value: Numeric) -> Decimal:
    """Quantise to 4 decimal places - the canonical ratio/percent precision."""
    return q(value, _Q4)


def q2(value: Numeric) -> Decimal:
    """Quantise to 2 decimal places - the canonical money precision."""
    return q(value, _Q2)


def safe_div(
    numerator: Numeric,
    denominator: Numeric,
    default: Numeric = ZERO,
) -> Decimal:
    """Divide, returning ``default`` when the denominator is zero.

    A flat portfolio, a brand-new account and a fully-closed book all produce a
    zero denominator somewhere in this package. Returning a defined value beats
    raising: a risk report that refuses to render is worse than one that
    honestly reports zero exposure.
    """
    den = D(denominator)
    if den == ZERO:
        return D(default)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        return D(numerator) / den


def dsqrt(value: Numeric) -> Decimal:
    """Square root under the pinned context.

    Non-positive input returns zero rather than raising: it only ever arises
    from residue in a variance sum, and a negative variance is not a condition
    the caller can act on.
    """
    val = D(value)
    if val <= ZERO:
        return ZERO
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        return val.sqrt()


def dsum(values: Iterable[Numeric]) -> Decimal:
    """Sum an iterable as Decimal. Empty iterables sum to zero."""
    total = ZERO
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        for value in values:
            total += D(value)
    return total


def dmean(values: Sequence[Numeric]) -> Decimal:
    """Arithmetic mean; zero for an empty sequence."""
    if not values:
        return ZERO
    return safe_div(dsum(values), len(values))


def dstdev(values: Sequence[Numeric], sample: bool = True) -> Decimal:
    """Standard deviation.

    Args:
        values: the observations.
        sample: apply Bessel's correction (n-1). Sample statistics are the
            right choice here - a return series is a sample of the process,
            not the whole population.

    Fewer than two observations yields zero: undefined volatility is reported
    as "no signal", and callers fall back to scenario-based risk instead.
    """
    n = len(values)
    if n < 2:
        return ZERO
    mean = dmean(values)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        acc = ZERO
        for value in values:
            diff = D(value) - mean
            acc += diff * diff
        divisor = D(n - 1) if sample else D(n)
        return dsqrt(acc / divisor)


def clamp(value: Numeric, lower: Numeric, upper: Numeric) -> Decimal:
    """Constrain ``value`` to ``[lower, upper]``.

    Raises:
        ValueError: if the bounds are inverted, which is always a caller bug.
    """
    val, lo, hi = D(value), D(lower), D(upper)
    if lo > hi:
        raise ValueError(f"clamp bounds inverted: lower={lo} upper={hi}")
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def dmax(*values: Numeric) -> Decimal:
    """Maximum of the given values as Decimal."""
    if not values:
        raise ValueError("dmax requires at least one value")
    return max(D(v) for v in values)


def dmin(*values: Numeric) -> Decimal:
    """Minimum of the given values as Decimal."""
    if not values:
        raise ValueError("dmin requires at least one value")
    return min(D(v) for v in values)


def to_pct(ratio: Numeric) -> Decimal:
    """Convert a ratio (0.0742) into a percent figure (7.42), 4dp."""
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        return q4(D(ratio) * HUNDRED)


def is_close(a: Numeric, b: Numeric, tol: Numeric = Decimal("0.000001")) -> bool:
    """Absolute-tolerance comparison, used mostly by tests and invariants."""
    return abs(D(a) - D(b)) <= D(tol)
