"""Determinism and end-to-end contract tests.

This is the file that defends the core product claim. If RaptorClick is going to
tell someone their portfolio is protected, the same inputs must always produce
the same answer - not approximately, but byte-for-byte.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from raptor.analytics import SCHEMA_VERSION, analyse
from raptor.analytics.samples import (
    balanced_portfolio,
    concentrated_portfolio,
    empty_portfolio,
    levered_portfolio,
    market_neutral_portfolio,
    sample_bids,
)

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden_report.json"


class TestDeterminism:
    def test_repeated_runs_are_byte_identical(self, balanced, bids):
        first = json.dumps(analyse(balanced, bids).to_dict(), sort_keys=True)
        second = json.dumps(analyse(balanced, bids).to_dict(), sort_keys=True)
        assert first == second

    def test_all_fixtures_are_reproducible(self, bids):
        for factory in (
            balanced_portfolio,
            concentrated_portfolio,
            levered_portfolio,
            market_neutral_portfolio,
            empty_portfolio,
        ):
            a = json.dumps(analyse(factory(), bids).to_dict(), sort_keys=True)
            b = json.dumps(analyse(factory(), bids).to_dict(), sort_keys=True)
            assert a == b, f"{factory.__name__} is not deterministic"

    def test_position_input_order_does_not_change_results(self, balanced, bids):
        # Alpaca does not guarantee ordering; our results must not depend on it.
        from raptor.analytics import PortfolioSnapshot

        shuffled = PortfolioSnapshot(
            account_id=balanced.account_id,
            timestamp=balanced.timestamp,
            cash=balanced.cash,
            equity=balanced.equity,
            positions=list(reversed(balanced.positions)),
            history=balanced.history,
        )
        assert analyse(shuffled, bids).to_dict() == analyse(balanced, bids).to_dict()

    def test_bid_input_order_does_not_change_the_recommendation(self, balanced, bids):
        forward = analyse(balanced, bids).recommended_bid_id
        backward = analyse(balanced, list(reversed(bids))).recommended_bid_id
        assert forward == backward

    def test_no_wall_clock_dependency(self, balanced, bids):
        # generated_at defaults to the snapshot timestamp, never datetime.now().
        assert analyse(balanced, bids).generated_at == balanced.timestamp

    def test_analysis_does_not_mutate_its_inputs(self, balanced, bids):
        before = balanced.to_dict()
        analyse(balanced, bids)
        assert balanced.to_dict() == before


class TestReportContract:
    def test_report_has_every_required_section(self, balanced_report):
        payload = balanced_report.to_dict()
        for key in (
            "schema_version", "account_id", "generated_at", "exposure",
            "concentration", "drawdown", "risk", "score", "hedge_evaluations",
            "recommended_bid_id",
        ):
            assert key in payload, f"missing contract key: {key}"

    def test_schema_version_is_pinned(self, balanced_report):
        # The frontend pins this; a mismatch should fail at the seam, not in a demo.
        assert balanced_report.schema_version == SCHEMA_VERSION

    def test_every_bid_is_evaluated(self, balanced, bids):
        assert len(analyse(balanced, bids).hedge_evaluations) == len(bids)

    def test_recommendation_is_always_a_viable_bid(self, balanced, concentrated, levered, bids):
        # We never recommend the "least bad" option - that would undermine the
        # verdict the whole report is built on.
        for snap in (balanced, concentrated, levered):
            report = analyse(snap, bids)
            if report.recommended_bid_id is not None:
                chosen = next(
                    e for e in report.hedge_evaluations
                    if e.bid_id == report.recommended_bid_id
                )
                assert chosen.is_viable

    def test_no_bids_yields_no_recommendation(self, balanced):
        report = analyse(balanced, [])
        assert report.recommended_bid_id is None
        assert report.hedge_evaluations == ()

    def test_all_numeric_fields_serialise_as_strings(self, balanced_report):
        payload = balanced_report.to_dict()
        for section in ("exposure", "concentration", "drawdown", "risk"):
            for key, value in payload[section].items():
                if isinstance(value, (int, bool)) or value is None:
                    continue
                if isinstance(value, dict):
                    continue
                assert isinstance(value, str), f"{section}.{key} is not a string"


class TestGoldenReport:
    """Regression guard: any change to the numbers must be intentional.

    Regenerate deliberately with ``python -m raptor.analytics.cli --golden``
    and review the diff. An unexplained change here means the model moved
    without anyone deciding it should.
    """

    @pytest.mark.skipif(not GOLDEN.exists(), reason="golden file not generated yet")
    def test_output_matches_the_committed_golden_file(self):
        expected = json.loads(GOLDEN.read_text())
        actual = analyse(balanced_portfolio(), sample_bids()).to_dict()
        assert actual == expected
