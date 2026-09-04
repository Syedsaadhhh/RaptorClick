import asyncio
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ExecuteRequest, ExecutionReceipt, HedgeRun, PortfolioSnapshot, ReauctionRequest, StartRunRequest
from app.services.alpaca import AlpacaClient, AlpacaError
from app.services.engine import create_run, load_portfolio, reauction_run
from app.settings import Settings, get_settings
from app.store import REACTIONS_BY_IDEMPOTENCY, RECEIPTS_BY_IDEMPOTENCY, RUNS

app = FastAPI(title="RaptorClick API", version="0.1.0")

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/v1/portfolio", response_model=PortfolioSnapshot)
async def portfolio(settings: Settings = Depends(get_settings)) -> PortfolioSnapshot:
    try:
        return await load_portfolio(settings)
    except AlpacaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.post("/api/v1/runs", response_model=HedgeRun, status_code=201)
async def start_run(payload: StartRunRequest, settings: Settings = Depends(get_settings)) -> HedgeRun:
    run = await create_run(settings, payload.stress_shock_pct, payload.max_premium_pct, payload.use_ai)
    RUNS[run.run_id] = run
    return run

def _get_run(run_id: str) -> HedgeRun:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.get("/api/v1/runs/{run_id}", response_model=HedgeRun)
async def get_run(run_id: str) -> HedgeRun:
    return _get_run(run_id)

@app.get("/api/v1/runs/{run_id}/events")
async def get_events(run_id: str) -> StreamingResponse:
    run = _get_run(run_id)
    async def stream():
        for event in run.events:
            yield f"event: run_event\ndata: {event.model_dump_json()}\n\n"
            await asyncio.sleep(0)
        yield "event: end\ndata: {}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/api/v1/runs/{run_id}/execute", response_model=ExecutionReceipt)
async def execute_run(run_id: str, payload: ExecuteRequest, settings: Settings = Depends(get_settings)) -> ExecutionReceipt:
    run = _get_run(run_id)
    existing = RECEIPTS_BY_IDEMPOTENCY.get(payload.idempotency_key)
    if existing:
        if existing.run_id != run_id or existing.mode != payload.mode:
            raise HTTPException(status_code=409, detail="Idempotency key already used for a different request")
        return existing
    if run.risk_verdict.status != "approved" or not run.selected_bid_id:
        raise HTTPException(status_code=409, detail="Run is not approved for execution")
    selected = next(bid for bid in run.bids if bid.id == run.selected_bid_id)
    if payload.mode == "dry_run":
        receipt = ExecutionReceipt(receipt_id=f"rcpt-{uuid4().hex[:12]}", mode="dry_run", status="validated", idempotency_key=payload.idempotency_key, run_id=run_id, detail=f"Dry-run validated {selected.contracts} contract unit(s); no broker order sent.")
        run.current_state = "dry_run_complete"
    else:
        if not settings.enable_paper_execution:
            raise HTTPException(status_code=403, detail="Paper execution is disabled by configuration")
        if settings.demo_mode:
            raise HTTPException(status_code=409, detail="Paper execution is unavailable while demo mode is enabled")
        if not any(receipt.mode == "dry_run" and receipt.status == "validated" for receipt in run.receipts):
            raise HTTPException(status_code=409, detail="A successful dry-run is required before paper execution")
        if selected.strategy != "protective_put" or not selected.contract_symbol:
            raise HTTPException(status_code=409, detail="MVP paper router currently supports a single-leg protective put only")
        order = {"symbol": selected.contract_symbol, "qty": str(selected.contracts), "side": "buy", "type": "market", "time_in_force": "day", "position_intent": "buy_to_open", "client_order_id": payload.idempotency_key}
        try:
            broker = await AlpacaClient(settings).submit_paper_order(order)
        except AlpacaError as exc:
            receipt = ExecutionReceipt(receipt_id=f"rcpt-{uuid4().hex[:12]}", mode="paper", status="failed", idempotency_key=payload.idempotency_key, run_id=run_id, detail=str(exc))
        else:
            receipt = ExecutionReceipt(receipt_id=f"rcpt-{uuid4().hex[:12]}", mode="paper", status="submitted", idempotency_key=payload.idempotency_key, run_id=run_id, broker_order_id=str(broker.get("id")) if broker.get("id") else None, detail="Paper order submitted to Alpaca.")
            run.current_state = "paper_order_submitted"
    RECEIPTS_BY_IDEMPOTENCY[payload.idempotency_key] = receipt
    run.receipts.append(receipt)
    return receipt

@app.post("/api/v1/runs/{run_id}/reauction", response_model=HedgeRun)
async def reauction(run_id: str, payload: ReauctionRequest, settings: Settings = Depends(get_settings)) -> HedgeRun:
    run = _get_run(run_id)
    if payload.idempotency_key in REACTIONS_BY_IDEMPOTENCY:
        return run
    REACTIONS_BY_IDEMPOTENCY.add(payload.idempotency_key)
    return reauction_run(run, payload.drift_pct, settings.reauction_drift_threshold_pct)
