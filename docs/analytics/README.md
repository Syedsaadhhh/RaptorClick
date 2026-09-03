# Protection Analytics

Deterministic risk and hedge analytics for RaptorClick. Issue #3.

Input a portfolio snapshot and a set of competing hedge bids; output a
`ProtectionReport` — a 0–100 protection score, a verdict, a ranked hedge
auction, and a set of machine-readable risk flags.

```python
from raptor.analytics import analyse
from raptor.analytics.samples import balanced_portfolio, sample_bids

report = analyse(balanced_portfolio(), sample_bids())
print(report.score.total, report.score.verdict, report.recommended_bid_id)
report.to_dict()   # JSON-ready, no custom encoder
```

## The one property that matters

**Same inputs, byte-identical output. Always.**

The pitch is "deterministic protection". If two runs over the same snapshot
disagree, the claim is dead. Four rules enforce it:

`Decimal` end to end, with floats converted via `repr` at the boundary only.
A pinned decimal context and banker's rounding, so no ambient state can change
a result. Sorted iteration everywhere — positions by symbol, flags by severity,
bids by a rank tuple ending in `bid_id` — so input order never leaks into
output. And no clock: `generated_at` is an injected parameter that defaults to
the snapshot's own timestamp, never `datetime.now()`.

`tests/analytics/test_determinism.py` asserts all of this, including that
reversing the input order changes nothing.

## The risk model

Stress loss splits into two terms:

```
stress_loss        = directional_loss + idiosyncratic_loss
directional_loss   = |beta-adjusted net exposure| × market_shock
idiosyncratic_loss = gross_exposure × market_shock × correlation_uplift × HHI
```

The first term is textbook. **The second term is the reason this is worth
building.**

A market-neutral book has near-zero directional loss, and a naive model calls
it safe. In a real crash correlations converge toward 1 and a concentrated
"neutral" book bleeds anyway. `correlation_uplift` encodes how much
diversification benefit evaporates in a given scenario; HHI scales it by how
few names actually carry the book. The `market_neutral_portfolio` fixture
exists to demonstrate exactly this: net exposure 0, stress loss decidedly not 0.

Scenarios are fixed and named (`mild_correction`, `correction`, `bear_shock`,
`crisis`), not simulated. A Monte Carlo run would look more sophisticated and
be unreproducible without seed plumbing. Every number here is arithmetic a
judge can re-derive on paper.

Parametric VaR is reported alongside, but deliberately does not drive the
verdict — it is backward-looking and blind to the tail, which is precisely what
a hedge is bought for.

## The hedge auction

Payoff is piecewise-linear with a deductible:

```
covered_loss = max(0, stress_loss − buffer_pct × notional)
payout       = min(covered_loss × coverage_ratio, max_payout)
net_benefit  = payout − premium
```

Instrument type matters — a put spread caps out, an inverse ETF does not.
Collapsing them into one linear model would make the auction rank on price
alone, which is the naive behaviour RaptorClick exists to beat.

Bids rank by viability, then the normalized score, net benefit, coverage,
premium, and `bid_id` as the final deterministic tie-break. The normalized
score exposes protection, cost-efficiency, liquidity, and premium components.
Hard gates cover premium, minimum coverage, efficiency, quote validity, spread,
volume, open interest, and excessive notional. Every rejection carries an
inspectable reason.

The selected bid is compared with the unprotected Shadow Book under the same
scenario. `Protection Delta = payout - premium`, so cost is never hidden.

If no bid clears the gates, `recommended_bid_id` is `None`. We never recommend
the least-bad option; that would undermine the verdict the report is built on.

## Scoring

Four weighted components — exposure 30%, concentration 25%, drawdown 20%,
hedge 25% — each scored 0–100 by a piecewise-linear band function.

Piecewise-linear was chosen over a step function (cliff edges make a portfolio
flip from 80 to 40 on a rounding change, which looks broken in a demo and *is*
broken as measurement) and over a logistic curve (smooth, but nobody can
re-derive it by hand). Explainability wins when a user is deciding whether to
trust the agent with money.

Every component carries a `rationale` string. **A score with no explanation is
not something a user will act on**, and the control room renders these directly.

**Hard overrides** guard the central weakness of weighted averages: a book can
be catastrophically levered and still score respectably because three other
components are clean. Any critical flag caps the total below the "acceptable"
band; a stress-test failure caps it below "exposed". One fatal risk cannot be
laundered behind healthy averages.

Missing equity history scores a neutral 50, not 100 — a fresh account has not
demonstrated resilience, and rewarding absent data would let any new account
claim maximum protection.

## Layout

```
src/raptor/analytics/
  _num.py      Decimal primitives, pinned context, safe division
  errors.py    single exception hierarchy for the backend to catch
  types.py     frozen dataclasses, validation, to_dict() contract
  config.py    every threshold, weight and scenario in one frozen object
  exposure.py  gross/net/beta exposure, HHI, top-N, sector weights
  drawdown.py  max/current drawdown, recovery, ulcer index
  volatility.py realized volatility from supplied market bars
  hedge.py     stress scenarios, VaR, liquidity, payoff and bid ranking
  counterfactual.py Shadow Book and net Protection Delta
  drift.py     stale-state and re-auction decision
  scoring.py   band scoring, flags, overrides, verdict
  engine.py    analyse() — the single public entry point
  samples.py   five deterministic fixtures
  cli.py       demo, golden-file generation, schema dump, frontend seed
tests/analytics/
  test_types.py test_exposure.py test_drawdown.py
  test_hedge.py test_scoring.py test_determinism.py test_issue3_acceptance.py
```

Thresholds live in `AnalyticsConfig`, never inline. Scattered constants are the
fastest way to lose determinism — two callers end up with two different notions
of "too concentrated" and the scores stop being comparable. `CONSERVATIVE_CONFIG`
demonstrates that they are policy, not physics.

## CLI

```bash
python -m raptor.analytics.cli --all              # summarise every fixture
python -m raptor.analytics.cli --fixture levered  # one full report as JSON
python -m raptor.analytics.cli --schema           # JSON schema
python -m raptor.analytics.cli --seed-frontend    # mock data for Issue #1
python -m raptor.analytics.cli --golden           # regenerate the golden file
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/analytics -v
```

Expectations are hand-computed from short explicit inputs wherever possible. A
test that recomputes a metric using the code under test proves nothing.
