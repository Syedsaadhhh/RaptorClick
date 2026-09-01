from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

RunState = Literal["idle", "loading_portfolio", "stress_testing", "collecting_bids", "judging", "risk_rejected", "approved", "dry_run_complete", "paper_order_submitted", "completed", "reauction_required", "failed"]

class Position(BaseModel):
    symbol: str
    qty: float
    market_value: float
    current_price: float | None = None
    sector: str | None = None

class PortfolioSnapshot(BaseModel):
    as_of: datetime
    account_status: str
    equity: float
    last_equity: float | None = None
    drawdown_pct: float | None = None
    gross_exposure: float
    concentration_pct: float | None = None
    positions: list[Position]
    source: Literal["alpaca-paper", "synthetic-demo", "unavailable"]

class StressScenario(BaseModel):
    id: str
    name: str
    shock_pct: float
    estimated_loss: float
    severity: Literal["LOW", "ELEVATED", "SEVERE"]

class ScoreComponents(BaseModel):
    protection: float = Field(ge=0, le=1)
    cost_efficiency: float = Field(ge=0, le=1)
    liquidity: float = Field(ge=0, le=1)

class HedgeBid(BaseModel):
    id: str
    strategy: Literal["protective_put", "put_spread", "tail_put"]
    underlying: str
    contract_symbol: str | None = None
    secondary_contract_symbol: str | None = None
    contracts: int = Field(ge=1)
    premium: float = Field(ge=0)
    estimated_protection: float = Field(ge=0)
    liquidity_score: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=100)
    score_components: ScoreComponents
    source: Literal["alpaca-option-chain", "synthetic-demo"]
    rationale: str

class RiskCheck(BaseModel):
    rule: str
    passed: bool
    detail: str

class RiskVerdict(BaseModel):
    status: Literal["approved", "rejected"]
    checks: list[RiskCheck]
    reasons: list[str]

class ShadowComparison(BaseModel):
    unprotected_loss: float
    protected_loss: float
    hedge_cost: float
    protection_delta: float

class RunEvent(BaseModel):
    id: str
    at: datetime
    state: RunState
    actor: str
    message: str

class ExecutionReceipt(BaseModel):
    receipt_id: str
    mode: Literal["dry_run", "paper"]
    status: Literal["validated", "submitted", "rejected", "failed"]
    idempotency_key: str
    run_id: str
    broker_order_id: str | None = None
    detail: str

class HedgeRun(BaseModel):
    run_id: str
    current_state: RunState
    portfolio: PortfolioSnapshot
    scenarios: list[StressScenario]
    bids: list[HedgeBid]
    selected_bid_id: str | None
    risk_verdict: RiskVerdict
    shadow: ShadowComparison | None
    events: list[RunEvent]
    receipts: list[ExecutionReceipt] = Field(default_factory=list)
    option_snapshots_seen: int = 0
    ai_strategy_hints: list[str] = Field(default_factory=list)
    degraded_reason: str | None = None

class StartRunRequest(BaseModel):
    stress_shock_pct: float = Field(default=-10.0, ge=-50.0, le=-1.0)
    max_premium_pct: float = Field(default=2.0, gt=0.0, le=20.0)
    use_ai: bool = True

class ExecuteRequest(BaseModel):
    mode: Literal["dry_run", "paper"] = "dry_run"
    idempotency_key: str = Field(min_length=8, max_length=128)

class ReauctionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    drift_pct: float = Field(default=2.0, ge=0.0, le=100.0)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)
