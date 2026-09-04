# RaptorClick backend vertical slice

FastAPI service for the paper-trading hedge-auction loop.

## Start locally

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

`RAPTORCLICK_DEMO_MODE=true` is the safe default. It uses clearly labelled synthetic fixtures and never sends a broker order.

To read a real Alpaca paper account, set `RAPTORCLICK_DEMO_MODE=false` and provide `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in `.env`.

Paper execution remains disabled until `ENABLE_PAPER_EXECUTION=true`. Even then, the MVP router requires a successful dry-run first and currently routes only a selected single-leg protective put. Live-money routing is not implemented.

## Optional Featherless strategy hints

Set `FEATHERLESS_API_KEY` to allow the proposal layer to suggest only one of three strategy categories. The model never supplies prices, contract quotes, risk limits, or final scores. Those remain deterministic.

## Test

```bash
cd backend
pytest -q
```

## API

- `GET /healthz`
- `GET /api/v1/portfolio`
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events` (SSE)
- `POST /api/v1/runs/{run_id}/execute`
- `POST /api/v1/runs/{run_id}/reauction`

## Safety contract

- Missing/incomplete market data cannot silently become approval.
- LLM output is untrusted and cannot alter numeric gates.
- Dry-run is the default execution mode.
- Idempotency keys prevent duplicate execution requests in the MVP process lifetime.
- Logs and responses never include API secrets.
