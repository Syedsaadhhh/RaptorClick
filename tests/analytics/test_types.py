"""Tests for the typed models and their validation rules.

Validation is the contract with the backend. If an invalid snapshot can be
constructed, every downstream metric silently becomes untrustworthy - so these
tests assert that bad input is rejected at the boundary, loudly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from raptor.analytics import (
    AssetClass,
    EquityPoint,
    HedgeBid,
    HedgeInstrument,
    PortfolioSnapshot,
    Position,
    Side,
    ValidationError,
)

UTC_NOW = datetime(2025, 8, 31, 12, 0, tzinfo=timezone.utc)


class TestPosition:
    def test_long_position_basics(self):
        pos = Position("AAPL", 100, "150.00")
        assert pos.side is Side.LONG
        assert pos.market_value == Decimal("15000.00")
        assert pos.exposure == Decimal("15000.00")

    def test_short_position_has_negative_value_but_positive_exposure(self):
        pos = Position("TSLA", -50, "200.00")
        assert pos.side is Side.SHORT
        assert pos.market_value == Decimal("-10000.00")
        # Exposure is capital at risk, which is direction-agnostic.
        assert pos.exposure == Decimal("10000.00")

    def test_symbol_is_normalised_to_upper_case(self):
        assert Position("aapl", 10, "1").symbol == "AAPL"

    def test_beta_adjusted_exposure_preserves_sign(self):
        long_pos = Position("AAPL", 100, "100", beta="1.5")
        short_pos = Position("QQQ", -100, "100", beta="1.5")
        assert long_pos.beta_adjusted_exposure == Decimal("15000.00")
        # Sign retention is what lets a hedged book net down correctly.
        assert short_pos.beta_adjusted_exposure == Decimal("-15000.00")

    def test_unrealised_pnl_requires_cost_basis(self):
        assert Position("AAPL", 100, "150").unrealised_pnl is None
        assert Position("AAPL", 100, "150", cost_basis="14000").unrealised_pnl == Decimal("1000.00")

    def test_float_input_does_not_leak_binary_error(self):
        # The whole reason we route floats through repr().
        assert Position("AAPL", 10, 0.1).current_price == Decimal("0.1000")

    @pytest.mark.parametrize(
        "kwargs, fragment",
        [
            (dict(symbol="AAPL", quantity=0, current_price="10"), "quantity cannot be zero"),
            (dict(symbol="AAPL", quantity=10, current_price="0"), "must be positive"),
            (dict(symbol="AAPL", quantity=10, current_price="-5"), "must be positive"),
            (dict(symbol="", quantity=10, current_price="10"), "not a valid ticker"),
            (dict(symbol="TOO$MUCH", quantity=10, current_price="10"), "not a valid ticker"),
        ],
    )
    def test_invalid_positions_are_rejected(self, kwargs, fragment):
        with pytest.raises(ValidationError, match=fragment):
            Position(**kwargs)

    def test_market_value_contradicting_quantity_is_rejected(self):
        # A long position with negative market value is data corruption, not a
        # valid state; catching it here stops it poisoning every aggregate.
        with pytest.raises(ValidationError, match="contradicts quantity"):
            Position("AAPL", 100, "150", market_value="-15000")

    def test_position_is_immutable(self):
        pos = Position("AAPL", 100, "150")
        with pytest.raises(Exception):
            pos.quantity = Decimal("200")  # type: ignore[misc]


class TestEquityPoint:
    def test_naive_datetime_is_assumed_utc(self):
        point = EquityPoint(datetime(2025, 8, 31, 12, 0), 1000)
        assert point.timestamp.tzinfo is timezone.utc

    def test_negative_equity_is_rejected(self):
        with pytest.raises(ValidationError, match="cannot be negative"):
            EquityPoint(UTC_NOW, -100)


class TestPortfolioSnapshot:
    def test_positions_are_sorted_by_symbol(self):
        # Determinism starts here: fetch order must not affect any sum.
        snap = PortfolioSnapshot(
            "acct", UTC_NOW, 1000, 50000,
            positions=[
                Position("ZM", 10, "70"),
                Position("AAPL", 10, "150"),
                Position("MSFT", 10, "400"),
            ],
        )
        assert [p.symbol for p in snap.positions] == ["AAPL", "MSFT", "ZM"]

    def test_history_is_sorted_chronologically(self):
        snap = PortfolioSnapshot(
            "acct", UTC_NOW, 1000, 50000,
            history=[
                EquityPoint(UTC_NOW, 1200),
                EquityPoint(UTC_NOW - timedelta(days=2), 1000),
                EquityPoint(UTC_NOW - timedelta(days=1), 1100),
            ],
        )
        assert [p.equity for p in snap.history] == [
            Decimal("1000.00"), Decimal("1100.00"), Decimal("1200.00")
        ]

    def test_duplicate_symbols_are_rejected(self):
        with pytest.raises(ValidationError, match="duplicate position"):
            PortfolioSnapshot(
                "acct", UTC_NOW, 1000, 50000,
                positions=[Position("AAPL", 10, "150"), Position("AAPL", 5, "150")],
            )

    def test_negative_equity_is_rejected(self):
        with pytest.raises(ValidationError, match="equity cannot be negative"):
            PortfolioSnapshot("acct", UTC_NOW, 0, -1)

    def test_missing_account_id_is_rejected(self):
        with pytest.raises(ValidationError, match="account_id is required"):
            PortfolioSnapshot("  ", UTC_NOW, 0, 1000)

    def test_empty_snapshot_is_valid(self):
        assert PortfolioSnapshot("acct", UTC_NOW, 1000, 1000).is_empty


class TestHedgeBid:
    def test_premium_bps_is_normalised_against_notional(self):
        bid = HedgeBid("b1", "P", HedgeInstrument.PUT, notional=100000, premium=1500)
        assert bid.premium_bps == Decimal("150.0000")

    def test_capped_instrument_requires_max_payout(self):
        # Without a cap, the payoff model would overstate a spread's protection.
        with pytest.raises(ValidationError, match="requires max_payout"):
            HedgeBid("b1", "P", HedgeInstrument.PUT_SPREAD, notional=100000, premium=500)

    @pytest.mark.parametrize(
        "kwargs, fragment",
        [
            (dict(notional=0, premium=100), "notional must be positive"),
            (dict(notional=1000, premium=-1), "premium cannot be negative"),
            (dict(notional=1000, premium=10, coverage_ratio="1.5"), "coverage_ratio"),
            (dict(notional=1000, premium=10, buffer_pct="-0.1"), "buffer_pct"),
            (dict(notional=1000, premium=10, expiry_days=0), "expiry_days"),
        ],
    )
    def test_invalid_bids_are_rejected(self, kwargs, fragment):
        with pytest.raises(ValidationError, match=fragment):
            HedgeBid("b1", "P", HedgeInstrument.PUT, **kwargs)

    def test_zero_premium_is_allowed(self):
        # A cash reserve is free but not costless; the scorer handles that.
        bid = HedgeBid("b1", "P", HedgeInstrument.CASH_RESERVE, notional=1000, premium=0)
        assert bid.premium_bps == Decimal("0.0000")


class TestSerialisation:
    def test_decimals_serialise_as_strings(self, balanced_report):
        # Floats would lose precision crossing into JS. This is the contract
        # the frontend depends on.
        payload = balanced_report.to_dict()
        assert isinstance(payload["exposure"]["gross_exposure"], str)
        assert isinstance(payload["score"]["total"], str)

    def test_report_is_json_serialisable_without_custom_encoder(self, balanced_report):
        import json
        assert json.loads(json.dumps(balanced_report.to_dict()))["account_id"] == "demo-balanced"
