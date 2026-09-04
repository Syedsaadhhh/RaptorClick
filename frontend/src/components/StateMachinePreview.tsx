/* Replay preview widget: a compact, labelled walkthrough of the RaptorClick state machine. */

import { ArrowUpRight, ChevronRight, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "wouter";
import { demoApi } from "@/lib/demoApi";
import { RUN_STATES, type HedgeRun, type RunState } from "@/demo/models";

const STATE_META: Record<RunState, { short: string; label: string }> = {
  idle: { short: "IDLE", label: "Ready for a new hedge run" },
  loading_portfolio: { short: "LOAD", label: "Snapshot ingestion in progress" },
  stress_testing: { short: "SHOCK", label: "Scenario paths are being computed" },
  collecting_bids: { short: "BIDS", label: "Auction window is open" },
  judging: { short: "JUDGE", label: "Risk Governor is ranking structures" },
  risk_rejected: { short: "BLOCK", label: "Policy gate blocked the proposal" },
  approved: { short: "PASS", label: "Selected hedge cleared policy" },
  dry_run_complete: { short: "DRY", label: "Simulation matched the order" },
  paper_order_submitted: { short: "PAPER", label: "Order staged for venue routing" },
  completed: { short: "DONE", label: "Protection state is active" },
  reauction_required: { short: "RE-AUC", label: "Inputs moved; refresh the auction" },
  failed: { short: "FAIL", label: "Execution halted safely" },
};

const TONE_BY_STATE: Record<RunState, string> = {
  idle: "neutral",
  loading_portfolio: "active",
  stress_testing: "active",
  collecting_bids: "active",
  judging: "active",
  risk_rejected: "danger",
  approved: "positive",
  dry_run_complete: "positive",
  paper_order_submitted: "active",
  completed: "positive",
  reauction_required: "warning",
  failed: "danger",
};

function formatTelemetry(value: number, suffix = "%") {
  return `${value.toFixed(1)}${suffix}`;
}

export default function StateMachinePreview() {
  const [state, setState] = useState<RunState>("idle");
  const [run, setRun] = useState<HedgeRun | null>(null);
  const currentIndex = RUN_STATES.indexOf(state);

  useEffect(() => {
    let cancelled = false;
    demoApi.getRun(state).then((snapshot) => {
      if (!cancelled) setRun(snapshot);
    });
    return () => { cancelled = true; };
  }, [state]);

  const nextStep = () => setState(RUN_STATES[Math.min(currentIndex + 1, RUN_STATES.length - 1)]);
  const reset = () => setState("idle");
  const riskTone = run?.riskVerdict.status === "rejected" ? "danger" : run?.riskVerdict.status === "approved" ? "positive" : "active";
  const progress = ((currentIndex + 1) / RUN_STATES.length) * 100;

  return (
    <div className="state-preview" aria-label="Live State Machine Preview">
      <div className="state-preview-topline">
        <div>
          <p className="eyebrow">Replay preview / control room</p>
          <h2>State machine monitor</h2>
        </div>
        <span className={`preview-status preview-status-${TONE_BY_STATE[state]}`}><span className="status-dot" />{STATE_META[state].short}</span>
      </div>

      <div className="state-preview-main">
        <div className="preview-orbit" aria-hidden="true"><span /><i /><b /></div>
        <div className="preview-current-state"><span className="mono">CURRENT STATE</span><strong>{STATE_META[state].label}</strong><small>{String(currentIndex + 1).padStart(2, "0")} / 12 gates complete</small></div>
      </div>

      <div className="preview-progress" aria-label={`${Math.round(progress)} percent through the state machine`}><span style={{ width: `${progress}%` }} /></div>
      <div className="preview-rail" role="list" aria-label="State machine steps">
        {RUN_STATES.map((item, index) => <button type="button" role="listitem" key={item} className={`preview-step ${index === currentIndex ? "is-current" : ""} ${index < currentIndex ? "is-past" : ""}`} onClick={() => setState(item)} aria-label={`Jump to ${STATE_META[item].label}`} aria-current={index === currentIndex ? "step" : undefined}><span>{String(index + 1).padStart(2, "0")}</span><strong>{STATE_META[item].short}</strong></button>)}
      </div>

      <div className="preview-telemetry">
        <div><span>DRAWDOWN</span><strong>{run ? formatTelemetry(run.portfolio.drawdownPct) : "--"}</strong></div>
        <div><span>EXPOSURE</span><strong>{run ? formatTelemetry(run.portfolio.exposurePct) : "--"}</strong></div>
        <div><span>RISK GATE</span><strong className={`preview-risk-${riskTone}`}>{run?.riskVerdict.status?.toUpperCase() ?? "SYNC"}</strong></div>
      </div>

      <div className="preview-footer">
        <span className="preview-footnote"><span className="green-dot" /> {run ? run.runId : "SYNCING RUN"}</span>
        <div className="preview-actions"><button type="button" className="preview-action" onClick={reset}><RotateCcw size={12} /> Reset</button><button type="button" className="preview-action preview-action-primary" onClick={nextStep} disabled={currentIndex === RUN_STATES.length - 1}>Next state <ChevronRight size={13} /></button><Link href="/control-room" className="preview-open">Open <ArrowUpRight size={12} /></Link></div>
      </div>
    </div>
  );
}
