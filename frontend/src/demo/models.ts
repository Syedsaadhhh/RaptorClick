/* Obsidian Sentinel / domain contracts for the RaptorClick control-room demo. */

export type RunState =
  | "idle"
  | "loading_portfolio"
  | "stress_testing"
  | "collecting_bids"
  | "judging"
  | "risk_rejected"
  | "approved"
  | "dry_run_complete"
  | "paper_order_submitted"
  | "completed"
  | "reauction_required"
  | "failed";

export const RUN_STATES: RunState[] = [
  "idle",
  "loading_portfolio",
  "stress_testing",
  "collecting_bids",
  "judging",
  "risk_rejected",
  "approved",
  "dry_run_complete",
  "paper_order_submitted",
  "completed",
  "reauction_required",
  "failed",
];

export interface PortfolioSnapshot {
  portfolioName: string;
  asOf: string;
  equity: string;
  equityValue: number;
  drawdownPct: number;
  exposurePct: number;
  concentrationPct: number;
  protectionState: "unprotected" | "in_review" | "protected" | "rejected";
  protectionLabel: string;
  netDelta: string;
}

export interface StressScenario {
  id: string;
  name: string;
  severity: "LOW" | "ELEVATED" | "SEVERE";
  stressedLoss: string;
  affectedPositions: string;
  color: "green" | "amber" | "red";
}

export interface HedgeBid {
  id: string;
  strategy: string;
  contractCount: string;
  premium: string;
  estimatedProtection: string;
  rankingScore: number;
  source: string;
  selected?: boolean;
}

export interface AuctionRanking {
  bidId: string;
  rank: number;
  score: number;
  rationale: string;
}

export interface RiskCheck {
  label: string;
  status: "passed" | "failed" | "pending";
  detail: string;
}

export interface RiskVerdict {
  status: "approved" | "rejected" | "pending";
  headline: string;
  rationale: string;
  checks: RiskCheck[];
}

export interface ShadowComparison {
  label: string;
  unprotected: string;
  protected: string;
  protectionDelta: string;
  unit: string;
}

export interface RunEvent {
  id: string;
  time: string;
  actor: "SYSTEM" | "RISK GOVERNOR" | "AUCTION" | "EXECUTION" | "OPERATOR";
  message: string;
  source: string;
  state: RunState;
  tone: "neutral" | "active" | "positive" | "warning" | "danger";
}

export interface ExecutionReceipt {
  id: string;
  label: string;
  status: "dry-run" | "submitted" | "filled" | "rejected" | "failed";
  executionId: string;
  detail: string;
}

export interface HedgeRun {
  runId: string;
  currentState: RunState;
  currentStep: number;
  portfolio: PortfolioSnapshot;
  scenarios: StressScenario[];
  bids: HedgeBid[];
  rankings: AuctionRanking[];
  riskVerdict: RiskVerdict;
  shadowComparison: ShadowComparison[];
  events: RunEvent[];
  receipts: ExecutionReceipt[];
}
