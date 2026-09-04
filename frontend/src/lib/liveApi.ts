import type {
  ExecutionReceipt,
  HedgeRun,
  RiskCheck,
  RunEvent,
  RunState,
} from "@/demo/models";
import { RUN_STATES } from "@/demo/models";

type ApiRun = {
  run_id: string;
  current_state: RunState;
  portfolio: {
    as_of: string;
    account_status: string;
    equity: number;
    drawdown_pct: number | null;
    gross_exposure: number;
    concentration_pct: number | null;
    source: "alpaca-paper" | "synthetic-demo" | "unavailable";
  };
  scenarios: Array<{ id: string; name: string; severity: "LOW" | "ELEVATED" | "SEVERE"; estimated_loss: number }>;
  bids: Array<{
    id: string;
    strategy: string;
    contracts: number;
    premium: number;
    estimated_protection: number;
    score: number;
    source: string;
    rationale: string;
  }>;
  selected_bid_id: string | null;
  risk_verdict: { status: "approved" | "rejected"; reasons: string[]; checks: Array<{ rule: string; passed: boolean; detail: string }> };
  shadow: { unprotected_loss: number; protected_loss: number; hedge_cost: number; protection_delta: number } | null;
  events: Array<{ id: string; at: string; state: RunState; actor: string; message: string }>;
  receipts: Array<{ receipt_id: string; mode: "dry_run" | "paper"; status: "validated" | "submitted" | "rejected" | "failed"; detail: string }>;
};

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export const isLiveApiConfigured = Boolean(baseUrl);

function money(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function signedMoney(value: number) {
  return `${value < 0 ? "−" : ""}${money(Math.abs(value))}`;
}

function eventTone(state: RunState): RunEvent["tone"] {
  if (["risk_rejected", "failed"].includes(state)) return "danger";
  if (state === "reauction_required") return "warning";
  if (["approved", "dry_run_complete", "completed"].includes(state)) return "positive";
  return state === "idle" ? "neutral" : "active";
}

function mapChecks(checks: ApiRun["risk_verdict"]["checks"]): RiskCheck[] {
  return checks.map((check) => ({ label: check.rule, status: check.passed ? "passed" : "failed", detail: check.detail }));
}

export function mapApiRun(run: ApiRun): HedgeRun {
  const protectionState = run.risk_verdict.status === "approved" ? "protected" : "rejected";
  const exposurePct = run.portfolio.equity > 0 ? (run.portfolio.gross_exposure / run.portfolio.equity) * 100 : 0;
  const selectedBid = run.bids.find((bid) => bid.id === run.selected_bid_id);

  return {
    runId: run.run_id,
    currentState: run.current_state,
    currentStep: Math.max(0, RUN_STATES.indexOf(run.current_state)),
    portfolio: {
      portfolioName: run.portfolio.source === "alpaca-paper" ? "Alpaca paper portfolio" : "Synthetic demo portfolio",
      asOf: new Date(run.portfolio.as_of).toLocaleString(),
      equity: money(run.portfolio.equity),
      equityValue: run.portfolio.equity,
      drawdownPct: run.portfolio.drawdown_pct ?? 0,
      exposurePct,
      concentrationPct: run.portfolio.concentration_pct ?? 0,
      protectionState,
      protectionLabel: protectionState === "protected" ? "RISK APPROVED" : "RISK REJECTED",
      netDelta: "Not calculated",
    },
    scenarios: run.scenarios.map((scenario) => ({
      id: scenario.id,
      name: scenario.name,
      severity: scenario.severity,
      stressedLoss: signedMoney(scenario.estimated_loss),
      affectedPositions: "Current portfolio",
      color: scenario.severity === "SEVERE" ? "red" : scenario.severity === "ELEVATED" ? "amber" : "green",
    })),
    bids: run.bids.map((bid) => ({
      id: bid.id,
      strategy: bid.strategy.replaceAll("_", " "),
      contractCount: `${bid.contracts} contract${bid.contracts === 1 ? "" : "s"}`,
      premium: money(bid.premium),
      estimatedProtection: signedMoney(bid.estimated_protection),
      rankingScore: bid.score,
      source: bid.source,
      selected: bid.id === run.selected_bid_id,
    })),
    rankings: [...run.bids].sort((a, b) => b.score - a.score).map((bid, index) => ({
      bidId: bid.id,
      rank: index + 1,
      score: bid.score,
      rationale: bid.rationale,
    })),
    riskVerdict: {
      status: run.risk_verdict.status,
      headline: run.risk_verdict.status === "approved" ? "Approved to protect" : "Risk rejected",
      rationale: run.risk_verdict.reasons.join(" ") || (selectedBid ? selectedBid.rationale : "No eligible hedge was selected."),
      checks: mapChecks(run.risk_verdict.checks),
    },
    shadowComparison: run.shadow ? [
      { label: "Stress loss", unprotected: signedMoney(run.shadow.unprotected_loss), protected: signedMoney(run.shadow.protected_loss), protectionDelta: money(run.shadow.protection_delta), unit: "loss avoided" },
      { label: "Hedge cost", unprotected: "$0", protected: signedMoney(run.shadow.hedge_cost), protectionDelta: signedMoney(-run.shadow.hedge_cost), unit: "premium" },
    ] : [],
    events: run.events.map((event) => ({
      id: event.id,
      time: new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      actor: event.actor.toUpperCase().includes("RISK") ? "RISK GOVERNOR" : event.actor.toUpperCase().includes("EXEC") ? "EXECUTION" : event.actor.toUpperCase().includes("AUCTION") ? "AUCTION" : "SYSTEM",
      message: event.message,
      source: run.portfolio.source.toUpperCase(),
      state: event.state,
      tone: eventTone(event.state),
    })),
    receipts: run.receipts.map((receipt): ExecutionReceipt => ({
      id: receipt.receipt_id,
      label: receipt.mode === "dry_run" ? "Dry run" : "Paper order",
      status: receipt.status === "validated" ? "dry-run" : receipt.status,
      executionId: receipt.receipt_id,
      detail: receipt.detail,
    })),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error("The live API URL is not configured.");
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) throw new Error((await response.text()) || `API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export const liveApi = {
  startRun: () => request<ApiRun>("/api/v1/runs", { method: "POST", body: JSON.stringify({ stress_shock_pct: -10, max_premium_pct: 2, use_ai: true }) }),
  executeDryRun: (runId: string) => request<ApiRun["receipts"][number]>(`/api/v1/runs/${runId}/execute`, { method: "POST", body: JSON.stringify({ mode: "dry_run", idempotency_key: `ui-dry-${crypto.randomUUID()}` }) }),
  reauction: (runId: string) => request<ApiRun>(`/api/v1/runs/${runId}/reauction`, { method: "POST", body: JSON.stringify({ drift_pct: 2, idempotency_key: `ui-reauction-${crypto.randomUUID()}` }) }),
  getRun: (runId: string) => request<ApiRun>(`/api/v1/runs/${runId}`),
  subscribe(runId: string, onEvent: (event: { state: RunState }) => void, onError: () => void) {
    if (!baseUrl) return () => undefined;
    const stream = new EventSource(`${baseUrl}/api/v1/runs/${runId}/events`);
    stream.addEventListener("run_event", (message) => {
      try { onEvent(JSON.parse((message as MessageEvent).data)); } catch { onError(); }
    });
    stream.addEventListener("end", () => stream.close());
    stream.onerror = () => { onError(); stream.close(); };
    return () => stream.close();
  },
};
