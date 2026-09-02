# Pitch notes — the protection analytics angle

Rough notes for the deck and the demo. Issue #3 deliverable.

## The one-liner

> Most trading agents optimise for return and bolt risk on afterwards.
> RaptorClick scores **protection** as a first-class output — deterministically,
> so the same portfolio always gets the same verdict.

## The problem worth naming on stage

Every AI trading agent in this hackathon will show a P&L curve. The interesting
question is not "did it make money", it is **"what happens when it doesn't"** —
and almost nothing in retail tooling answers that in a way a user can check.

Two specific failures we attack:

**Naive risk models call market-neutral books safe.** Net exposure near zero,
so directional loss near zero, so the dashboard shows green. In an actual crash
correlations converge and a concentrated "neutral" book bleeds anyway. Our
model has an explicit idiosyncratic term scaled by HHI and by how much
diversification fails in each scenario. The `market_neutral` fixture is the
demo: net exposure exactly 0, stress loss 9.13%, verdict downgraded.

**Hedge shopping gets ranked on price.** The cheapest hedge is worthless if it
doesn't pay out. Our auction ranks on *net benefit* — modelled payout minus
premium — and rejects bids on three gates: premium ceiling, minimum coverage,
minimum cost efficiency. The `ThinShield` bid in the sample set is designed to
look cheap and get rejected for covering almost nothing.

## The differentiator judges can verify

**Determinism.** Run it twice, get byte-identical JSON. No clock, no randomness,
no ambient state, Decimal throughout, sorted iteration everywhere. There is a
test that reverses every input list and asserts the output is unchanged.

This matters more than it sounds. Most LLM-driven agents cannot tell you why
they said what they said, or reproduce it tomorrow. We can hand a judge the
snapshot and the config and they can re-derive the score with a calculator.

**Explainability by construction.** Every score component carries a `rationale`
string in the payload, not a tooltip added later:

> "Gross leverage 2.31x breaches the 1.5x limit; a shock is amplified against
> equity."

> "HHI 0.8123 implies 1.2311 effective positions; NVDA at 0.8912 exceeds the
> 0.25 single-name cap (-25 points)."

**Hard overrides.** A weighted average can launder one fatal risk behind three
healthy components. Any critical flag caps the headline score below
"acceptable"; a stress-test failure caps it below "exposed". A book that cannot
survive its own stress scenario is never labelled acceptable, whatever the
average says.

## Demo script (60 seconds)

Open on `balanced` — 95.46, grade A, protected, zero flags. This is what good
looks like.

Switch to `market_neutral`. Point at net exposure: **zero**. Say: "a
directional risk model stops here and shows green." Then the score: 70.78, four
flags. The concentration term caught what the directional term missed.

Switch to `levered` — 39.99, critical, six flags, 80.95% stress loss. Note the
score is capped by the override, not by the average.

Run the hedge auction. Five bids come in; show that the winner is not the
cheapest, and read out the rejection reason on `ThinShield`.

Close by running the same analysis twice and diffing the JSON. Identical.

## Lines that land

"We don't predict the crash. We price what it costs you."

"Every number in this report can be re-derived on paper. That's a deliberate
constraint, not a limitation."

"A 50% drawdown needs a 100% gain to recover. We report that asymmetry as its
own field, because it's the number retail traders consistently underestimate."

"Concentration isn't a display metric here — it's an input to the loss
calculation."

## What to be honest about if asked

Options are modelled as payoff functions, not greeks. Correlation is a scalar
per scenario, not a matrix. Betas come from the backend, and default to 1.0 if
absent. Scenarios are fixed and named rather than simulated — that is a
deliberate trade of sophistication for reproducibility, and we should say so
before a judge points it out.
