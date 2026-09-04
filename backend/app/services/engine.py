import math
import re
from uuid import uuid4

from app.models import HedgeBid, HedgeRun, PortfolioSnapshot, Position, RiskCheck, RiskVerdict, RunEvent, ScoreComponents, ShadowComparison, StressScenario, utcnow
from app.services.alpaca import AlpacaClient, AlpacaError
from app.services.featherless import get_strategy_hints
from app.settings import Settings

_OPTION_RE = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")

def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default

def _event(state: str, actor: str, message: str) -> RunEvent:
    return RunEvent(id=f"evt-{uuid4().hex[:10]}", at=utcnow(), state=state, actor=actor, message=message)

def _demo_portfolio() -> PortfolioSnapshot:
    positions = [
        Position(symbol="SPY", qty=120, market_value=78120, current_price=651.0),
        Position(symbol="NVDA", qty=80, market_value=14320, current_price=179.0),
        Position(symbol="AAPL", qty=70, market_value=16240, current_price=232.0),
    ]
    equity = 120000.0
    gross = sum(abs(p.market_value) for p in positions)
    return PortfolioSnapshot(as_of=utcnow(), account_status="PAPER_DEMO", equity=equity, last_equity=123000.0, drawdown_pct=round((equity / 123000.0 - 1) * 100, 3), gross_exposure=gross, concentration_pct=round(max(abs(p.market_value) for p in positions) / gross * 100, 3), positions=positions, source="synthetic-demo")

async def load_portfolio(settings: Settings) -> PortfolioSnapshot:
    """Load a paper portfolio or return an explicit synthetic demo snapshot."""
    if settings.demo_mode:
        return _demo_portfolio()
    client = AlpacaClient(settings)
    account, raw_positions = await client.get_account(), await client.get_positions()
    positions = [Position(symbol=str(row.get("symbol", "UNKNOWN")), qty=_float(row.get("qty")), market_value=_float(row.get("market_value")), current_price=_float(row.get("current_price")) or None) for row in raw_positions]
    equity = _float(account.get("equity"))
    last_equity = _float(account.get("last_equity")) or None
    gross = sum(abs(p.market_value) for p in positions)
    concentration = max((abs(p.market_value) for p in positions), default=0.0)
    return PortfolioSnapshot(as_of=utcnow(), account_status=str(account.get("status", "UNKNOWN")), equity=equity, last_equity=last_equity, drawdown_pct=round((equity / last_equity - 1) * 100, 3) if last_equity else None, gross_exposure=gross, concentration_pct=round(concentration / gross * 100, 3) if gross else None, positions=positions, source="alpaca-paper")

def build_scenarios(portfolio: PortfolioSnapshot, shock_pct: float) -> list[StressScenario]:
    """Create deterministic portfolio-wide shock scenarios."""
    gross = portfolio.gross_exposure
    shocks = [shock_pct * 0.6, shock_pct, shock_pct * 1.4]
    names = ["Moderate gap", "Primary downside", "Severe gap"]
    severities = ["ELEVATED", "SEVERE", "SEVERE"]
    return [StressScenario(id=f"shock-{index + 1}", name=names[index], shock_pct=round(shock, 3), estimated_loss=round(abs(shock) / 100 * gross, 2), severity=severities[index]) for index, shock in enumerate(shocks)]

def _quote(snapshot: dict) -> tuple[float, float]:
    quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
    bid = _float(quote.get("bp") or quote.get("bid_price") or quote.get("bidPrice"))
    ask = _float(quote.get("ap") or quote.get("ask_price") or quote.get("askPrice"))
    return bid, ask

def _strike(symbol: str) -> float | None:
    match = _OPTION_RE.match(symbol)
    if not match or match.group(3) != "P":
        return None
    return int(match.group(4)) / 1000

def _liquidity_score(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or ask < bid:
        return 0.0
    mid = (bid + ask) / 2
    if mid <= 0:
        return 0.0
    spread_pct = (ask - bid) / mid
    return round(max(0.0, min(1.0, 1 - spread_pct / 0.25)), 4)

def _score(protection: float, premium: float, stress_loss: float, liquidity: float) -> tuple[float, ScoreComponents]:
    protection_component = min(1.0, protection / max(stress_loss, 1.0))
    efficiency_component = min(1.0, protection / max(premium * 4, 1.0))
    components = ScoreComponents(protection=round(protection_component, 4), cost_efficiency=round(efficiency_component, 4), liquidity=round(liquidity, 4))
    score = 100 * (0.5 * components.protection + 0.3 * components.cost_efficiency + 0.2 * components.liquidity)
    return round(score, 2), components

def _demo_bids(portfolio: PortfolioSnapshot, stress_loss: float) -> list[HedgeBid]:
    underlying = portfolio.positions[0].symbol if portfolio.positions else "SPY"
    raw = [("protective_put", 960.0, stress_loss * 0.78, 0.90), ("put_spread", 640.0, stress_loss * 0.62, 0.95), ("tail_put", 390.0, stress_loss * 0.34, 0.88)]
    bids: list[HedgeBid] = []
    for index, (strategy, premium, protection, liquidity) in enumerate(raw, start=1):
        score, components = _score(protection, premium, stress_loss, liquidity)
        bids.append(HedgeBid(id=f"bid-{index}", strategy=strategy, underlying=underlying, contracts=max(1, math.ceil(abs(portfolio.positions[0].qty) / 100)) if portfolio.positions else 1, premium=premium, estimated_protection=round(protection, 2), liquidity_score=liquidity, score=score, score_components=components, source="synthetic-demo", rationale="Synthetic fixture used only to exercise the deterministic auction contract."))
    return sorted(bids, key=lambda bid: bid.score, reverse=True)

def _real_bids(portfolio: PortfolioSnapshot, chain: dict, stress_loss: float) -> list[HedgeBid]:
    if not portfolio.positions:
        return []
    top = max(portfolio.positions, key=lambda p: abs(p.market_value))
    spot = top.current_price or 0.0
    snapshots = chain.get("snapshots") if isinstance(chain, dict) else None
    if not isinstance(snapshots, dict) or spot <= 0:
        return []
    candidates: list[tuple[str, float, float, float]] = []
    for symbol, snapshot in snapshots.items():
        strike = _strike(symbol)
        if strike is None or not isinstance(snapshot, dict):
            continue
        bid_px, ask_px = _quote(snapshot)
        if ask_px <= 0:
            continue
        distance = abs(strike / spot - 0.95)
        candidates.append((symbol, strike, ask_px, _liquidity_score(bid_px, ask_px) - distance))
    candidates.sort(key=lambda row: row[3], reverse=True)
    chosen = candidates[:3]
    contracts = max(1, math.ceil(abs(top.qty) / 100))
    stressed_price = spot * 0.90
    bids: list[HedgeBid] = []
    strategies = ["protective_put", "put_spread", "tail_put"]
    for index, row in enumerate(chosen):
        symbol, strike, ask_px, adjusted_liquidity = row
        premium = ask_px * 100 * contracts
        payoff = max(0.0, strike - stressed_price) * 100 * contracts
        protection = max(0.0, payoff - premium)
        liquidity = max(0.0, min(1.0, adjusted_liquidity + abs(strike / spot - 0.95)))
        score, components = _score(protection, premium, stress_loss, liquidity)
        bids.append(HedgeBid(id=f"bid-{index + 1}", strategy=strategies[index], underlying=top.symbol, contract_symbol=symbol, contracts=contracts, premium=round(premium, 2), estimated_protection=round(protection, 2), liquidity_score=round(liquidity, 4), score=score, score_components=components, source="alpaca-option-chain", rationale="Quote-derived candidate. Final ranking is deterministic and independent of LLM output."))
    return sorted(bids, key=lambda bid: bid.score, reverse=True)

def risk_governor(portfolio: PortfolioSnapshot, selected: HedgeBid | None, max_premium_pct: float) -> RiskVerdict:
    """Apply hard deterministic approval rules."""
    if selected is None:
        return RiskVerdict(status="rejected", checks=[RiskCheck(rule="candidate_available", passed=False, detail="No valid hedge candidate available")], reasons=["No valid hedge candidate available"])
    premium_budget = portfolio.equity * max_premium_pct / 100
    checks = [
        RiskCheck(rule="premium_budget", passed=selected.premium <= premium_budget, detail=f"premium={selected.premium:.2f}; ceiling={premium_budget:.2f}"),
        RiskCheck(rule="positive_protection", passed=selected.estimated_protection > 0, detail=f"estimated_protection={selected.estimated_protection:.2f}"),
        RiskCheck(rule="liquidity_floor", passed=selected.liquidity_score >= 0.25, detail=f"liquidity_score={selected.liquidity_score:.3f}; floor=0.250"),
    ]
    reasons = [check.detail for check in checks if not check.passed]
    return RiskVerdict(status="approved" if not reasons else "rejected", checks=checks, reasons=reasons)

async def create_run(settings: Settings, shock_pct: float, max_premium_pct: float, use_ai: bool) -> HedgeRun:
    events = [_event("loading_portfolio", "Portfolio Sentinel", "Loading portfolio state")]
    degraded_reason: str | None = None
    option_count = 0
    try:
        portfolio = await load_portfolio(settings)
    except AlpacaError as exc:
        portfolio = PortfolioSnapshot(as_of=utcnow(), account_status="UNAVAILABLE", equity=0, gross_exposure=0, positions=[], source="unavailable")
        degraded_reason = str(exc)
    events.append(_event("stress_testing", "Shock Lab", "Running deterministic downside scenarios"))
    scenarios = build_scenarios(portfolio, shock_pct)
    stress_loss = scenarios[1].estimated_loss if len(scenarios) > 1 else 0.0
    hints = await get_strategy_hints(settings, portfolio, scenarios) if use_ai else []
    events.append(_event("collecting_bids", "Hedge Auction", "Collecting typed hedge candidates"))
    bids: list[HedgeBid] = []
    if portfolio.source == "synthetic-demo":
        bids = _demo_bids(portfolio, stress_loss)
    elif portfolio.source == "alpaca-paper" and portfolio.positions:
        top = max(portfolio.positions, key=lambda p: abs(p.market_value))
        try:
            chain = await AlpacaClient(settings).get_option_chain(top.symbol)
            snapshots = chain.get("snapshots", {}) if isinstance(chain, dict) else {}
            option_count = len(snapshots) if isinstance(snapshots, dict) else 0
            bids = _real_bids(portfolio, chain, stress_loss)
        except AlpacaError as exc:
            degraded_reason = str(exc)
    selected = bids[0] if bids else None
    events.append(_event("judging", "Risk Governor", "Ranking candidates and applying hard risk gates"))
    verdict = risk_governor(portfolio, selected, max_premium_pct)
    state = "approved" if verdict.status == "approved" else "risk_rejected"
    events.append(_event(state, "Risk Governor", f"Risk verdict: {verdict.status}"))
    shadow = None
    if selected:
        protected_loss = max(0.0, stress_loss - selected.estimated_protection) + selected.premium
        shadow = ShadowComparison(unprotected_loss=round(stress_loss, 2), protected_loss=round(protected_loss, 2), hedge_cost=round(selected.premium, 2), protection_delta=round(stress_loss - protected_loss, 2))
    return HedgeRun(run_id=f"run-{uuid4().hex[:12]}", current_state=state, portfolio=portfolio, scenarios=scenarios, bids=bids, selected_bid_id=selected.id if selected else None, risk_verdict=verdict, shadow=shadow, events=events, option_snapshots_seen=option_count, ai_strategy_hints=hints, degraded_reason=degraded_reason)

def reauction_run(run: HedgeRun, drift_pct: float, threshold_pct: float) -> HedgeRun:
    """Mark stale state and deterministically re-rank when drift exceeds threshold."""
    if drift_pct < threshold_pct:
        run.events.append(_event(run.current_state, "Monitor", f"Drift {drift_pct:.2f}% below re-auction threshold"))
        return run
    run.current_state = "reauction_required"
    run.events.append(_event("reauction_required", "Monitor", f"Portfolio drift {drift_pct:.2f}% invalidated prior ranking"))
    for index, bid in enumerate(run.bids):
        cost_factor = 1 + (index - 1) * drift_pct / 100
        protection_factor = 1 + (1 - index) * drift_pct / 200
        bid.premium = round(max(0.0, bid.premium * cost_factor), 2)
        bid.estimated_protection = round(max(0.0, bid.estimated_protection * protection_factor), 2)
        stress_loss = run.shadow.unprotected_loss if run.shadow else 1.0
        bid.score, bid.score_components = _score(bid.estimated_protection, bid.premium, stress_loss, bid.liquidity_score)
    run.bids.sort(key=lambda bid: bid.score, reverse=True)
    run.selected_bid_id = run.bids[0].id if run.bids else None
    return run
