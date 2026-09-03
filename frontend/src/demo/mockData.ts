/* Obsidian Sentinel / deterministic demo dataset for each portfolio-insurance state. */

import type {
  AuctionRanking,
  ExecutionReceipt,
  HedgeBid,
  HedgeRun,
  PortfolioSnapshot,
  RiskVerdict,
  RunEvent,
  RunState,
  ShadowComparison,
  StressScenario,
} from "./models";

const portfolio: PortfolioSnapshot = {
  portfolioName: "Northstar / Global Macro",
  asOf: "30 AUG 2026 · 14:32:08 UTC",
  equity: "$18.42M",
  equityValue: 18420000,
  drawdownPct: 3.8,
  exposurePct: 62.4,
  concentrationPct: 28.1,
  protectionState: "in_review",
  protectionLabel: "HEDGE IN REVIEW",
  netDelta: "−$412K",
};

const scenarios: StressScenario[] = [
  { id: "s01", name: "Equity gap-down", severity: "SEVERE", stressedLoss: "−$1.42M", affectedPositions: "US growth · 18 lines", color: "red" },
  { id: "s02", name: "Rates reprice", severity: "ELEVATED", stressedLoss: "−$690K", affectedPositions: "Duration · 7 lines", color: "amber" },
  { id: "s03", name: "Volatility spike", severity: "ELEVATED", stressedLoss: "−$510K", affectedPositions: "Options · 12 lines", color: "amber" },
  { id: "s04", name: "FX liquidity gap", severity: "LOW", stressedLoss: "−$184K", affectedPositions: "EM FX · 4 lines", color: "green" },
];

const bids: HedgeBid[] = [
  { id: "bid-01", strategy: "Put spread / 95-88", contractCount: "1,200 contracts", premium: "$284K", estimatedProtection: "−$1.08M", rankingScore: 94.2, source: "Northstar Derivatives", selected: true },
  { id: "bid-02", strategy: "Put spread / 92-84", contractCount: "1,450 contracts", premium: "$247K", estimatedProtection: "−$914K", rankingScore: 89.7, source: "Axiom Markets" },
  { id: "bid-03", strategy: "Put ladder / 96-90-82", contractCount: "1,100 contracts", premium: "$221K", estimatedProtection: "−$776K", rankingScore: 86.1, source: "Crown Peak" },
  { id: "bid-04", strategy: "Tail hedge / 85 put", contractCount: "1,600 contracts", premium: "$198K", estimatedProtection: "−$642K", rankingScore: 81.8, source: "Blue Mesa" },
];

const rankings: AuctionRanking[] = [
  { bidId: "bid-01", rank: 1, score: 94.2, rationale: "Best protection-to-premium fit" },
  { bidId: "bid-02", rank: 2, score: 89.7, rationale: "Lower premium, wider loss band" },
  { bidId: "bid-03", rank: 3, score: 86.1, rationale: "Balanced tail response" },
  { bidId: "bid-04", rank: 4, score: 81.8, rationale: "Lowest premium, weaker first-loss cover" },
];

const shadowComparison: ShadowComparison[] = [
  { label: "Stress loss", unprotected: "−$1.42M", protected: "−$340K", protectionDelta: "$1.08M", unit: "loss avoided" },
  { label: "Portfolio delta", unprotected: "−7.7%", protected: "−1.8%", protectionDelta: "5.9 pp", unit: "delta" },
  { label: "Peak drawdown", unprotected: "11.4%", protected: "5.5%", protectionDelta: "5.9 pp", unit: "contained" },
];

const baseEvents: RunEvent[] = [
  { id: "evt-01", time: "14:31:58", actor: "OPERATOR", message: "Hedge run initialized for Northstar / Global Macro", source: "RUNNER", state: "idle", tone: "neutral" },
  { id: "evt-02", time: "14:32:01", actor: "SYSTEM", message: "Portfolio snapshot loaded · 186 positions · $18.42M equity", source: "PORTFOLIO API", state: "loading_portfolio", tone: "active" },
  { id: "evt-03", time: "14:32:04", actor: "SYSTEM", message: "4 shock paths staged against current exposures", source: "SHOCK LAB", state: "stress_testing", tone: "active" },
  { id: "evt-04", time: "14:32:08", actor: "AUCTION", message: "Auction window open · 4 executable bids received", source: "BID STREAM", state: "collecting_bids", tone: "active" },
  { id: "evt-05", time: "14:32:12", actor: "RISK GOVERNOR", message: "Bid ranking complete · selected bid-01", source: "RISK GOVERNOR", state: "judging", tone: "positive" },
  { id: "evt-06", time: "14:32:15", actor: "RISK GOVERNOR", message: "Risk rule failed: premium budget exceeded on the proposed band", source: "POLICY ENGINE", state: "risk_rejected", tone: "danger" },
  { id: "evt-07", time: "14:32:18", actor: "RISK GOVERNOR", message: "Selected hedge cleared all portfolio policy rules", source: "POLICY ENGINE", state: "approved", tone: "positive" },
  { id: "evt-08", time: "14:32:21", actor: "EXECUTION", message: "Dry-run matched 1,200 contracts · no market order sent", source: "EXECUTION SIM", state: "dry_run_complete", tone: "positive" },
  { id: "evt-09", time: "14:32:23", actor: "EXECUTION", message: "Paper order staged with broker routing metadata", source: "PAPER ROUTER", state: "paper_order_submitted", tone: "active" },
  { id: "evt-10", time: "14:32:27", actor: "EXECUTION", message: "Order receipt confirmed · protection state is active", source: "EXECUTION API", state: "completed", tone: "positive" },
  { id: "evt-11", time: "14:32:30", actor: "OPERATOR", message: "Underlying book moved 2.1% · new inputs require auction refresh", source: "RUNNER", state: "reauction_required", tone: "warning" },
  { id: "evt-12", time: "14:32:33", actor: "SYSTEM", message: "Auction halted after venue acknowledgement timeout", source: "BID STREAM", state: "failed", tone: "danger" },
];

const baseReceipts: ExecutionReceipt[] = [
  { id: "rcpt-01", label: "Dry run", status: "dry-run", executionId: "SIM-8K2Q-94", detail: "1,200 contracts · selected bid-01" },
  { id: "rcpt-02", label: "Paper order", status: "submitted", executionId: "PPR-4H7M-21", detail: "Routing staged · awaiting venue ack" },
  { id: "rcpt-03", label: "Live fill", status: "filled", executionId: "FIL-2N8A-07", detail: "Protection state active · 14:32:27 UTC" },
  { id: "rcpt-04", label: "Rejected", status: "rejected", executionId: "RJT-9V1C-52", detail: "Premium budget rule · no order sent" },
  { id: "rcpt-05", label: "Failed", status: "failed", executionId: "ERR-6P0D-18", detail: "Venue acknowledgement timeout · safe halt" },
];

const checks: RiskVerdict["checks"] = [
  { label: "Counterparty eligibility", status: "passed", detail: "Tier 1 venue · approved list" },
  { label: "Premium budget", status: "passed", detail: "$284K / $300K ceiling" },
  { label: "Concentration cap", status: "passed", detail: "28.1% / 35.0% ceiling" },
  { label: "Liquidity window", status: "passed", detail: "12 min remaining" },
];

function getVerdict(state: RunState): RiskVerdict {
  if (state === "risk_rejected") {
    return {
      status: "rejected",
      headline: "Risk rejected",
      rationale: "The proposed hedge is blocked until the premium band is recalculated against updated inputs.",
      checks: checks.map((check) => check.label === "Premium budget" ? { ...check, status: "failed", detail: "$318K / $300K ceiling" } : check),
    };
  }
  if (state === "failed") {
    return {
      status: "pending",
      headline: "Execution halted",
      rationale: "The venue did not acknowledge the order inside the execution window. No live order was confirmed.",
      checks: checks.map((check) => check.label === "Liquidity window" ? { ...check, status: "failed", detail: "Venue acknowledgement timeout" } : check),
    };
  }
  if (["approved", "dry_run_complete", "paper_order_submitted", "completed"].includes(state)) {
    return { status: "approved", headline: "Approved to protect", rationale: "Selected structure clears the active policy set and is eligible for paper execution.", checks };
  }
  return { status: "pending", headline: "Awaiting verdict", rationale: "Risk Governor is evaluating the current inputs and ranked bids.", checks: checks.map((check) => ({ ...check, status: "pending" })) };
}

function getProtectionState(state: RunState): PortfolioSnapshot["protectionState"] {
  if (state === "risk_rejected") return "rejected";
  if (["approved", "dry_run_complete", "paper_order_submitted", "completed"].includes(state)) return "protected";
  return "in_review";
}

export function getHedgeRun(state: RunState): HedgeRun {
  const currentStep = Math.max(0, RUN_STATE_INDEX[state]);
  const events = baseEvents.filter((event) => RUN_STATE_INDEX[event.state] <= currentStep);
  const visibleReceipts = baseReceipts.filter((receipt) => {
    if (["idle", "loading_portfolio", "stress_testing", "collecting_bids", "judging", "reauction_required"].includes(state)) return false;
    if (state === "risk_rejected") return receipt.status === "rejected";
    if (state === "failed") return receipt.status === "failed" || receipt.status === "submitted";
    if (state === "completed") return true;
    if (state === "paper_order_submitted") return receipt.status === "dry-run" || receipt.status === "submitted";
    if (state === "dry_run_complete") return receipt.status === "dry-run";
    return receipt.status === "dry-run";
  });
  return {
    runId: "HR-2026-08-30-014",
    currentState: state,
    currentStep,
    portfolio: { ...portfolio, protectionState: getProtectionState(state), protectionLabel: getProtectionState(state) === "protected" ? "PROTECTION ACTIVE" : getProtectionState(state) === "rejected" ? "RISK REJECTED" : "HEDGE IN REVIEW" },
    scenarios,
    bids,
    rankings,
    riskVerdict: getVerdict(state),
    shadowComparison,
    events,
    receipts: visibleReceipts,
  };
}

export const RUN_STATE_INDEX: Record<RunState, number> = {
  idle: 0,
  loading_portfolio: 1,
  stress_testing: 2,
  collecting_bids: 3,
  judging: 4,
  risk_rejected: 5,
  approved: 6,
  dry_run_complete: 7,
  paper_order_submitted: 8,
  completed: 9,
  reauction_required: 10,
  failed: 11,
};
