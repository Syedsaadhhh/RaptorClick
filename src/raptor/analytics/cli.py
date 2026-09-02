"""Command-line entry point for demos, golden-file generation and schema dump.

Usage:
    python -m raptor.analytics.cli                     # analyse every fixture
    python -m raptor.analytics.cli --fixture balanced  # one fixture, full report
    python -m raptor.analytics.cli --golden            # write fixtures/golden_report.json
    python -m raptor.analytics.cli --schema            # print the JSON schema
    python -m raptor.analytics.cli --seed-frontend     # write frontend seed data

This is the same code the tests exercise, so the demo and the regression suite
cannot drift apart.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

from .samples import (
    balanced_portfolio,
    concentrated_portfolio,
    empty_portfolio,
    levered_portfolio,
    market_neutral_portfolio,
    sample_bids,
)
from .engine import analyse
from .config import DEFAULT_CONFIG

_FIXTURES = {
    "balanced": balanced_portfolio,
    "concentrated": concentrated_portfolio,
    "levered": levered_portfolio,
    "neutral": market_neutral_portfolio,
    "empty": empty_portfolio,
}


def _report_for(name: str) -> Dict[str, Any]:
    return analyse(_FIXTURES[name](), sample_bids()).to_dict()


def build_schema() -> Dict[str, Any]:
    """A hand-maintained JSON schema, kept explicit rather than inferred.

    Auto-generating a schema from the dataclasses sounds appealing and produces
    a document nobody can read. The frontend consumes this directly, so it
    should be written in the shape a human expects.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "RaptorClick ProtectionReport",
        "version": "1.0.0",
        "description": (
            "Deterministic protection analytics output. All Decimal values are "
            "transported as strings to avoid precision loss across the JSON "
            "boundary into JavaScript."
        ),
        "type": "object",
        "required": [
            "schema_version", "account_id", "generated_at", "exposure",
            "concentration", "drawdown", "risk", "score",
            "hedge_evaluations", "recommended_bid_id",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": "1.0.0"},
            "account_id": {"type": "string"},
            "generated_at": {"type": "string", "format": "date-time"},
            "exposure": {"type": "object"},
            "concentration": {"type": "object"},
            "drawdown": {"type": "object"},
            "risk": {"type": "object"},
            "score": {"type": "object"},
            "hedge_evaluations": {"type": "array"},
            "recommended_bid_id": {"type": ["string", "null"]},
        },
    }


def seed_frontend(root: Path) -> Path:
    """Write a fixtures bundle the React control room can import as mock data.

    Generates one report per fixture with a stable file name, so the frontend
    (Issue #1) never has to guess what valid input looks like.
    """
    out = root / "fixtures" / "frontend_seed"
    out.mkdir(parents=True, exist_ok=True)
    for name in _FIXTURES:
        payload = _report_for(name)
        path = out / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2))
    sample = {"market_context": "2025-08-31", "bids": [b.to_dict() for b in sample_bids()]}
    (out / "bids.json").write_text(json.dumps(sample, indent=2))
    return out


def _print_report(name: str) -> None:
    payload = _report_for(name)
    score = payload["score"]
    risk = payload["risk"]
    print(f"=== {name} ===")
    print(f"  score    : {score['total']} ({score['grade']}) -> {score['verdict']}")
    print(f"  exposure : gross {payload['exposure']['gross_exposure']} "
          f"net {payload['exposure']['net_exposure']} "
          f"lev {payload['exposure']['gross_leverage']}x")
    print(f"  conc     : hhi {payload['concentration']['hhi']} "
          f"eff {payload['concentration']['effective_positions']} positions "
          f"top {payload['concentration']['top_position_weight']} "
          f"[{payload['concentration']['largest_symbol']}]")
    print(f"  drawdown : max {payload['drawdown']['max_drawdown']} "
          f"current {payload['drawdown']['current_drawdown']} "
          f"ulcer {payload['drawdown']['ulcer_index']}")
    print(f"  risk     : {risk['scenario_name']} loss {risk['stress_loss']} "
          f"({risk['stress_loss_pct']}%) var {risk['parametric_var']}")
    print(f"  hedge    : {len(payload['hedge_evaluations'])} bids, "
          f"recommend {payload['recommended_bid_id']}")
    for flag in score["flags"]:
        print(f"    ! [{flag['severity'].upper()}] {flag['message']}")
    print()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raptor-analytics")
    parser.add_argument(
        "--fixture", choices=sorted(_FIXTURES),
        help="analyse a single fixture and print its full report JSON",
    )
    parser.add_argument("--all", action="store_true", help="summarise every fixture")
    parser.add_argument(
        "--golden", action="store_true",
        help="write fixtures/golden_report.json (regenerate deliberately)",
    )
    parser.add_argument("--schema", action="store_true", help="print the JSON schema")
    parser.add_argument(
        "--seed-frontend",
        action="store_true",
        help="write fixtures/frontend_seed/*.json for the React control room",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[3]

    if args.fixture:
        print(json.dumps(_report_for(args.fixture), indent=2))
        return 0

    if args.all:
        for name in _FIXTURES:
            _print_report(name)
        return 0

    if args.golden:
        target = root / "fixtures" / "golden_report.json"
        target.write_text(json.dumps(_report_for("balanced"), indent=2))
        print(f"wrote {target}")
        return 0

    if args.schema:
        print(json.dumps(build_schema(), indent=2))
        return 0

    if args.seed_frontend:
        out = seed_frontend(root)
        print(f"wrote frontend seed data to {out}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
