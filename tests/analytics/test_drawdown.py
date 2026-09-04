"""Tests for drawdown analytics.

Most expectations are hand-computed from short, explicit equity curves so the
arithmetic is visible in the test itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from raptor.analytics import EquityPoint, PortfolioSnapshot, compute_drawdown
from raptor.analytics.drawdown import drawdown_series, returns_series

START = datetime(2025, 8, 1, tzinfo=timezone.utc)


def _history(*equities):
    return [EquityPoint(START + timedelta(days=i), e) for i, e in enumerate(equities)]


def _snap(*equities):
    hist = _history(*equities)
    last = hist[-1].equity if hist else Decimal("0")
    return PortfolioSnapshot("t", START, 0, last, history=hist)


class TestDrawdownSeries:
    def test_monotonic_rise_has_no_drawdown(self):
        assert drawdown_series(_history(100, 110, 120)) == [Decimal("0.0000")] * 3

    def test_drawdown_is_measured_from_running_peak(self):
        # Peak 120, trough 90 -> (120-90)/120 = 0.25
        series = drawdown_series(_history(100, 120, 90))
        assert series == [Decimal("0.0000"), Decimal("0.0000"), Decimal("0.2500")]

    def test_new_peak_resets_drawdown_to_zero(self):
        series = drawdown_series(_history(100, 80, 120))
        assert series[-1] == Decimal("0.0000")


class TestComputeDrawdown:
    def test_max_drawdown_is_the_deepest_decline(self):
        dd = compute_drawdown(_snap(100, 120, 90, 110))
        assert dd.max_drawdown == Decimal("0.2500")
        assert dd.peak_equity == Decimal("120.00")
        assert dd.trough_equity == Decimal("90.00")

    def test_current_drawdown_differs_from_max_after_recovery(self):
        # Max was 25%, but we have since recovered to 110 -> current is ~8.33%.
        dd = compute_drawdown(_snap(100, 120, 90, 110))
        assert dd.max_drawdown == Decimal("0.2500")
        assert dd.current_drawdown == pytest.approx(
            Decimal("0.0833"), abs=Decimal("0.001")
        )

    def test_recovery_asymmetry_is_reported_correctly(self):
        # 50% loss requires a 100% gain. The most under-appreciated fact in
        # retail risk, and the reason this is a separate field.
        dd = compute_drawdown(_snap(100, 50))
        assert dd.max_drawdown == Decimal("0.5000")
        assert dd.recovery_needed == Decimal("1.0000")

    def test_recovery_is_zero_at_a_new_high(self):
        assert compute_drawdown(_snap(100, 90, 150)).recovery_needed == Decimal("0")

    def test_max_drawdown_value_is_absolute_currency(self):
        dd = compute_drawdown(_snap(1000, 1200, 900))
        assert dd.max_drawdown_value == Decimal("300.00")

    def test_ulcer_index_penalises_prolonged_drawdowns(self):
        # Same trough depth; the longer stay under water must score worse.
        brief = compute_drawdown(_snap(100, 80, 100, 100, 100))
        prolonged = compute_drawdown(_snap(100, 80, 80, 80, 80))
        assert prolonged.ulcer_index > brief.ulcer_index

    def test_periods_under_water_counted(self):
        assert compute_drawdown(_snap(100, 90, 95, 100, 105)).periods_under_water == 2

    def test_insufficient_history_returns_zeroed_metrics(self):
        # Deliberately not an exception: a fresh account is a normal state.
        dd = compute_drawdown(_snap(100))
        assert dd.observations == 0
        assert dd.max_drawdown == Decimal("0")

    def test_no_history_at_all(self, empty):
        assert compute_drawdown(empty).observations == 0

    def test_flat_curve_has_no_drawdown(self):
        dd = compute_drawdown(_snap(100, 100, 100))
        assert dd.max_drawdown == Decimal("0.0000")
        assert dd.ulcer_index == Decimal("0.0000")


class TestReturnsSeries:
    def test_returns_are_period_over_period(self):
        assert returns_series(_history(100, 110, 99)) == [
            Decimal("0.1000"), Decimal("-0.1000")
        ]

    def test_zero_equity_period_is_skipped_not_treated_as_total_loss(self):
        # Including it would poison the volatility estimate feeding VaR.
        assert len(returns_series(_history(0, 100, 110))) == 1

    def test_single_point_yields_no_returns(self):
        assert returns_series(_history(100)) == []
