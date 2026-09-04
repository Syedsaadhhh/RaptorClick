"""Tests for the scoring engine and verdict logic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from raptor.analytics import (
    CONSERVATIVE_CONFIG,
    DEFAULT_CONFIG,
    AnalyticsConfig,
    ConfigError,
    Severity,
    Verdict,
    analyse,
    band_score,
    grade_for,
)


class TestBandScore:
    def test_anchors_map_to_the_endpoints(self):
        assert band_score("1.0", good="1.0", bad="2.0") == Decimal("100.0000")
        assert band_score("2.0", good="1.0", bad="2.0") == Decimal("0.0000")

    def test_midpoint_interpolates_linearly(self):
        assert band_score("1.5", good="1.0", bad="2.0") == Decimal("50.0000")

    def test_values_beyond_the_anchors_are_clamped(self):
        assert band_score("0.1", good="1.0", bad="2.0") == Decimal("100.0000")
        assert band_score("9.9", good="1.0", bad="2.0") == Decimal("0.0000")

    def test_higher_is_better_inverts_the_direction(self):
        assert band_score("1.0", good="1.0", bad="0", higher_is_better=True) == Decimal("100.0000")
        assert band_score("0.5", good="1.0", bad="0", higher_is_better=True) == Decimal("50.0000")

    def test_scoring_is_continuous_not_stepped(self):
        # Cliff edges make a demo look broken and are bad risk measurement.
        a = band_score("1.4999", good="1.0", bad="2.0")
        b = band_score("1.5001", good="1.0", bad="2.0")
        assert abs(a - b) < Decimal("1")

    def test_degenerate_band_does_not_divide_by_zero(self):
        assert band_score("1.0", good="1.0", bad="1.0") == Decimal("100")
        assert band_score("2.0", good="1.0", bad="1.0") == Decimal("0")


class TestGrades:
    @pytest.mark.parametrize(
        "total, grade",
        [("95", "A"), ("80", "A"), ("70", "B"), ("60", "B"),
         ("45", "C"), ("40", "C"), ("25", "D"), ("10", "F")],
    )
    def test_grade_bands(self, total, grade):
        assert grade_for(Decimal(total)) == grade


class TestScoring:
    def test_balanced_portfolio_scores_well(self, balanced, bids):
        report = analyse(balanced, bids)
        assert report.score.total >= DEFAULT_CONFIG.score_acceptable
        assert report.score.verdict in (Verdict.PROTECTED, Verdict.ACCEPTABLE)

    def test_levered_portfolio_scores_poorly(self, levered, bids):
        report = analyse(levered, bids)
        assert report.score.verdict in (Verdict.EXPOSED, Verdict.CRITICAL)

    def test_concentrated_portfolio_is_penalised(self, concentrated, balanced, bids):
        worse = analyse(concentrated, bids).score
        better = analyse(balanced, bids).score
        assert worse.total < better.total

    def test_components_are_all_present_and_weighted(self, balanced_report):
        components = {c.name for c in balanced_report.score.components}
        assert components == {"exposure", "concentration", "drawdown", "hedge"}
        weights = sum(c.weight for c in balanced_report.score.components)
        assert weights == Decimal("1.00")

    def test_every_component_carries_a_rationale(self, balanced_report):
        # A score with no explanation is not something a user will act on.
        for component in balanced_report.score.components:
            assert component.rationale.strip()
            assert component.rationale.endswith(".")

    def test_contribution_is_score_times_weight(self, balanced_report):
        for c in balanced_report.score.components:
            assert c.contribution == pytest.approx(
                c.score * c.weight, abs=Decimal("0.01")
            )

    def test_total_is_bounded(self, balanced, concentrated, levered, empty, bids):
        for snap in (balanced, concentrated, levered, empty):
            total = analyse(snap, bids).score.total
            assert Decimal("0") <= total <= Decimal("100")

    def test_missing_history_scores_neutral_not_perfect(self, empty, bids):
        # A fresh account has not demonstrated resilience.
        drawdown = next(
            c for c in analyse(empty, bids).score.components if c.name == "drawdown"
        )
        assert drawdown.score == Decimal("50")
        assert "insufficient" in drawdown.rationale.lower()


class TestRiskFlags:
    def test_levered_portfolio_raises_a_leverage_flag(self, levered, bids):
        codes = {f.code for f in analyse(levered, bids).score.flags}
        assert "LEVERAGE_BREACH" in codes

    def test_concentrated_portfolio_raises_a_concentration_flag(self, concentrated, bids):
        codes = {f.code for f in analyse(concentrated, bids).score.flags}
        assert "POSITION_CONCENTRATION" in codes

    def test_healthy_portfolio_raises_no_flags(self, balanced, bids):
        assert analyse(balanced, bids).score.flags == ()

    def test_flags_are_sorted_by_severity(self, levered, bids):
        flags = analyse(levered, bids).score.flags
        rank = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
        order = [rank[f.severity] for f in flags]
        assert order == sorted(order)

    def test_every_flag_reports_value_against_threshold(self, levered, bids):
        for flag in analyse(levered, bids).score.flags:
            assert flag.metric and flag.message
            assert isinstance(flag.value, Decimal)


class TestOverrides:
    def test_critical_flag_caps_the_headline_score(self, levered, bids):
        # The guard against a weighted average laundering one fatal risk
        # behind three healthy components.
        report = analyse(levered, bids)
        assert any(f.severity is Severity.CRITICAL for f in report.score.flags)
        assert report.score.total < DEFAULT_CONFIG.score_acceptable

    def test_stress_failure_forces_the_lowest_band(self, levered, bids):
        report = analyse(levered, bids)
        if any(f.code == "STRESS_FAILURE" for f in report.score.flags):
            assert report.score.total < DEFAULT_CONFIG.score_exposed


class TestConfig:
    def test_weights_must_sum_to_one(self):
        with pytest.raises(ConfigError, match="must sum to 1.0"):
            AnalyticsConfig(
                weight_exposure=Decimal("0.5"),
                weight_concentration=Decimal("0.5"),
                weight_drawdown=Decimal("0.5"),
                weight_hedge=Decimal("0.5"),
            )

    def test_verdict_bands_must_decrease(self):
        with pytest.raises(ConfigError, match="strictly decrease"):
            AnalyticsConfig(
                score_protected=Decimal("50"),
                score_acceptable=Decimal("60"),
                score_exposed=Decimal("70"),
            )

    def test_unknown_primary_scenario_is_rejected(self):
        with pytest.raises(ConfigError, match="not among the configured"):
            AnalyticsConfig(primary_scenario="apocalypse")

    def test_conservative_config_is_stricter(self, balanced, bids):
        # Thresholds are policy, not physics - and the difference is visible.
        default = analyse(balanced, bids, DEFAULT_CONFIG).score.total
        strict = analyse(balanced, bids, CONSERVATIVE_CONFIG).score.total
        assert strict <= default

    def test_with_overrides_coerces_and_validates(self):
        cfg = DEFAULT_CONFIG.with_overrides(max_hhi=0.25)
        assert cfg.max_hhi == Decimal("0.25")
        with pytest.raises(ConfigError, match="unknown config field"):
            DEFAULT_CONFIG.with_overrides(not_a_field=1)

    def test_config_is_serialisable_for_reproducibility(self):
        payload = DEFAULT_CONFIG.to_dict()
        assert payload["primary_scenario"] == "bear_shock"
        assert len(payload["scenarios"]) == 4
