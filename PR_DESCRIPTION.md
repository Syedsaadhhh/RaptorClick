# Analytics: protection metrics, scoring and tests (Issue #3)

## Outcome

This PR supplies the pure, deterministic analytics package for RaptorClick.
The backend calls `analyse(snapshot, bids)` and serializes `report.to_dict()`;
the frontend can build fixtures from the same versioned JSON contract.

## Included

- Typed immutable inputs and outputs using `Decimal` for financial values.
- Symbol/sector exposure, concentration, drawdown, and historical volatility
  from supplied bars.
- Named deterministic stress scenarios and parametric VaR.
- Protective-put, put-spread, and defined-risk collar candidates using one bid
  shape.
- Premium, maximum-risk, payoff, residual-loss, quote-spread, volume, and
  open-interest calculations.
- A normalized 0-100 bid score with visible protection, efficiency, liquidity,
  and premium components.
- Protected versus Shadow Book loss and Protection Delta net of hedge cost.
- Deterministic portfolio-drift detection that marks a prior ranking stale.
- Synthetic fixtures, frontend JSON seeds, a committed golden report, pitch
  notes, and pytest coverage for every Issue #3 edge case.

Missing/incomplete market data is returned as `unavailable` or `inconclusive`
with numeric values set to `null`. It never becomes a fabricated zero. A bid
with unavailable or failed liquidity cannot be recommended.

## Ranking change after state change

The committed acceptance test uses the same two candidates before and after a
named market-state change:

| State | Stress loss | Rank 1 | Score | Rank 2 | Score |
|---|---:|---|---:|---|---:|
| `mild_correction` | $6,929.27 | `first-loss` | 74.9333 | `high-buffer` | 28.2667 |
| `crisis` | $53,364.39 | `high-buffer` | 87.6467 | `first-loss` | 74.9333 |

The high-buffer put is rejected in the mild state because the loss remains
inside its deductible. Under crisis stress it becomes the stronger proposal.
This is deterministic and covered by
`test_ranking_changes_when_stress_state_changes`.

## Verification

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/analytics -q
python -m raptor.analytics.cli --all
```

All tests pass locally on Python 3.12. The package declares Python 3.10+ and has
no runtime dependencies.

## Integration notes

- Contract version: `1.1.0`.
- All serialized decimals are strings; unavailable values are JSON `null`.
- `recommended_bid_id` is `null` when every bid fails a hard gate.
- Analytics performs no I/O, reads no secrets, and cannot place orders.
- Execution remains dry-run/paper-only in the backend.

## Intentionally out of scope

Option Greeks and repricing, a full correlation matrix, beta estimation,
multi-currency conversion, persistence, and broker execution remain outside
this analytics checkpoint. See `docs/analytics/WIP.md`.
