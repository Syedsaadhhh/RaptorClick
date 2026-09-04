# RaptorClick — One-Page Technical Write-Up

## What it is

RaptorClick is an autonomous portfolio-protection agent built around Alpaca paper trading. Instead of asking one model for a trade, it creates multiple hedge candidates, tests them against the same portfolio state, applies deterministic risk gates, compares the winning proposal with an unprotected Shadow Book, and re-auctions when the market or portfolio drifts far enough to invalidate the original decision.

## AI logic

The AI layer is intentionally narrow. Featherless-hosted LLM inference may suggest a hedge *category* or proposal framing, but it does not control prices, scores, risk limits, or order approval. Every proposal is treated as untrusted input.

The deterministic analytics layer computes exposure, concentration, drawdown, historical volatility, stress losses, hedge payoff, liquidity quality, normalized score components, and Protection Delta. Competing bids can represent protective puts, put spreads, and other defined-risk structures. Missing quote or liquidity data remains unavailable/inconclusive; it is never silently replaced with zero.

## Risk gates

The Risk Governor is outside the LLM. A hedge can be rejected for hard conditions such as excessive premium, insufficient protection, invalid or missing quote data, wide spread, inadequate volume/open interest, excessive notional, or other policy breaches. A failed rule returns a structured reason. There is no fallback path that converts a failed or incomplete proposal into an approval.

Execution is dry-run first. Paper execution must be explicitly enabled and requires a successful dry-run for the same approved run. Idempotency keys prevent duplicate execution requests. Live-money routing is not part of the MVP.

## Alpaca infrastructure

RaptorClick uses the Alpaca paper environment for account state, open positions, market data, option snapshots, and paper order routing. The backend exposes a FastAPI surface for portfolio reads, hedge runs, run-state reads, SSE lifecycle events, execution, and re-auction.

Core API flow:

`Alpaca paper state -> Shock Lab -> competing hedge bids -> deterministic analytics -> Risk Governor -> Shadow Book comparison -> dry-run -> optional Alpaca paper order -> Monitor -> re-auction`

The Monitor detects portfolio/state drift. Once a prior decision is stale, the system emits `reauction_required` and recomputes from fresh state rather than mutating the historical decision.

## What the demo proves

A complete demo should show: a real Alpaca paper portfolio read; multiple materially different hedge bids; an inspectable ranking; at least one deterministic rejection; protected versus unprotected Shadow Book output; Protection Delta net of hedge cost; a dry-run receipt; optional paper-order evidence; typed lifecycle events; and one controlled state change that triggers a new auction.

The key claim is not profitability. The key claim is that autonomous protection can be **observable, reproducible, risk-gated, and auditable** before any paper order is routed.
