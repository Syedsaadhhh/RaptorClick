# Remaining analytics work

Issue #3's first complete contract is implemented and tested. These limitations
remain visible so nobody mistakes the hackathon model for production risk
software.

- Options use deterministic payoff functions, not delta/gamma/vega repricing.
- Position beta is supplied by the caller and defaults to `1.0`; analytics does
  not estimate beta or fabricate sector classifications.
- Scenario correlation is one documented scalar rather than a correlation
  matrix.
- Price-bar volatility is close-to-close historical volatility. It is not an
  implied-volatility surface.
- Multi-currency conversion, intraday aggregation, persistence, and execution
  are outside this package.
- A spread or collar currently accepts aggregate liquidity fields. The backend
  should pass conservative combined values for multi-leg structures until the
  shared contract grows per-leg quote objects.

Before merging, Saad and Reann should confirm the `1.1.0` JSON field names in
`docs/analytics/INTEGRATION.md`. Backend approval and Alpaca paper execution
remain separate hard gates; analytics never sends an order.
