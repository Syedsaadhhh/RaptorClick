# RaptorClick pitch story (working draft)

## Why protection is the problem

Most trading agents focus on finding the next trade. That is useful until the
market moves the wrong way. RaptorClick starts with the portfolio already in
front of us and asks a narrower question: what is the smallest useful hedge we
should buy now, and when has the state changed enough to replace it?

## Why independent bids beat one black box

A protective put, a put spread, and a collar make different trade-offs. One
may cover the first loss but cost too much. Another may be cheap but stop paying
when the drawdown gets serious. Independent agents submit the candidates, then
deterministic code checks the quotes and ranks every bid on the same visible
components. No agent can promote its own answer or bypass a failed risk rule.

## What the Shadow Book proves

The Shadow Book keeps the same portfolio unhedged. That gives us a fair
counterfactual: the protected and unprotected books face the same named shock,
so the difference comes from the hedge rather than a different market path.

## What Protection Delta means

Protection Delta is the loss avoided after paying for the hedge:

`hedge payout - hedge premium`

A positive value means the hedge reduced the modeled loss net of cost. A
negative value is allowed and useful because it shows that protection was too
expensive for that scenario.

## Thirty-second demo ending

Show two bids under the mild correction. The first-loss spread ranks first and
the high-buffer put fails because the shock never clears its deductible. Switch
to the crisis state. The same inputs are recalculated, the high-buffer put moves
to first place, and the Monitor marks the old ranking stale. End on the Shadow
Book comparison: the protected loss is lower, the premium is visible, and
Protection Delta states exactly how much loss the selected hedge avoided.
