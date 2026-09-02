# Integration contract

For Issue #1 (frontend) and Issue #2 (backend). This is what analytics
guarantees, so neither side has to guess.

## Ownership

Analytics owns `src/raptor/analytics/**` and `tests/analytics/**` and touches
nothing else. `src/raptor/__init__.py` is a PEP 420 namespace package, so the
backend can add `raptor.api` and `raptor.agents` in the same tree without
either branch editing a shared file. That is the mechanical reason these
branches merge without a rewrite.

## The entire public API

```python
from raptor.analytics import analyse, PortfolioSnapshot, Position, EquityPoint, HedgeBid

report = analyse(snapshot, bids, config=DEFAULT_CONFIG, generated_at=None)
payload = report.to_dict()   # JSON-native, no custom encoder
```

One function, one return type. Everything else is implementation detail.

`analyse()` is pure: no I/O, no clock, no global state. `generated_at` defaults
to the snapshot's timestamp — pass an explicit value only if you want
wall-clock provenance on the event.

## Backend — what analytics needs from you

Build a `PortfolioSnapshot` from Alpaca state:

```python
snapshot = PortfolioSnapshot(
    account_id="...",
    timestamp=...,          # datetime; naive is assumed UTC
    cash=account.cash,
    equity=account.equity,
    positions=[
        Position(
            symbol=p.symbol,
            quantity=p.qty,             # signed; negative = short
            current_price=p.current_price,
            market_value=p.market_value, # optional, defaults to qty × price
            cost_basis=p.cost_basis,     # optional, enables unrealised P&L
            beta="1.0",                  # optional, defaults to 1.0
            sector="technology",         # optional, defaults to "unclassified"
        )
        for p in alpaca_positions
    ],
    history=[EquityPoint(bar.timestamp, bar.equity) for bar in portfolio_history],
)
```

Constructors accept `int`, `float`, `str` or `Decimal` and coerce safely, so raw
Alpaca JSON can be passed straight through.

Three things to know. Validation raises `ValidationError` (subclass of
`AnalyticsError`) at construction — catch `AnalyticsError` once and map it to a
typed API error. Closed positions must be omitted, not sent with `quantity=0`.
And duplicate symbols are rejected, so merge fills before building the snapshot.

Beta and sector are optional but load-bearing: without them the model flattens
to a plain exposure calculation. If Alpaca doesn't supply them, we should agree
on a static lookup table — flagged as an open question in `WIP.md`.

## Frontend — what you can rely on

Generate mock data from the real code:

```bash
python -m raptor.analytics.cli --seed-frontend
# writes fixtures/frontend_seed/{balanced,concentrated,levered,neutral,empty}.json
python -m raptor.analytics.cli --schema > contract.json
```

Build against those files and the UI will not need reshaping when the backend
lands.

**All numeric values are strings**, not JSON numbers. `"gross_exposure":
"382450.00"`. This is deliberate — floats lose precision crossing into
JavaScript, and money must not. Parse with a decimal library or format as-is
for display.

Report shape:

```
schema_version      "1.0.0"  — pin this; a mismatch should fail loudly
account_id
generated_at        ISO-8601
exposure            gross/net/long/short, beta_adjusted, leverage, cash_ratio
concentration       hhi, effective_positions, top_1/3/5 weights, sector_weights
drawdown            max, current, recovery_needed, ulcer_index, observations
risk                stress_loss, split into directional + idiosyncratic, VaR
score               total, grade (A–F), verdict, components[], flags[]
hedge_evaluations   ranked; index 0 is the winner when is_viable
recommended_bid_id  string or null
```

Two fields worth building UI around specifically. Each entry in
`score.components` has a `rationale` string written for display — render it
next to the component, it is why the score is trustworthy. And `score.flags`
are pre-sorted by severity (critical → warning → info) with a stable `code`,
`message`, `value` and `threshold`, so they can be rendered as an actionable
list without client-side sorting.

`recommended_bid_id` is `null` when no bid passed the viability gates. That is
a real state, not an error — render it as "no acceptable hedge offered", not as
a loading failure.

`verdict` is one of `protected` / `acceptable` / `exposed` / `critical`, and
`grade` is `A`–`F`.

## Stability guarantees

Field names and types will not change without a `SCHEMA_VERSION` bump. Enum
values are lowercase strings and stable. Ordering is deterministic everywhere —
positions by symbol, flags by severity then code, bids by rank with `bid_id` as
the final tie-break — so a UI diff will never show phantom reordering.

## Flag codes

`LEVERAGE_BREACH`, `DIRECTIONAL_BREACH`, `POSITION_CONCENTRATION`,
`SECTOR_CONCENTRATION`, `LOW_DIVERSIFICATION`, `DRAWDOWN_BREACH`,
`STRESS_FAILURE`.

Frontend can map these to icons and copy. Adding a code is backwards
compatible; removing one is not.
