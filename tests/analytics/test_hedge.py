"""Tests for risk assessment and hedge evaluation.

These cover the analytical claims RaptorClick makes in its pitch, so they are
written as assertions about *behaviour under a named condition* rather than
about specific magic numbers wherever possible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from raptor.analytics import (
    DEFAULT_CONFIG,
    HedgeBid,
    HedgeInstrument,
    PortfolioSnapshot,
    Position,
    assess_risk,
    compute_concentration,
    compute_exposure,
    evaluate_bid,
    evaluate_bids,
    hedge_payout,
)

UTC = datetime(2025, 8, 31, tzinfo=timezone.utc)


def _risk_for(snapshot, config=DEFAULT_CONFIG, scenario=None):
    exp = compute_exposure(snapshot)
    con = compute_concentration(snapshot)
    return assess_risk(snapshot, exp, con, config, scenario), exp


def _snap(positions, equity):
    return PortfolioSnapshot("t", UTC, 0, equity, positions=positions)


class TestAssessRisk:
    def test_directional_loss_scales_with_beta(self):
        low = _snap([Position("A", 1000, "100", beta="0.5")], 100000)
        high = _snap([Position("A", 1000, "100", beta="2.0")], 100000)
        assert _risk_for(high)[0].directional_loss > _risk_for(low)[0].directional_loss

    def test_directional_loss_is_hand_computable(self):
        # 100k exposure, beta 1.0, bear_shock 20% -> 20k directional.
        snap = _snap([Position("A", 1000, "100")], 100000)
        risk, _ = _risk_for(snap)
        assert risk.directional_loss == Decimal("20000.00")

    def test_concentrated_book_carries_more_idiosyncratic_loss(self):
        # Identical gross exposure, identical beta - only breadth differs.
        one_name = _snap([Position("A", 1000, "100")], 100000)
        ten_names = _snap(
            [Position(f"S{i}", 100, "100") for i in range(10)], 100000
        )
        assert (
            _risk_for(one_name)[0].idiosyncratic_loss
            > _risk_for(ten_names)[0].idiosyncratic_loss
        )

    def test_market_neutral_book_still_carries_risk(self):
        # The headline claim: near-zero net exposure is not the same as safe.
        snap = _snap(
            [Position("A", 500, "100"), Position("B", -500, "100")], 100000
        )
        risk, exp = _risk_for(snap)
        assert exp.net_exposure == Decimal("0.0000")
        assert risk.directional_loss == Decimal("0.00")
        # A purely directional model would stop at zero. We do not.
        assert risk.idiosyncratic_loss > Decimal("0")
        assert risk.stress_loss > Decimal("0")

    def test_worse_scenarios_produce_larger_losses(self):
        snap = _snap([Position("A", 1000, "100")], 100000)
        losses = [
            _risk_for(snap, scenario=DEFAULT_CONFIG.scenario(name))[0].stress_loss
            for name in ("mild_correction", "correction", "bear_shock", "crisis")
        ]
        assert losses == sorted(losses)

    def test_survival_flag_tracks_the_configured_limit(self):
        modest = _snap([Position("A", 100, "100")], 100000)   # 10k exposure
        extreme = _snap([Position("A", 5000, "100")], 100000)  # 500k exposure
        assert _risk_for(modest)[0].survives_stress is True
        assert _risk_for(extreme)[0].survives_stress is False

    def test_empty_portfolio_has_no_stress_loss(self, empty):
        risk, _ = _risk_for(empty)
        assert risk.stress_loss == Decimal("0.00")
        assert risk.survives_stress is True

    def test_var_is_zero_without_sufficient_history(self):
        # "No signal", not "no risk" - the scenario loss still drives the verdict.
        snap = _snap([Position("A", 100, "100")], 100000)
        assert _risk_for(snap)[0].parametric_var == Decimal("0")

    def test_var_is_positive_with_a_volatile_history(self, balanced):
        risk, _ = _risk_for(balanced)
        assert risk.parametric_var > Decimal("0")


class TestHedgePayout:
    def _bid(self, **kwargs):
        params = dict(
            bid_id="b", provider="p", instrument=HedgeInstrument.PUT,
            notional=100000, premium=1000, coverage_ratio="1.0", buffer_pct="0",
        )
        params.update(kwargs)
        return HedgeBid(**params)

    def test_full_coverage_no_buffer_pays_the_whole_loss(self):
        assert hedge_payout(self._bid(), Decimal("10000")) == Decimal("10000.00")

    def test_buffer_acts_as_a_deductible(self):
        # 5% of 100k = 5k absorbed; 10k loss -> 5k payout.
        bid = self._bid(buffer_pct="0.05")
        assert hedge_payout(bid, Decimal("10000")) == Decimal("5000.00")

    def test_loss_inside_the_buffer_pays_nothing(self):
        bid = self._bid(buffer_pct="0.05")
        assert hedge_payout(bid, Decimal("4000")) == Decimal("0")

    def test_coverage_ratio_scales_the_payout(self):
        bid = self._bid(coverage_ratio="0.60")
        assert hedge_payout(bid, Decimal("10000")) == Decimal("6000.00")

    def test_max_payout_caps_a_spread(self):
        bid = self._bid(
            instrument=HedgeInstrument.PUT_SPREAD, max_payout=3000, buffer_pct="0"
        )
        assert hedge_payout(bid, Decimal("50000")) == Decimal("3000.00")

    def test_capped_instrument_never_exceeds_notional(self):
        bid = self._bid(instrument=HedgeInstrument.CASH_RESERVE, notional=5000)
        assert hedge_payout(bid, Decimal("999999")) == Decimal("5000.00")

    def test_zero_or_negative_loss_pays_nothing(self):
        assert hedge_payout(self._bid(), Decimal("0")) == Decimal("0")
        assert hedge_payout(self._bid(), Decimal("-500")) == Decimal("0")


class TestEvaluateBid:
    def test_good_hedge_is_viable_and_explained(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[0], risk, exp)
        assert ev.is_viable
        # The rationale is a deliverable, not decoration.
        assert "Covers" in ev.reason

    def test_overpriced_bid_is_rejected_with_a_reason(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[2], risk, exp)  # 350bps, over the 200bps ceiling
        assert not ev.is_viable
        assert "premium" in ev.reason.lower()

    def test_token_hedge_is_rejected_on_coverage(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[3], risk, exp)  # 30% coverage on a quarter notional
        assert not ev.is_viable
        assert "covers only" in ev.reason.lower()

    def test_zero_premium_bid_does_not_divide_by_zero(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[4], risk, exp)
        assert ev.cost_efficiency >= Decimal("0")

    def test_notional_gap_exposes_an_undersized_hedge(self, balanced, bids):
        # A cheap bid covering a fraction of the book is a small hedge, not a
        # cheap one. This field is what makes that visible.
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[3], risk, exp)
        assert ev.notional_gap > Decimal("0")

    def test_net_benefit_is_payout_minus_premium(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        ev = evaluate_bid(bids[0], risk, exp)
        assert ev.net_benefit == ev.expected_payout - ev.premium


class TestEvaluateBids:
    def test_viable_bids_rank_ahead_of_rejected_ones(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        results = evaluate_bids(bids, risk, exp)
        viability = [e.is_viable for e in results]
        assert viability == sorted(viability, reverse=True)

    def test_ranking_is_by_net_benefit_not_cheapest_premium(self, balanced, bids):
        # Ranking on price alone is the failure mode this auction exists to avoid.
        risk, exp = _risk_for(balanced)
        results = [e for e in evaluate_bids(bids, risk, exp) if e.is_viable]
        if len(results) > 1:
            assert results[0].net_benefit >= results[1].net_benefit

    def test_ranking_is_stable_regardless_of_input_order(self, balanced, bids):
        risk, exp = _risk_for(balanced)
        forward = [e.bid_id for e in evaluate_bids(bids, risk, exp)]
        reverse = [e.bid_id for e in evaluate_bids(list(reversed(bids)), risk, exp)]
        assert forward == reverse

    def test_identical_bids_break_ties_by_id(self, balanced):
        risk, exp = _risk_for(balanced)
        common = dict(
            provider="P", instrument=HedgeInstrument.PUT, notional=150000,
            premium=1500, coverage_ratio="0.9", buffer_pct="0.03",
        )
        pair = [HedgeBid(bid_id="bid-B", **common), HedgeBid(bid_id="bid-A", **common)]
        assert [e.bid_id for e in evaluate_bids(pair, risk, exp)] == ["bid-A", "bid-B"]

    def test_no_bids_returns_empty(self, balanced):
        risk, exp = _risk_for(balanced)
        assert evaluate_bids([], risk, exp) == ()
