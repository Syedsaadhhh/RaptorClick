"""Tests for exposure and concentration metrics.

Hand-computed expectations throughout. A test that recomputes the metric using
the same code it is testing proves nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from raptor.analytics import PortfolioSnapshot, Position, compute_concentration, compute_exposure
from raptor.analytics.exposure import herfindahl_index, position_weights, sector_weights

UTC = datetime(2025, 8, 31, tzinfo=timezone.utc)


def _snap(positions, cash=0, equity=None):
    gross = sum(p.exposure for p in positions) if positions else Decimal("0")
    return PortfolioSnapshot(
        "t", UTC, cash, equity if equity is not None else gross + Decimal(cash),
        positions=positions,
    )


class TestExposure:
    def test_long_only_gross_equals_net(self):
        snap = _snap([Position("A", 100, "10"), Position("B", 100, "20")])
        exp = compute_exposure(snap)
        assert exp.gross_exposure == Decimal("3000.0000")
        assert exp.net_exposure == Decimal("3000.0000")
        assert exp.short_exposure == Decimal("0.0000")

    def test_long_short_book_nets_down(self):
        # 1000 long, 400 short -> gross 1400, net 600.
        snap = _snap([Position("A", 100, "10"), Position("B", -40, "10")], equity=1000)
        exp = compute_exposure(snap)
        assert exp.gross_exposure == Decimal("1400.0000")
        assert exp.net_exposure == Decimal("600.0000")
        assert exp.long_exposure == Decimal("1000.0000")
        assert exp.short_exposure == Decimal("400.0000")

    def test_market_neutral_book_has_zero_net_but_real_gross(self):
        # The case a naive directional model calls riskless.
        snap = _snap([Position("A", 100, "10"), Position("B", -100, "10")], equity=1000)
        exp = compute_exposure(snap)
        assert exp.net_exposure == Decimal("0.0000")
        assert exp.gross_exposure == Decimal("2000.0000")

    def test_beta_adjusted_exposure_amplifies_high_beta(self):
        snap = _snap([Position("A", 100, "10", beta="2.0")], equity=1000)
        assert compute_exposure(snap).beta_adjusted_exposure == Decimal("2000.0000")

    def test_leverage_ratios(self):
        snap = _snap([Position("A", 100, "10")], equity=500)
        exp = compute_exposure(snap)
        assert exp.gross_leverage == Decimal("2.0000")  # 1000 / 500
        assert exp.net_leverage == Decimal("2.0000")

    def test_zero_equity_yields_zero_leverage_not_an_exception(self):
        # A report that refuses to render is worse than one reporting zero.
        snap = PortfolioSnapshot("t", UTC, 0, 0, positions=[Position("A", 1, "10")])
        assert compute_exposure(snap).gross_leverage == Decimal("0.0000")

    def test_long_short_ratio_is_none_without_shorts(self):
        snap = _snap([Position("A", 100, "10")], equity=1000)
        assert compute_exposure(snap).long_short_ratio is None

    def test_empty_portfolio_is_all_cash(self, empty):
        exp = compute_exposure(empty)
        assert exp.gross_exposure == Decimal("0.0000")
        assert exp.position_count == 0
        assert exp.cash_ratio == Decimal("1.0000")


class TestConcentration:
    def test_hhi_of_equal_weights_is_reciprocal_of_count(self):
        # Four equal positions -> HHI 0.25 -> 4 effective positions.
        snap = _snap([Position(s, 10, "10") for s in ("A", "B", "C", "D")], equity=400)
        con = compute_concentration(snap)
        assert con.hhi == Decimal("0.2500")
        assert con.effective_positions == Decimal("4.0000")

    def test_single_position_has_maximal_hhi(self):
        snap = _snap([Position("A", 100, "10")], equity=1000)
        con = compute_concentration(snap)
        assert con.hhi == Decimal("1.0000")
        assert con.top_position_weight == Decimal("1.0000")
        assert con.largest_symbol == "A"

    def test_weights_sum_to_one(self):
        snap = _snap([Position("A", 37, "13.7"), Position("B", 11, "204.3")], equity=5000)
        assert sum(position_weights(snap.positions).values()) == pytest.approx(
            Decimal("1"), abs=Decimal("0.001")
        )

    def test_short_positions_count_toward_concentration(self):
        # A large short is a large bet; using signed value would hide it.
        snap = _snap([Position("A", 10, "10"), Position("B", -90, "10")], equity=1000)
        con = compute_concentration(snap)
        assert con.largest_symbol == "B"
        assert con.top_position_weight == Decimal("0.9000")

    def test_sector_weights_aggregate_case_insensitively(self):
        snap = _snap(
            [
                Position("A", 10, "10", sector="Technology"),
                Position("B", 10, "10", sector="technology"),
                Position("C", 10, "10", sector="energy"),
            ],
            equity=300,
        )
        weights = sector_weights(snap.positions)
        assert weights["technology"] == pytest.approx(
            Decimal("0.6667"), abs=Decimal("0.001")
        )
        assert compute_concentration(snap).top_sector == "technology"

    def test_top_n_weights_are_cumulative_and_ordered(self):
        snap = _snap([Position(s, q, "10") for s, q in
                      [("A", 50), ("B", 30), ("C", 10), ("D", 6), ("E", 4)]], equity=1000)
        con = compute_concentration(snap)
        assert con.top_position_weight == Decimal("0.5000")
        assert con.top_3_weight == Decimal("0.9000")
        assert con.top_5_weight == Decimal("1.0000")

    def test_ties_break_deterministically_by_symbol(self):
        # Two identical positions must never swap between runs.
        snap = _snap([Position("ZZZ", 10, "10"), Position("AAA", 10, "10")], equity=200)
        assert compute_concentration(snap).largest_symbol == "AAA"

    def test_empty_portfolio_returns_zeroed_metrics(self, empty):
        con = compute_concentration(empty)
        assert con.hhi == Decimal("0")
        assert con.largest_symbol is None
        assert con.sector_weights == {}

    def test_herfindahl_of_empty_mapping(self):
        assert herfindahl_index({}) == Decimal("0")

    def test_concentrated_fixture_breaches_single_name_cap(self, concentrated):
        con = compute_concentration(concentrated)
        assert con.largest_symbol == "NVDA"
        assert con.top_position_weight > Decimal("0.80")
        assert con.effective_positions < Decimal("1.5")
