# What is still incomplete

Requested explicitly by the team lead. Honest status as of this draft PR.

## Verified

The full pipeline runs end to end against all five fixtures and produces
sensible, discriminating output:

| fixture | score | verdict | stress loss | flags |
|---|---|---|---|---|
| balanced | 95.46 | protected | 16.59% | 0 |
| market_neutral | 70.78 | acceptable | 9.13% | 4 |
| concentrated | 39.99 | critical | 36.83% | 4 |
| levered | 39.99 | critical | 80.95% | 6 |
| empty | 90.00 | protected | 0.00% | 0 |

The model separates the cases it is supposed to separate, and the
market-neutral book scores below the balanced one despite near-zero net
exposure — which is the behaviour the whole idiosyncratic term exists to
produce.

## Not yet verified — needs a run on your machine

**The pytest suite has not been executed.** The environment I built this in has
no network, so pytest could not be installed, and the sandbox became
unresponsive before I could finish running a stdlib fallback harness. The tests
are written against real pytest conventions (fixtures, `parametrize`, `raises`)
and the code they exercise is smoke-tested, but treat the suite as unrun until
CI is green.

First thing to do:

```bash
pip install -e ".[dev]"
pytest tests/analytics -v
```

Expect possible small fixes in the hand-computed expectations — a few assert
exact quantised values (e.g. `Decimal("0.0833")`) where the real output may
differ in the last decimal place. Those are test-side corrections, not model
bugs.

**The golden file is not generated.** `fixtures/golden_report.json` does not
exist yet, and `test_output_matches_the_committed_golden_file` skips itself
until it does. I deliberately did not hand-write it — a golden file made up by
hand is worse than no golden file. Generate it from the code once the suite
passes:

```bash
python -m raptor.analytics.cli --golden
```

Then commit it and review the diff on every future change.

## Known gaps

Options greeks are not modelled. A put is treated as a payoff function, not a
delta/gamma position, so an option-heavy book will be approximated rather than
priced. Fine for the checkpoint, wrong for a real options desk.

Beta is per-position input, not estimated. If the backend cannot supply betas,
everything defaults to 1.0 and the directional term becomes a plain exposure
calculation.

Correlation is a single scalar per scenario (`correlation_uplift`) rather than
a matrix. This is a deliberate simplification for determinism and
explainability, but it means we cannot express "tech and energy decouple in
this scenario".

Intraday and multi-currency are out of scope. Everything assumes one currency
and end-of-period equity points.

No persistence layer. `analyse()` is a pure function; storing reports is the
backend's call, which keeps Issue #2 and Issue #3 cleanly separated.

## Open questions for the team

For the backend (Issue #2): does the Alpaca snapshot include per-position beta
and sector, or should analytics carry a static lookup table? Right now both are
optional inputs with safe defaults, so nothing blocks, but the defaults will
flatten the model if they are never populated.

For the frontend (Issue #1): `report.to_dict()` is the contract, and
`--seed-frontend` writes one JSON file per fixture to build mocks against. If
any field name or shape does not suit the control room, say so now — changing
it after both sides are built is the rewrite we agreed to avoid.

Should `SCHEMA_VERSION` be echoed on the event bus? I have pinned it at
`1.0.0` and the frontend test asserts it, so a mismatch fails at the seam
rather than during a demo.
