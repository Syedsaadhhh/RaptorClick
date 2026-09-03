"""Acceptance coverage mapped directly to GitHub Issue #3."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from raptor.analytics import (
    DEFAULT_CONFIG,
    HedgeBid,
    HedgeInstrument,
    MetricStatus,
    PortfolioSnapshot,
    Position,
    PriceBar,
    analyse,
    assess_liquidity,
    assess_risk,
    assess_state_drift,
    compare_shadow_book,
    compute_concentration,
    compute_exposure,
    compute_historical_volatility,
    evaluate_bid,
    evaluate_bids,
    maximum_hedge_risk,
)
from raptor.analytics.samples import FIXED_TIME, balanced_portfolio


def _option_bid(**overrides):
    values = {
        "bid_id": "candidate",
        "provider": "SyntheticTestAgent",
        "instrument": HedgeInstrument.PUT,
        "notional": Decimal("150000"),
        "premium": Decimal("1200"),
        "coverage_ratio": Decimal("0.90"),
        "buffer_pct": Decimal("0.03"),
        "expiry_days": 30,
        "quote_bid": Decimal("4.80"),
        "quote_ask": Decimal("5.00"),
        "volume": 500,
        "open_interest": 2500,
    }
    values.update(overrides)
    return HedgeBid(**values)


def _risk(snapshot):
    exposure = compute_exposure(snapshot)
    return (
        assess_risk(snapshot, exposure, compute_concentration(snapshot)),
        exposure,
    )


def test_exposure_is_available_by_symbol_and_sector():
    exposure = compute_exposure(balanced_portfolio())
    assert exposure.symbol_exposures["AAPL"] == Decimal("18550.0000")
    assert exposure.sector_exposures["technology"] == Decimal("43162.0000")


def test_historical_volatility_uses_supplied_bars_and_is_repeatable():
    closes = ("100", "102", "99", "104")
    bars = [
        PriceBar("SPY", FIXED_TIME + timedelta(days=index), close)
        for index, close in enumerate(closes)
    ]
    first = compute_historical_volatility(bars)
    second = compute_historical_volatility(tuple(reversed(bars)))
    assert first == second
    assert first.status is MetricStatus.AVAILABLE
    assert first.estimates[0].annualized_volatility is not None


def test_missing_bars_are_explicitly_unavailable():
    result = compute_historical_volatility([])
    assert result.status is MetricStatus.UNAVAILABLE
    assert result.estimates == ()


def test_missing_option_data_is_not_fabricated_as_zero():
    bid = _option_bid(quote_bid=None, quote_ask=None, volume=None, open_interest=None)
    liquidity = assess_liquidity(bid)
    risk, exposure = _risk(balanced_portfolio())
    evaluation = evaluate_bid(bid, risk, exposure)
    assert liquidity.status is MetricStatus.UNAVAILABLE
    assert liquidity.score is None
    assert liquidity.passed is None
    assert not evaluation.is_viable
    assert "Missing option data" in evaluation.reason


def test_zero_quote_is_inconclusive_not_a_zero_liquidity_claim():
    liquidity = assess_liquidity(_option_bid(quote_bid=0))
    assert liquidity.status is MetricStatus.INCONCLUSIVE
    assert liquidity.score is None
    assert liquidity.passed is None


def test_illiquid_contract_fails_spread_volume_and_interest_gates():
    bid = _option_bid(quote_bid="1", quote_ask="2", volume=1, open_interest=2)
    liquidity = assess_liquidity(bid)
    risk, exposure = _risk(balanced_portfolio())
    assert liquidity.status is MetricStatus.AVAILABLE
    assert liquidity.passed is False
    assert len(liquidity.reasons) == 3
    assert evaluate_bid(bid, risk, exposure).is_viable is False


def test_over_budget_hedge_is_rejected():
    bid = _option_bid(premium="6000")
    risk, exposure = _risk(balanced_portfolio())
    result = evaluate_bid(bid, risk, exposure)
    assert not result.is_viable
    assert "premium" in result.reason
    assert "ceiling" in result.reason


def test_proposal_fails_notional_hard_limit():
    snapshot = balanced_portfolio()
    risk, exposure = _risk(snapshot)
    bid = _option_bid(notional=exposure.gross_exposure * Decimal("2"))
    result = evaluate_bid(bid, risk, exposure)
    assert not result.is_viable
    assert "hard limit" in result.reason


def test_maximum_risk_for_each_defined_risk_strategy_is_net_premium():
    for instrument in (
        HedgeInstrument.PUT,
        HedgeInstrument.PUT_SPREAD,
        HedgeInstrument.COLLAR,
    ):
        extras = {"max_payout": "20000"} if instrument is not HedgeInstrument.PUT else {}
        bid = _option_bid(instrument=instrument, **extras)
        assert maximum_hedge_risk(bid) == bid.premium


def test_shadow_book_and_protection_delta_are_net_of_cost():
    bid = _option_bid()
    risk, _ = _risk(balanced_portfolio())
    comparison = compare_shadow_book(bid, risk)
    assert comparison.protection_delta == comparison.hedge_payout - comparison.hedge_cost
    assert comparison.protected_loss == (
        comparison.unprotected_loss - comparison.protection_delta
    )


def test_ranking_changes_when_stress_state_changes():
    snapshot = balanced_portfolio()
    exposure = compute_exposure(snapshot)
    concentration = compute_concentration(snapshot)
    low_risk = assess_risk(
        snapshot,
        exposure,
        concentration,
        scenario=DEFAULT_CONFIG.scenario("mild_correction"),
    )
    high_risk = assess_risk(
        snapshot,
        exposure,
        concentration,
        scenario=DEFAULT_CONFIG.scenario("crisis"),
    )
    high_buffer = _option_bid(
        bid_id="high-buffer",
        premium="1000",
        coverage_ratio="1",
        buffer_pct="0.05",
    )
    first_loss = _option_bid(
        bid_id="first-loss",
        instrument=HedgeInstrument.PUT_SPREAD,
        premium="500",
        coverage_ratio="0.5",
        buffer_pct="0",
        max_payout="50000",
    )
    before = evaluate_bids([high_buffer, first_loss], low_risk, exposure)
    after = evaluate_bids([high_buffer, first_loss], high_risk, exposure)
    assert before[0].bid_id == "first-loss"
    assert after[0].bid_id == "high-buffer"


def test_portfolio_drift_marks_prior_ranking_stale():
    previous = balanced_portfolio()
    changed_positions = list(previous.positions)
    changed_positions[0] = Position("AAPL", 500, "185.50", sector="technology")
    current = PortfolioSnapshot(
        account_id=previous.account_id,
        timestamp=previous.timestamp + timedelta(minutes=5),
        cash=previous.cash,
        equity=previous.equity,
        positions=changed_positions,
        history=previous.history,
    )
    drift = assess_state_drift(previous, current)
    assert drift.is_stale
    assert drift.gross_exposure_drift > DEFAULT_CONFIG.max_gross_exposure_drift


def test_full_report_exposes_normalized_components_and_shadow_result():
    report = analyse(balanced_portfolio(), [_option_bid()])
    evaluation = report.hedge_evaluations[0]
    assert Decimal("0") <= evaluation.normalized_score <= Decimal("100")
    assert {component.name for component in evaluation.score_components} == {
        "protection",
        "cost_efficiency",
        "liquidity",
        "premium",
    }
    assert report.shadow_comparison is not None
    assert report.to_dict()["volatility"]["status"] == "unavailable"
