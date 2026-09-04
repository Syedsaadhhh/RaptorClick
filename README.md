# RaptorClick

### An autonomous portfolio insurance market built on Alpaca

RaptorClick does not ask one model to guess the next winning trade. It asks a stricter question:

> What is the smallest, most useful hedge this portfolio should buy now, and when should that protection be replaced?

Specialized hedge agents compete to protect a real Alpaca paper portfolio. Their proposals are stress-tested, ranked against an unprotected shadow portfolio, checked by deterministic risk rules, and either rejected or sent to Alpaca for paper execution.

**Current status:** the FastAPI vertical slice, deterministic analytics, and React control room are merged into `main`. The dashboard retains a labelled replay adapter while live REST/SSE wiring is completed in [Issue #7](https://github.com/Syedsaadhhh/RaptorClick/issues/7). Backend run state is currently in memory, so serverless persistence is not yet production-ready. Nothing here is a claim of profitability or live-money readiness.

## Why this exists

Most autonomous trading demos focus on finding entries. That leaves the harder operational questions unresolved:

- How much downside is the portfolio carrying right now?
- Which hedge is worth its premium under the current regime?
- Is a protective put better than a cheaper spread for this exact portfolio?
- Did the hedge materially improve the outcome, or merely add cost?
- When has the market changed enough to make the original protection stale?

RaptorClick treats protection as a market of competing proposals rather than a single opaque recommendation.

## The core loop

1. **Portfolio Sentinel** reads the Alpaca paper account, positions, exposure, concentration, drawdown, and market state.
2. **Shock Lab** creates deterministic downside scenarios for the current portfolio.
3. **Hedge Agents** independently propose protective puts, put spreads, and other defined-risk candidates.
4. **Hedge Auction** ranks valid bids by protection, cost, liquidity, risk reduction, and fit.
5. **Counterfactual Judge** compares the proposed protected portfolio with a Shadow Book that remains unhedged.
6. **Risk Governor** applies hard limits that an agent cannot override.
7. **Execution Agent** creates a dry-run receipt or submits an approved paper order through Alpaca.
8. **Monitor** watches for state drift. If the hedge becomes stale, the system starts a new auction.

~~~mermaid
flowchart TD
    A["Alpaca paper account and market data"] --> B["Portfolio Sentinel"]
    B --> C["Shock Lab"]
    C --> D["Competing hedge agents"]
    D --> E["Hedge Auction"]
    E --> F["Counterfactual Judge"]
    F --> G["Deterministic Risk Governor"]
    G -->|approved| H["Alpaca paper execution"]
    G -->|rejected| D
    H --> I["Protected Book"]
    F --> J["Shadow Book"]
    I --> K["Protection comparator"]
    J --> K
    K -->|state drift| B
~~~

## The proof that matters

RaptorClick is successful only if the demo proves all of the following:

- It reads real account and market state from Alpaca.
- Multiple agents return materially different hedge bids.
- The auction explains why one valid proposal outranks the others.
- The Risk Governor can reject an attractive but invalid proposal.
- The Shadow Book shows what would have happened without protection.
- **Protection Delta** shows the measured change between protected and unprotected outcomes, net of hedge cost.
- A changed portfolio or market state invalidates stale assumptions and triggers re-auction.
- Every step produces a timestamped event or execution receipt.

A polished dashboard without this loop is not the product.

## MVP completion contract

The first complete vertical slice will:

- load an Alpaca paper portfolio and an options chain;
- calculate exposure, concentration, drawdown, volatility, and stress scenarios;
- produce at least three typed hedge bids;
- score and rank those bids deterministically;
- issue a structured approval or rejection from the Risk Governor;
- support dry-run mode before any paper order is placed;
- stream the run state and decisions to the dashboard;
- maintain protected and shadow portfolio snapshots; and
- trigger one visible re-auction after a controlled state change.

## Agent responsibilities

| Component | Owns | Must not own |
|---|---|---|
| Portfolio Sentinel | Portfolio state, exposure and trigger detection | Trade approval |
| Shock Lab | Reproducible stress scenarios | Narrative market predictions |
| Hedge Agents | Independent typed hedge proposals | Final ranking or execution |
| Hedge Auction | Comparable scoring and ranking | Bypassing invalid bids |
| Counterfactual Judge | Protected versus shadow comparison | Editing risk limits |
| Risk Governor | Position, cost, liquidity and exposure gates | Creative strategy generation |
| Execution Agent | Idempotent dry-run and Alpaca paper orders | Silent retries or live-money routing |
| Monitor | Drift detection and re-auction triggers | Rewriting historical receipts |

LLMs may interpret context and propose candidates. Numeric calculations, scoring, limits, order validation, and final execution gates remain deterministic.

## Dashboard

The interface is a control room for the insurance cycle, not a wall of decorative trading cards.

The MVP dashboard will expose:

- current portfolio risk and protection state;
- Shock Lab scenarios and estimated downside;
- live agent status and hedge bids;
- auction ranking with cost/protection trade-offs;
- Risk Governor verdict and failed rules;
- protected versus Shadow Book comparison;
- Protection Delta;
- order receipts and execution status; and
- the event that caused a re-auction.

The activity stream will show tool events, concise decision summaries, risk checks, and state transitions. It will not expose private chain-of-thought.

## Stack

| Layer | Choice |
|---|---|
| Brokerage and market data | Alpaca Trading API, Market Data API and paper environment |
| Backend | Python, FastAPI and Pydantic |
| Analytics | Deterministic Python modules with pytest coverage |
| Frontend | React, TypeScript, Tailwind CSS and shadcn/ui |
| Charts | TradingView Lightweight Charts or an equivalent lightweight React integration |
| Live updates | REST snapshots plus Server-Sent Events |
| Execution mode | Dry-run first, Alpaca paper trading second |
| Secrets | Local environment variables only; never committed |

The exact dependency versions will be committed with the first implementation pull requests.

## API direction

These contracts are intentionally small so frontend and backend work can proceed in parallel:

| Method | Route | Purpose |
|---|---|---|
| GET | /api/v1/portfolio | Current portfolio and risk snapshot |
| POST | /api/v1/runs | Start a hedge-auction run |
| GET | /api/v1/runs/{run_id} | Read the latest run state |
| GET | /api/v1/runs/{run_id}/events | Stream typed run events over SSE |
| POST | /api/v1/runs/{run_id}/execute | Dry-run or paper-execute an approved bid |
| POST | /api/v1/runs/{run_id}/reauction | Trigger a controlled re-auction demo |

Schemas will be versioned. Frontend fixtures must be labelled as demo data and match the backend models.

## Delivery status

| Area | State |
|---|---|
| Deterministic analytics and tests | Merged |
| FastAPI + Alpaca/Featherless vertical slice | Merged |
| React control-room UI | Merged |
| Frontend live REST/SSE adapter | In progress — Issue #7 |
| Vercel configuration | Merged; projects still need importing |
| Durable run/receipt storage | Not yet implemented |
| Pitch/demo package | In progress — Issue #8 |

## Team

| Member | Ownership |
|---|---|
| **Saad** | Team lead; backend, agent orchestration, Alpaca integration, Risk Governor and end-to-end delivery |
| **Reann / Mafu** ([reavelle](https://github.com/reavelle)) | Frontend lead; control-room UI, live state visualization, charts and responsive experience |
| **Shamveel** ([shamveelmazhar](https://github.com/shamveelmazhar)) | Deterministic analytics, tests, visual direction, pitch story and demo support |

## Working agreement

- Use one branch per task and open a pull request into **main**.
- Keep pull requests small enough to review quickly.
- Put shared request, response, and event shapes in one versioned contract.
- Never commit Alpaca keys, tokens, account identifiers, or private screenshots.
- Mark fixtures, simulations, and placeholder values clearly.
- Do not claim performance numbers that were not produced by a repeatable test.
- Execution defaults to dry-run. Paper trading must be explicitly enabled.
- A failed risk rule returns a structured rejection; it never silently falls back to approval.

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Put private credentials only in `backend/.env`. Keep `ENABLE_PAPER_EXECUTION=false` until the dry-run is verified.

### Frontend

From the repository root:

```bash
cp .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

### Verification

```bash
curl http://localhost:8000/healthz
npm run check
npm run build
pytest
cd backend && pytest
```

## Environment variables

Frontend (public): `VITE_API_BASE_URL`.

Backend (private): `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `ALPACA_PAPER_BASE_URL`, `ALPACA_DATA_BASE_URL`, `FEATHERLESS_API_KEY`, `FEATHERLESS_BASE_URL`, `FEATHERLESS_MODEL`, `RAPTORCLICK_DEMO_MODE`, `ENABLE_PAPER_EXECUTION`, and `FRONTEND_ORIGIN`.

Anything prefixed with `VITE_` is exposed to the browser. Alpaca and Featherless secrets belong only in the backend environment.

## Deploy on Vercel

Create two Vercel projects from this repository:

1. **Backend:** root directory `backend`, Framework Preset **Other**. Add the private backend variables, deploy, and verify `https://<backend>.vercel.app/healthz`.
2. **Frontend:** repository root. Set `VITE_API_BASE_URL=https://<backend>.vercel.app`, then deploy.
3. Set backend `FRONTEND_ORIGIN=https://<frontend>.vercel.app` and redeploy the backend.

Start with `ENABLE_PAPER_EXECUTION=false`. The root and backend `vercel.json` files contain the required build/function configuration.

## Official references

- [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon)
- [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading)
- [Alpaca options trading](https://docs.alpaca.markets/us/docs/options-trading)
- [Alpaca market-data streaming](https://docs.alpaca.markets/us/docs/streaming-market-data)
- [Alpaca trade-update streaming](https://docs.alpaca.markets/us/docs/websocket-streaming)

## Safety and scope

RaptorClick is a hackathon prototype for research and paper-trading demonstration. It does not provide financial advice, guarantee protection, or promise returns. Paper results do not reproduce every cost, fill condition, latency effect, or market impact present in live trading. Live-money execution is outside the MVP.

## License

A license has not been selected yet. Until one is added, normal copyright restrictions apply.
